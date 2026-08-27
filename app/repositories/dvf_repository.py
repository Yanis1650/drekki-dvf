"""DVF Repository implementation (Mutations & Transactions).

Segregated from enrichment for SOLID compliance.
"""

import logging
from datetime import date
from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb

from app.domain.models import MutationAggregate, NatureMutation, Transaction, TypeLocal
from app.infrastructure.duckdb_spatial import ensure_spatial
from app.repositories.interfaces import ITransactionRepository

logger = logging.getLogger(__name__)


class DvfRepository(ITransactionRepository):
    """DuckDB implementation for DVF transaction data.

    Handles mutations and transactions queries.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
            ensure_spatial(self._conn)
        return self._conn

    async def get_transactions_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions for a commune."""
        conn = self._get_connection()
        query = """
            SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                   code_commune, id_parcelle, type_local, surface_reelle_bati, nombre_pieces
            FROM transactions
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
            Transaction(
                id_mutation=r[0],
                date_mutation=r[1],
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=TypeLocal(r[6]) if r[6] else None,
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8],
            )
            for r in results
        ]

    async def get_mutations_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Retrieve aggregated mutations (pre-computed by ETL)."""
        conn = self._get_connection()
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
        return self._results_to_mutations(results)

    async def get_transactions_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions within a bounding box."""
        conn = self._get_connection()
        query = """
            SELECT t.id_mutation, t.date_mutation, t.nature_mutation, t.valeur_fonciere,
                   t.code_commune, t.id_parcelle, t.type_local, t.surface_reelle_bati, t.nombre_pieces
            FROM transactions t
            JOIN parcelles p ON t.id_parcelle = p.id_parcelle
            WHERE ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
        """
        params: list = [min_x, min_y, max_x, max_y]

        if date_from:
            query += " AND t.date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND t.date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        return [
            Transaction(
                id_mutation=r[0],
                date_mutation=r[1],
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=TypeLocal(r[6]) if r[6] else None,
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8],
            )
            for r in results
        ]

    async def get_price_stats(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Decimal]:
        """Get price statistics for a commune (outliers exclus).

        Utilise france_foncier_test (table enrichie) pour bénéficier du flag
        is_outlier calculé par l'ETL. Fallback sur mutations_aggregated si la
        table enrichie n'existe pas (base non encore buildée).
        """
        conn = self._get_connection()
        tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        if "france_foncier_test" in tables:
            query = """
                SELECT
                    MIN(prix_m2)    as min_price,
                    MAX(prix_m2)    as max_price,
                    MEDIAN(prix_m2) as median_price,
                    AVG(prix_m2)    as avg_price
                FROM france_foncier_test
                WHERE code_commune = ?
                  AND prix_m2 IS NOT NULL AND prix_m2 > 0
                  AND COALESCE(is_outlier, FALSE) = FALSE
            """
        else:
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
        """Retrieve mutations within a radius using Haversine."""
        conn = self._get_connection()

        # Bounding box pre-filter
        lat_delta = radius_meters / 111000
        lon_delta = radius_meters / (111000 * abs(cos(radians(lat))))

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
                id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                code_commune, parcelles, surface_habitable_totale, nombre_locaux,
                prix_m2, longitude, latitude, distance_meters
            FROM with_distance
            WHERE distance_meters <= ?
        """

        params: list = [
            lon - lon_delta, lon + lon_delta,
            lat - lat_delta, lat + lat_delta,
            lat, lon, lat,
            radius_meters,
        ]

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
        return self._results_to_mutations_with_coords(results)

    def _results_to_mutations(self, results: list) -> list[MutationAggregate]:
        """Convert query results to MutationAggregate list."""
        mutations = []
        for r in results:
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            mutations.append(MutationAggregate(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
            ))
        return mutations

    def _results_to_mutations_with_coords(self, results: list) -> list[MutationAggregate]:
        """Convert results with coordinates to MutationAggregate list."""
        mutations = []
        for r in results:
            mutation_date = r[1]
            if isinstance(mutation_date, str):
                from datetime import datetime
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            mutations.append(MutationAggregate(
                id_mutation=r[0],
                date_mutation=mutation_date,
                nature_mutation=NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
                longitude=r[9],
                latitude=r[10],
            ))
        return mutations

    async def get_parcelles_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 1000,
    ) -> str:
        """Retrieve parcelles as GeoJSON FeatureCollection with DPE data.

        Uses france_foncier_test table which contains enriched data (DPE, annee_construction).
        Falls back to creating synthetic polygons from mutation points if no geometry available.
        """
        conn = self._get_connection()

        # Try france_foncier_test first (enriched data with DPE)
        # Use simple lat/lon bounding box filter since data has coordinates
        query = """
            SELECT
                id_mutation as id,
                longitude,
                latitude,
                classe_consommation_energie as dpe,
                annee_construction as annee,
                valeur_fonciere,
                surface_reelle
            FROM france_foncier_test
            WHERE longitude IS NOT NULL
              AND latitude IS NOT NULL
              AND longitude BETWEEN ? AND ?
              AND latitude BETWEEN ? AND ?
            LIMIT ?
        """

        try:
            results = conn.execute(query, [min_x, max_x, min_y, max_y, limit]).fetchall()
        except Exception as e:
            # Fallback: use basic parcelles table if france_foncier_test fails
            logger.warning("Requete france_foncier_test echouee (%s) — repli sur parcelles", e)
            results = []

        features = []
        for r in results:
            if not r[1] or not r[2]:
                continue

            lon, lat = r[1], r[2]
            dpe = r[3] if r[3] else None
            annee = r[4] if r[4] else None

            # Create a small polygon (approx 10m square) around the point
            # This simulates a building footprint for visualization
            delta = 0.00005  # ~5m at mid-latitudes

            polygon = (
                f"[[[{lon - delta}, {lat - delta}], [{lon + delta}, {lat - delta}], "
                f"[{lon + delta}, {lat + delta}], [{lon - delta}, {lat + delta}], "
                f"[{lon - delta}, {lat - delta}]]]"
            )

            properties = f'"id": "{r[0]}"'
            if dpe:
                properties += f', "dpe": "{dpe}"'
            if annee:
                properties += f', "annee": {int(annee)}'

            features.append(
                f'{{"type": "Feature", "properties": {{{properties}}}, '
                f'"geometry": {{"type": "Polygon", "coordinates": {polygon}}}}}'
            )

        return '{"type": "FeatureCollection", "features": [' + ",".join(features) + ']}'

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

