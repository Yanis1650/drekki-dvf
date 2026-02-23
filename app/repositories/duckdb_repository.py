"""DuckDB repository implementations.

Uses DuckDB spatial extension for fast local queries.
"""

from datetime import date
from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb
from pyproj import Transformer

from app.domain.models import (
    DensificationScore,
    EnrichmentScore,
    MutationAggregate,
    NatureMutation,
    Parcelle,
    Transaction,
)
from app.infrastructure.duckdb_pool import DuckDBPool
from app.repositories.interfaces import (
    IEnrichmentRepository,
    ILandRepository,
    ITransactionRepository,
)


class DuckDBLandRepository(ILandRepository, ITransactionRepository, IEnrichmentRepository):
    """DuckDB implementation of land repositories.

    Uses DuckDB's spatial extension for efficient local querying.
    Supports both legacy single-DB and multi-dept pool modes.
    """

    def __init__(self, db_path: Path | str, pool: DuckDBPool | None = None) -> None:
        self._db_path = Path(db_path)
        self._pool = pool
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self, dept: str | None = None) -> duckdb.DuckDBPyConnection:
        """Get connection, routing to per-dept DB when pool is available."""
        if self._pool and dept:
            return self._pool.get_connection(dept)

        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
            self._conn.execute("INSTALL spatial; LOAD spatial;")
        return self._conn

    def _dept_from_parcelle(self, id_parcelle: str) -> str | None:
        if self._pool and id_parcelle and len(id_parcelle) >= 2:
            return DuckDBPool.extract_dept(id_parcelle)
        return None

    def _dept_from_commune(self, code_commune: str) -> str | None:
        if self._pool and code_commune and len(code_commune) >= 2:
            return DuckDBPool.extract_dept(code_commune)
        return None

    async def get_parcelle_by_id(self, id_parcelle: str) -> Parcelle | None:
        """Retrieve a single parcel by its ID."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        result = conn.execute(
            """
            SELECT id_parcelle, code_commune, prefixe, section, numero,
                   ST_AsText(geometry) as geometry_wkt
            FROM parcelles
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return Parcelle(
            id_parcelle=result[0],
            code_commune=result[1],
            prefixe=result[2],
            section=result[3],
            numero=result[4],
            geometry_wkt=result[5],
            surface_m2=None,  # Column not in parcelles table
        )

    async def get_parcelles_by_commune(self, code_commune: str) -> list[Parcelle]:
        """Retrieve all parcels in a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, code_commune, prefixe, section, numero,
                   ST_AsText(geometry) as geometry_wkt, surface_m2
            FROM parcelles
            WHERE code_commune = ?
            """,
            [code_commune],
        ).fetchall()

        return [
            Parcelle(
                id_parcelle=r[0],
                code_commune=r[1],
                prefixe=r[2],
                section=r[3],
                numero=r[4],
                geometry_wkt=r[5],
                surface_m2=Decimal(str(r[6])) if r[6] else None,
            )
            for r in results
        ]

    async def get_transactions_geojson(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """Retrieve DVF transactions as GeoJSON Point features.
        
        Returns transaction points with properties: id, prix_m2, date, valeur_fonciere.
        Uses france_foncier_test table for transactions with coordinates.
        """
        conn = self._get_connection()

        query = """
            SELECT 
                id_mutation,
                longitude,
                latitude,
                prix_m2,
                date_mutation,
                valeur_fonciere,
                nature_mutation
            FROM france_foncier_test
            WHERE longitude BETWEEN ? AND ?
              AND latitude BETWEEN ? AND ?
              AND longitude IS NOT NULL
              AND latitude IS NOT NULL
            LIMIT ?
        """

        try:
            results = conn.execute(query, [min_x, max_x, min_y, max_y, limit]).fetchall()
            print(f"DEBUG: get_transactions_geojson found {len(results)} transactions")
        except Exception as e:
            print(f"ERROR: get_transactions_geojson failed: {e}")
            return '{"type": "FeatureCollection", "features": []}'

        features = []

        for r in results:
            mutation_id = r[0]
            lon, lat = float(r[1]), float(r[2])
            prix_m2 = float(r[3]) if r[3] else None
            date_mutation = str(r[4]) if r[4] else None
            valeur_fonciere = float(r[5]) if r[5] else None
            nature_mutation = r[6] if r[6] else None

            # Build properties for transaction point
            props = [f'"id": "{mutation_id}"']
            if prix_m2:
                props.append(f'"prix_m2": {prix_m2}')
            if date_mutation:
                props.append(f'"date": "{date_mutation}"')
            if valeur_fonciere:
                props.append(f'"valeur_fonciere": {valeur_fonciere}')
            if nature_mutation:
                props.append(f'"nature": "{nature_mutation}"')

            props_str = ", ".join(props)

            # Create Point geometry
            features.append(
                f'{{"type": "Feature", "properties": {{{props_str}}}, "geometry": {{"type": "Point", "coordinates": [{lon}, {lat}]}}}}'
            )

        return '{"type": "FeatureCollection", "features": [' + ",".join(features) + ']}'

    async def get_parcelles_geojson(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 500,
    ) -> str:
        """Retrieve cadastral parcels as GeoJSON Polygon features with BDNB enrichment.
        
        Returns parcel polygons with properties: id_parcelle, dpe, annee_construction.
        Uses parcelles table with LEFT JOIN on BDNB stats for DPE data.
        Limited to Dept 35 for performance (real geometry available).
        """
        conn = self._get_connection()

        try:
            # Convert WGS84 bbox to Lambert-93 using pyproj

            # Create transformer: WGS84 (EPSG:4326) -> Lambert-93 (EPSG:2154)
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)

            # Transform bbox corners
            min_x_l93, min_y_l93 = transformer.transform(min_x, min_y)
            max_x_l93, max_y_l93 = transformer.transform(max_x, max_y)

            print(f"DEBUG: WGS84 bbox: ({min_x}, {min_y}) -> ({max_x}, {max_y})")
            print(f"DEBUG: Lambert-93 bbox: ({min_x_l93:.2f}, {min_y_l93:.2f}) -> ({max_x_l93:.2f}, {max_y_l93:.2f})")

            # Step 1: Get parcelles in bbox with FULL 14-char ID
            # Construct ID from: code_commune (5) + prefixe (3) + section (2) + numero (4 with padding) = 14 chars
            # Filter out large cadastral sections (> 10,000 m² = 1 hectare) - these are divisions, not individual parcels
            parcelles_query = """
                SELECT 
                    CONCAT(
                        COALESCE(p.code_commune, ''),
                        COALESCE(p.prefixe, '000'),
                        COALESCE(p.section, ''),
                        LPAD(COALESCE(p.numero, ''), 4, '0')
                    ) as full_id_parcelle,
                    ST_AsText(p.geometry) as geom_wkt,
                    ST_AsGeoJSON(p.geometry) as geom_json,
                    ST_Area(p.geometry) as surface_m2
                FROM parcelles p
                WHERE p.code_commune LIKE '35%'
                  AND ST_Intersects(
                      p.geometry,
                      ST_MakeEnvelope(?, ?, ?, ?)
                  )
                  AND ST_Area(p.geometry) < 10000  -- Exclude large sections (> 1 hectare)
                  AND ST_Area(p.geometry) > 10     -- Exclude micro-parcels (< 10 m²)
                LIMIT ?
            """

            parcelles_results = conn.execute(parcelles_query, [min_x_l93, min_y_l93, max_x_l93, max_y_l93, limit]).fetchall()
            print(f"DEBUG: get_parcelles_geojson found {len(parcelles_results)} parcels")

            # Step 2: Get transactions in same bbox (WGS84 coordinates)
            transactions_query = """
                SELECT 
                    id_mutation,
                    longitude,
                    latitude
                FROM france_foncier_test
                WHERE longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
                  AND longitude IS NOT NULL
                  AND latitude IS NOT NULL
            """

            transactions_results = conn.execute(transactions_query, [min_x, max_x, min_y, max_y]).fetchall()
            print(f"DEBUG: Found {len(transactions_results)} transactions in bbox for spatial join")

        except Exception as e:
            print(f"ERROR: get_parcelles_geojson failed: {e}")
            import traceback
            traceback.print_exc()
            return '{"type": "FeatureCollection", "features": []}'

        # Step 3: SQL-based spatial join using DuckDB (FAST!)
        # Count transactions per parcel using ST_Contains in DuckDB
        try:
            count_query = """
                WITH tx_points AS (
                    SELECT 
                        id_mutation,
                        ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:2154') as geom_l93
                    FROM france_foncier_test
                    WHERE longitude BETWEEN ? AND ?
                      AND latitude BETWEEN ? AND ?
                      AND longitude IS NOT NULL
                      AND latitude IS NOT NULL
                ),
                parcel_bounds AS (
                    SELECT 
                        p.id_parcelle,
                        p.geometry
                    FROM parcelles p
                    WHERE p.code_commune LIKE '35%'
                      AND ST_Intersects(
                          p.geometry,
                          ST_MakeEnvelope(?, ?, ?, ?)
                      )
                      AND ST_Area(p.geometry) < 10000  -- Exclude large sections
                      AND ST_Area(p.geometry) > 10     -- Exclude micro-parcels
                    LIMIT ?
                )
                SELECT 
                    pb.id_parcelle,
                    COUNT(tx.id_mutation) as transaction_count
                FROM parcel_bounds pb
                LEFT JOIN tx_points tx ON ST_Contains(pb.geometry, tx.geom_l93)
                GROUP BY pb.id_parcelle
            """

            tx_counts_results = conn.execute(count_query, [
                min_x, max_x, min_y, max_y,  # Transaction bbox (WGS84)
                min_x_l93, min_y_l93, max_x_l93, max_y_l93,  # Parcel bbox (Lambert-93)
                limit
            ]).fetchall()

            # Build transaction count map
            transaction_counts = {row[0]: row[1] for row in tx_counts_results}
            print(f"DEBUG: Transaction counts computed for {len(transaction_counts)} parcels via SQL")

        except Exception as e:
            print(f"ERROR: SQL spatial join failed: {e}")
            import traceback
            traceback.print_exc()
            transaction_counts = {}



        features = []
        seen_ids = set()

        # Create reverse transformer: Lambert-93 -> WGS84 for output
        transformer_output = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)

        for r in parcelles_results:  # Use parcelles_results instead of undefined 'results'
            parcel_id = r[0]
            geom_wkt_str = r[1]
            geom_json_l93 = r[2]  # Geometry in Lambert-93

            if parcel_id in seen_ids:
                continue
            seen_ids.add(parcel_id)

            if not geom_json_l93:
                continue

            # Parse Lambert-93 geometry and transform to WGS84
            import json
            geom_l93 = json.loads(geom_json_l93)

            # Transform coordinates from Lambert-93 to WGS84
            if geom_l93['type'] == 'Polygon':
                # Polygon has array of rings (outer + holes)
                transformed_coords = []
                for ring in geom_l93['coordinates']:
                    transformed_ring = [
                        list(transformer_output.transform(x, y))
                        for x, y in ring
                    ]
                    transformed_coords.append(transformed_ring)
                geom_wgs84 = {
                    'type': 'Polygon',
                    'coordinates': transformed_coords
                }
            elif geom_l93['type'] == 'MultiPolygon':
                # MultiPolygon has array of polygons
                transformed_coords = []
                for polygon in geom_l93['coordinates']:
                    transformed_polygon = []
                    for ring in polygon:
                        transformed_ring = [
                            list(transformer_output.transform(x, y))
                            for x, y in ring
                        ]
                        transformed_polygon.append(transformed_ring)
                    transformed_coords.append(transformed_polygon)
                geom_wgs84 = {
                    'type': 'MultiPolygon',
                    'coordinates': transformed_coords
                }
            else:
                # Fallback: keep original (shouldn't happen)
                geom_wgs84 = geom_l93

            # Build properties for parcel
            tx_count = transaction_counts.get(parcel_id, 0)
            props = [
                f'"id_parcelle": "{parcel_id}"',
                f'"transaction_count": {tx_count}'
            ]
            props_str = ", ".join(props)

            # Create Polygon feature with WGS84 coordinates
            geom_json_wgs84 = json.dumps(geom_wgs84)
            features.append(
                f'{{"type": "Feature", "properties": {{{props_str}}}, "geometry": {geom_json_wgs84}}}'
            )

        return '{"type": "FeatureCollection", "features": [' + ",".join(features) + ']}'

    async def get_parcelles_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """DEPRECATED: Use get_parcelles_geojson() instead.
        
        This method is kept for backward compatibility but will be removed.
        It incorrectly mixes DVF transactions with parcel geometries.
        """
        print("WARNING: get_parcelles_in_bbox is deprecated. Use get_parcelles_geojson() instead.")
        return await self.get_parcelles_geojson(min_x, min_y, max_x, max_y, limit)


    async def get_transactions_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions for a commune.
        
        Uses mutations_aggregated and UNNESTs parcelles to simulate transaction rows.
        """
        conn = self._get_connection()
        query = """
            SELECT m.id_mutation, m.date_mutation, m.nature_mutation, m.valeur_fonciere,
                   m.code_commune, unnest(m.parcelles) as id_parcelle, 
                   NULL as type_local, 
                   m.surface_habitable_totale as surface_reelle_bati, 
                   m.nombre_locaux as nombre_pieces
            FROM mutations_aggregated m
            WHERE m.code_commune = ?
        """
        params: list = [code_commune]

        if date_from:
            query += " AND m.date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND m.date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        transactions = []
        for r in results:
             # Parse date if string
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            transactions.append(Transaction(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=None, # Not available in aggregated
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8] if r[8] else 0,
            ))
        return transactions

    async def get_transactions_for_parcel(self, id_parcelle: str, limit: int = 100) -> list[MutationAggregate]:
        """Retrieve DVF transactions that include a specific parcel.
        
        Searches mutations_aggregated where the parcel ID is in the parcelles array.
        Also falls back to france_foncier_test for direct coordinate-based queries.
        
        Note: For single-parcel queries, the limit is set high (100) because a typical
        parcel has only 1-3 sales over the DVF period (2014-2025). The limit is mainly
        a safety net for edge cases (e.g., commercial properties).
        
        Args:
            id_parcelle: 14-character cadastral parcel ID
            limit: Max transactions to return (default 100)
            
        Returns:
            List of MutationAggregate objects for transactions on this parcel
        """
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))

        # Query mutations where this parcel is referenced
        query = f"""
            SELECT 
                id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                code_commune, parcelles, surface_habitable_totale, nombre_locaux,
                prix_m2, longitude, latitude
            FROM mutations_aggregated
            WHERE list_contains(parcelles, ?)
            ORDER BY date_mutation DESC
            LIMIT {limit}
        """

        try:
            results = conn.execute(query, [id_parcelle]).fetchall()
        except Exception:
            # Fallback: try UNNEST approach
            query_fallback = f"""
                SELECT 
                    m.id_mutation, m.date_mutation, m.nature_mutation, m.valeur_fonciere,
                    m.code_commune, m.parcelles, m.surface_habitable_totale, m.nombre_locaux,
                    m.prix_m2, m.longitude, m.latitude
                FROM mutations_aggregated m
                WHERE EXISTS (
                    SELECT 1 FROM UNNEST(m.parcelles) as t(p) WHERE t.p = ?
                )
                ORDER BY m.date_mutation DESC
                LIMIT {limit}
            """
            results = conn.execute(query_fallback, [id_parcelle]).fetchall()

        mutations = []
        for r in results:
            # Parse date if string
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            mutations.append(MutationAggregate(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation(r[2]) if r[2] else NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])) if r[3] else Decimal("0"),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])) if r[6] else Decimal("0"),
                nombre_locaux=r[7] if r[7] else 0,
                longitude=r[9] if len(r) > 9 else None,
                latitude=r[10] if len(r) > 10 else None,
            ))

        return mutations


    async def get_mutations_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Retrieve aggregated mutations (pre-computed by ETL)."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        query = """
            SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                   code_commune, parcelles, surface_habitable_totale, nombre_locaux
            FROM mutations_aggregated
            WHERE code_commune = ?
        """
        params: list = [code_commune]

        if date_from:
            query += " AND date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        return [
            MutationAggregate(
                id_mutation=r[0],
                date_mutation=r[1] if not isinstance(r[1], str) else datetime.strptime(r[1], "%Y-%m-%d").date(),
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                parcelles=r[5],  # Already a list from DuckDB
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
            )
            for r in results
        ]

    async def get_transactions_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions within a bounding box.
        
        Uses mutations_aggregated joined with parcelles (spatially).
        """
        conn = self._get_connection()
        query = """
            SELECT m.id_mutation, m.date_mutation, m.nature_mutation, m.valeur_fonciere,
                   m.code_commune, p.id_parcelle, 
                   NULL as type_local,
                   m.surface_habitable_totale, 
                   m.nombre_locaux
            FROM mutations_aggregated m
            CROSS JOIN UNNEST(m.parcelles) as t(pid)
            JOIN parcelles p ON t.pid = p.id_parcelle
            WHERE ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
        """
        params: list = [min_x, min_y, max_x, max_y]

        if date_from:
            query += " AND m.date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND m.date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        transactions = []
        for r in results:
             # Parse date if string
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            transactions.append(Transaction(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=None,
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8] if r[8] else 0,
            ))
        return transactions

    async def get_price_stats(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Decimal]:
        """Get price statistics for a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        query = """
            SELECT
                MIN(valeur_fonciere / surface_habitable_totale) as min_price,
                MAX(valeur_fonciere / surface_habitable_totale) as max_price,
                MEDIAN(valeur_fonciere / surface_habitable_totale) as median_price,
                AVG(valeur_fonciere / surface_habitable_totale) as avg_price
            FROM mutations_aggregated
            WHERE code_commune = ?
              AND surface_habitable_totale > 0
        """
        params: list = [code_commune]

        if date_from:
            query += " AND date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date_mutation <= ?"
            params.append(date_to)

        result = conn.execute(query, params).fetchone()

        return {
            "min_price_m2": Decimal(str(result[0])) if result[0] else Decimal("0"),
            "max_price_m2": Decimal(str(result[1])) if result[1] else Decimal("0"),
            "median_price_m2": Decimal(str(result[2])) if result[2] else Decimal("0"),
            "avg_price_m2": Decimal(str(result[3])) if result[3] else Decimal("0"),
        }

    async def get_mutations_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[MutationAggregate]:
        """Retrieve mutations within a radius using optimized Haversine.

        Strategy:
        1. Pre-filter with bounding box for performance (uses index)
        2. Apply precise Haversine formula for accurate distance
        3. Order by distance ascending
        """
        conn = self._get_connection()

        # Calculate approximate bounding box (1 degree ≈ 111km at equator)
        # Add margin for latitude variation
        lat_delta = radius_meters / 111000  # degrees latitude
        lon_delta = radius_meters / (111000 * abs(cos(radians(lat))))  # degrees longitude

        # Haversine formula in SQL
        # Distance = 6371000 * acos(cos(lat1)*cos(lat2)*cos(lon2-lon1) + sin(lat1)*sin(lat2))
        query = """
            WITH bbox_filtered AS (
                SELECT *
                FROM mutations_aggregated
                WHERE longitude IS NOT NULL
                  AND latitude IS NOT NULL
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
            ),
            with_distance AS (
                SELECT *,
                    6371000 * ACOS(
                        LEAST(1.0, GREATEST(-1.0,
                            COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS(?)) +
                            SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                        ))
                    ) AS distance_meters
                FROM bbox_filtered
            )
            SELECT
                id_mutation,
                date_mutation,
                nature_mutation,
                valeur_fonciere,
                code_commune,
                parcelles,
                surface_habitable_totale,
                nombre_locaux,
                prix_m2,
                longitude,
                latitude,
                distance_meters
            FROM with_distance
            WHERE distance_meters <= ?
        """

        params: list = [
            lon - lon_delta, lon + lon_delta,  # lon bounds
            lat - lat_delta, lat + lat_delta,  # lat bounds
            lat, lon, lat,  # for Haversine
            radius_meters,  # distance filter
        ]

        # Add date filters
        if date_from:
            query = query.replace(
                "WHERE distance_meters",
                f"WHERE date_mutation >= '{date_from}' AND distance_meters"
            )
        if date_to:
            query = query.replace(
                "WHERE distance_meters",
                f"WHERE date_mutation <= '{date_to}' AND distance_meters"
            )

        query += f" ORDER BY distance_meters ASC LIMIT {limit}"

        results = conn.execute(query, params).fetchall()

        # Convert to domain models
        mutations = []
        for r in results:
            # Parse date if string
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            mutations.append(MutationAggregate(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation("Vente"),  # All filtered are Vente
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
                longitude=r[9],
                latitude=r[10],
            ))

        return mutations

    async def get_enrichment_by_parcelle(self, id_parcelle: str) -> EnrichmentScore | None:
        """Retrieve enrichment score for a parcel."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        result = conn.execute(
            """
            SELECT id_parcelle, schools_score, transport_score,
                   nuisances_score, green_spaces_score
            FROM enrichment_scores
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return EnrichmentScore(
            id_parcelle=result[0],
            schools_score=Decimal(str(result[1])),
            transport_score=Decimal(str(result[2])),
            nuisances_score=Decimal(str(result[3])),
            green_spaces_score=Decimal(str(result[4])),
        )

    async def get_enrichments_by_commune(self, code_commune: str) -> list[EnrichmentScore]:
        """Retrieve all enrichment scores for a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT e.id_parcelle, e.schools_score, e.transport_score,
                   e.nuisances_score, e.green_spaces_score
            FROM enrichment_scores e
            JOIN parcelles p ON e.id_parcelle = p.id_parcelle
            WHERE p.code_commune = ?
            """,
            [code_commune],
        ).fetchall()

        return [
            EnrichmentScore(
                id_parcelle=r[0],
                schools_score=Decimal(str(r[1])),
                transport_score=Decimal(str(r[2])),
                nuisances_score=Decimal(str(r[3])),
                green_spaces_score=Decimal(str(r[4])),
            )
            for r in results
        ]

    def find_parcelle_with_spatial_fallback(
        self,
        id_parcelle_dvf: str,
        longitude: float,
        latitude: float,
        buffer_meters: float = -2.0,
    ) -> str | None:
        """Find parcel by ID, fallback to spatial intersection with negative buffer.
        
        Args:
            id_parcelle_dvf: Parcel ID from DVF (may be incorrect)
            longitude: WGS84 longitude
            latitude: WGS84 latitude
            buffer_meters: Negative buffer in meters (default: -2m)
            
        Returns:
            Corrected parcel ID or None
        """
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle_dvf))

        # Step 1: Direct ID lookup
        try:
            result = conn.execute(
                "SELECT id_parcelle FROM parcelles WHERE id_parcelle = ? LIMIT 1",
                [id_parcelle_dvf],
            ).fetchone()
            if result:
                return result[0]
        except Exception as e:
            logger.warning(f"Direct lookup failed for {id_parcelle_dvf}: {e}")

        # Step 2: Spatial intersection
        logger.info(f"Parcelle {id_parcelle_dvf} not found, spatial fallback")
        buffer_degrees = buffer_meters / 111000

        query = """
            SELECT p.id_parcelle,
                ST_Distance(
                    ST_Transform(p.geometry, 'EPSG:2154', 'EPSG:4326'),
                    ST_Point(?, ?)
                ) * 111000 as distance_meters
            FROM parcelles p
            WHERE ST_Intersects(
                ST_Buffer(
                    ST_Transform(p.geometry, 'EPSG:2154', 'EPSG:4326'),
                    ?
                ),
                ST_Point(?, ?)
            )
            ORDER BY distance_meters LIMIT 1
        """

        try:
            result = conn.execute(
                query, [longitude, latitude, buffer_degrees, longitude, latitude]
            ).fetchone()
            if result:
                logger.info(f"Spatial fix: {id_parcelle_dvf} → {result[0]} ({result[1]:.2f}m)")
                return result[0]
        except Exception as e:
            logger.error(f"Spatial fallback failed: {e}")

        return None

    async def get_parcelle_fiche(self, id_parcelle: str) -> dict | None:
        """Fiche parcelle complète : DVF + BDNB + densification + confiance.

        Single query joining all data sources for maximum API efficiency.
        Returns a flat dict ready for JSON serialization.
        """
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))

        result = conn.execute("""
            WITH transactions AS (
                SELECT
                    cadastre_parcelle_id,
                    COUNT(*) AS nb_transactions,
                    MAX(date_mutation) AS derniere_mutation,
                    MIN(date_mutation) AS premiere_mutation,
                    MAX(valeur_fonciere) AS derniere_valeur,
                    MAX(prix_m2) AS dernier_prix_m2,
                    MAX(surface_habitable_totale) AS surface_habitable,
                    MAX(dpe_energie) AS dpe_energie,
                    MAX(annee_construction) AS annee_construction,
                    MAX(hauteur_moyenne) AS hauteur_moyenne,
                    MAX(nb_niveau) AS nb_niveau,
                    MAX(type_usage) AS type_usage,
                    MAX(nb_log) AS nb_log
                FROM france_foncier_test
                WHERE cadastre_parcelle_id = ?
                GROUP BY cadastre_parcelle_id
            )
            SELECT
                t.cadastre_parcelle_id   AS id_parcelle,
                t.nb_transactions,
                t.derniere_mutation,
                t.premiere_mutation,
                t.derniere_valeur,
                t.dernier_prix_m2,
                t.surface_habitable,

                -- BDNB
                t.dpe_energie,
                t.annee_construction,
                t.hauteur_moyenne,
                t.nb_niveau,
                t.type_usage,
                t.nb_log,

                -- Densification
                d.surface_parcelle_m2,
                d.surface_plancher_m2,
                d.emprise_sol_m2,
                d.ces_actuel,
                d.ces_potentiel,
                d.potentiel_densification,
                d.surface_constructible_restante,
                d.categorie          AS categorie_densification,
                d.source_ces,

                -- Confiance
                c.confidence_global,
                c.confidence_label,
                c.score_bdnb,
                c.score_dvf,
                c.score_densification,
                c.score_fraicheur

            FROM transactions t
            LEFT JOIN densification_scores d
                ON t.cadastre_parcelle_id = d.id_parcelle
            LEFT JOIN confidence_scores c
                ON t.cadastre_parcelle_id = c.id_parcelle
        """, [id_parcelle]).fetchone()

        if result is None:
            return None

        cols = [
            "id_parcelle", "nb_transactions", "derniere_mutation",
            "premiere_mutation", "derniere_valeur", "dernier_prix_m2",
            "surface_habitable",
            "dpe_energie", "annee_construction", "hauteur_moyenne",
            "nb_niveau", "type_usage", "nb_log",
            "surface_parcelle_m2", "surface_plancher_m2", "emprise_sol_m2",
            "ces_actuel", "ces_potentiel", "potentiel_densification",
            "surface_constructible_restante", "categorie_densification",
            "source_ces",
            "confidence_global", "confidence_label", "score_bdnb",
            "score_dvf", "score_densification", "score_fraicheur",
        ]

        fiche = {}
        for col, val in zip(cols, result):
            if isinstance(val, Decimal):
                fiche[col] = float(val)
            elif val is None:
                fiche[col] = None
            else:
                fiche[col] = val

        # Round floats for cleaner API output
        for key in ["derniere_valeur", "dernier_prix_m2", "surface_habitable",
                     "surface_parcelle_m2", "surface_plancher_m2", "emprise_sol_m2",
                     "ces_actuel", "ces_potentiel", "potentiel_densification",
                     "surface_constructible_restante",
                     "confidence_global", "score_bdnb", "score_dvf",
                     "score_densification", "score_fraicheur"]:
            if fiche.get(key) is not None:
                fiche[key] = round(float(fiche[key]), 4)

        # Warning if confidence is low
        conf = fiche.get("confidence_global")
        if conf is not None and conf < 0.55:
            fiche["warning"] = "Données partielles — fiabilité limitée pour cette parcelle"

        return fiche

    async def get_densification_score(self, id_parcelle: str) -> DensificationScore | None:
        """Retrieve densification score for a single parcel.
        
        Args:
            id_parcelle: 14-character parcel ID
            
        Returns:
            DensificationScore or None if not found
        """
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        result = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return DensificationScore(
            id_parcelle=result[0],
            surface_parcelle_m2=Decimal(str(result[1])),
            surface_plancher_m2=Decimal(str(result[2])),
            ces_actuel=Decimal(str(result[3])),
            ces_potentiel=Decimal(str(result[4])),
        )

    async def get_densification_scores_by_commune(
        self, code_commune: str
    ) -> list[DensificationScore]:
        """Retrieve all densification scores for a commune.
        
        Args:
            code_commune: 5-character commune code
            
        Returns:
            List of DensificationScore objects
        """
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE code_commune = ?
            ORDER BY potentiel_densification DESC
            """,
            [code_commune],
        ).fetchall()

        return [
            DensificationScore(
                id_parcelle=r[0],
                surface_parcelle_m2=Decimal(str(r[1])),
                surface_plancher_m2=Decimal(str(r[2])),
                ces_actuel=Decimal(str(r[3])),
                ces_potentiel=Decimal(str(r[4])),
            )
            for r in results
        ]

    async def get_top_densification_opportunities(
        self, code_commune: str, limit: int = 20
    ) -> list[DensificationScore]:
        """Retrieve top densification opportunities for a commune.
        
        Returns parcels with FORT potential (≥20% margin) sorted by
        surface_constructible_restante descending.
        
        Args:
            code_commune: 5-character commune code
            limit: Maximum number of results (default 20)
            
        Returns:
            List of DensificationScore objects with highest potential
        """
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE code_commune = ?
              AND categorie = 'FORT'
            ORDER BY surface_constructible_restante DESC
            LIMIT ?
            """,
            [code_commune, limit],
        ).fetchall()

        return [
            DensificationScore(
                id_parcelle=r[0],
                surface_parcelle_m2=Decimal(str(r[1])),
                surface_plancher_m2=Decimal(str(r[2])),
                ces_actuel=Decimal(str(r[3])),
                ces_potentiel=Decimal(str(r[4])),
            )
            for r in results
        ]

    async def search_parcelles(
        self,
        code_commune: str | None = None,
        categorie: str | None = None,
        confidence_min: float = 0.0,
        prix_m2_max: float | None = None,
        surface_min: float | None = None,
        annee_min: int | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Multi-criteria parcel search joining DVF, densification and confidence.

        Returns a list of flat dicts ready for JSON/CSV serialization.
        """
        conn = self._get_connection(self._dept_from_commune(code_commune))

        clauses = ["1=1"]
        params: list = []

        if code_commune:
            clauses.append("f.code_commune = ?")
            params.append(code_commune)
        if categorie:
            clauses.append("d.categorie = ?")
            params.append(categorie.upper())
        if confidence_min > 0:
            clauses.append("c.confidence_global >= ?")
            params.append(confidence_min)
        if prix_m2_max is not None:
            clauses.append("f.prix_m2 <= ?")
            params.append(prix_m2_max)
        if surface_min is not None:
            clauses.append("d.surface_parcelle_m2 >= ?")
            params.append(surface_min)
        if annee_min is not None:
            clauses.append("YEAR(f.date_mutation) >= ?")
            params.append(annee_min)

        where = " AND ".join(clauses)

        query = f"""
            SELECT
                f.cadastre_parcelle_id   AS id_parcelle,
                f.code_commune,
                f.valeur_fonciere,
                f.prix_m2,
                d.surface_parcelle_m2,
                f.date_mutation,
                d.categorie,
                d.potentiel_densification,
                d.surface_constructible_restante,
                d.source_ces,
                c.confidence_global,
                c.confidence_label
            FROM france_foncier_test f
            LEFT JOIN densification_scores d
                ON f.cadastre_parcelle_id = d.id_parcelle
            LEFT JOIN confidence_scores c
                ON f.cadastre_parcelle_id = c.id_parcelle
            WHERE {where}
            ORDER BY d.potentiel_densification DESC NULLS LAST
            LIMIT ?
        """
        params.append(limit)

        results = conn.execute(query, params).fetchall()
        cols = [
            "id_parcelle", "code_commune", "valeur_fonciere", "prix_m2",
            "surface_parcelle_m2", "date_mutation", "categorie",
            "potentiel_densification", "surface_constructible_restante",
            "source_ces", "confidence_global", "confidence_label",
        ]

        rows = []
        for row in results:
            d = {}
            for col, val in zip(cols, row):
                if isinstance(val, Decimal):
                    d[col] = float(val)
                else:
                    d[col] = val
            rows.append(d)
        return rows

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
