"""POI/Enrichment Repository implementation.

Segregated from DVF for SOLID compliance.
"""

from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb

from app.domain.models import EnrichmentScore
from app.repositories.interfaces import IEnrichmentRepository


class PoiRepository(IEnrichmentRepository):
    """DuckDB implementation for POI and enrichment data.

    Handles POI queries and enrichment scores.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
        return self._conn

    async def get_enrichment_by_parcelle(self, id_parcelle: str) -> EnrichmentScore | None:
        """Retrieve enrichment score for a parcel."""
        conn = self._get_connection()
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
        conn = self._get_connection()
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

    async def get_poi_count_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        type_poi: str | None = None,
    ) -> int:
        """Count POI within a radius."""
        conn = self._get_connection()

        lat_delta = radius_meters / 111000
        lon_delta = radius_meters / (111000 * abs(cos(radians(lat))))

        query = """
            SELECT COUNT(*)
            FROM points_interet
            WHERE longitude BETWEEN ? AND ?
              AND latitude BETWEEN ? AND ?
        """
        params = [
            lon - lon_delta, lon + lon_delta,
            lat - lat_delta, lat + lat_delta,
        ]

        if type_poi:
            query += " AND type_poi = ?"
            params.append(type_poi)

        result = conn.execute(query, params).fetchone()
        return result[0] if result else 0

    async def get_nearest_poi(
        self,
        lat: float,
        lon: float,
        type_poi: str,
        max_distance_m: int = 5000,
    ) -> dict | None:
        """Get nearest POI of a specific type with distance."""
        conn = self._get_connection()

        lat_delta = max_distance_m / 111000
        lon_delta = max_distance_m / (111000 * abs(cos(radians(lat))))

        result = conn.execute("""
            WITH poi_dist AS (
                SELECT
                    id, nom, sous_type, longitude, latitude,
                    6371000 * ACOS(
                        LEAST(1.0, GREATEST(-1.0,
                            COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS(?)) +
                            SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                        ))
                    ) AS distance_m
                FROM points_interet
                WHERE type_poi = ?
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
            )
            SELECT id, nom, sous_type, longitude, latitude, distance_m
            FROM poi_dist
            ORDER BY distance_m ASC
            LIMIT 1
        """, [
            lat, lon, lat,
            type_poi,
            lon - lon_delta, lon + lon_delta,
            lat - lat_delta, lat + lat_delta,
        ]).fetchone()

        if not result:
            return None

        return {
            "id": result[0],
            "nom": result[1],
            "sous_type": result[2],
            "longitude": result[3],
            "latitude": result[4],
            "distance_m": result[5],
        }

    async def get_poi_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        type_poi: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get POI within a radius with distances."""
        conn = self._get_connection()

        lat_delta = radius_meters / 111000
        lon_delta = radius_meters / (111000 * abs(cos(radians(lat))))

        query = """
            WITH poi_dist AS (
                SELECT
                    id, nom, type_poi, sous_type, longitude, latitude,
                    6371000 * ACOS(
                        LEAST(1.0, GREATEST(-1.0,
                            COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                            COS(RADIANS(longitude) - RADIANS(?)) +
                            SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                        ))
                    ) AS distance_m
                FROM points_interet
                WHERE longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
        """
        params = [
            lat, lon, lat,
            lon - lon_delta, lon + lon_delta,
            lat - lat_delta, lat + lat_delta,
        ]

        if type_poi:
            query += " AND type_poi = ?"
            params.append(type_poi)

        query += f"""
            )
            SELECT id, nom, type_poi, sous_type, longitude, latitude, distance_m
            FROM poi_dist
            WHERE distance_m <= {radius_meters}
            ORDER BY distance_m ASC
            LIMIT {limit}
        """

        results = conn.execute(query, params).fetchall()

        return [
            {
                "id": r[0],
                "nom": r[1],
                "type_poi": r[2],
                "sous_type": r[3],
                "longitude": r[4],
                "latitude": r[5],
                "distance_m": r[6],
            }
            for r in results
        ]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
