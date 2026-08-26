"""Proximity Scorer - Calculates distances to POI.

Handles spatial queries for POI proximity.
"""

import logging
from dataclasses import dataclass
from math import cos, radians
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


@dataclass
class ProximityResult:
    """Result of proximity calculation."""
    category: str
    nearest_distance_m: float | None
    count_500m: int
    count_1km: int
    count_2km: int
    poi_types: list[str]


class ProximityScorer:
    """Calculates proximity to POI using DuckDB spatial queries."""

    def __init__(self, duckdb_path: Path | str = "./data/foncier.duckdb") -> None:
        self._duckdb_path = Path(duckdb_path)

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get read-only DuckDB connection."""
        return duckdb.connect(str(self._duckdb_path), read_only=True)

    def calculate_proximity(
        self,
        latitude: float,
        longitude: float,
        category: str,
    ) -> ProximityResult:
        """Calculate proximity metrics for a point to POI of a category.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude
            category: POI category (education, transport, commerce, environnement)

        Returns:
            ProximityResult with distances and counts
        """
        conn = self._get_connection()

        try:
            # Calculate bounding box for 2km
            lat_delta = 2000 / 111000
            lon_delta = 2000 / (111000 * abs(cos(radians(latitude))))

            # Query POI with distances
            result = conn.execute("""
                WITH poi_distances AS (
                    SELECT 
                        id,
                        nom,
                        sous_type,
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
                SELECT 
                    MIN(distance_m) as nearest,
                    SUM(CASE WHEN distance_m <= 500 THEN 1 ELSE 0 END) as count_500m,
                    SUM(CASE WHEN distance_m <= 1000 THEN 1 ELSE 0 END) as count_1km,
                    SUM(CASE WHEN distance_m <= 2000 THEN 1 ELSE 0 END) as count_2km
                FROM poi_distances
            """, [
                latitude, longitude, latitude,
                category,
                longitude - lon_delta, longitude + lon_delta,
                latitude - lat_delta, latitude + lat_delta,
            ]).fetchone()

            # Get POI types present
            types_result = conn.execute("""
                SELECT DISTINCT sous_type
                FROM points_interet
                WHERE type_poi = ?
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
            """, [
                category,
                longitude - lon_delta, longitude + lon_delta,
                latitude - lat_delta, latitude + lat_delta,
            ]).fetchall()

            return ProximityResult(
                category=category,
                nearest_distance_m=result[0] if result[0] else None,
                count_500m=result[1] or 0,
                count_1km=result[2] or 0,
                count_2km=result[3] or 0,
                poi_types=[r[0] for r in types_result if r[0]],
            )

        except Exception as e:
            logger.debug(f"Proximity calculation failed: {e}")
            return ProximityResult(
                category=category,
                nearest_distance_m=None,
                count_500m=0,
                count_1km=0,
                count_2km=0,
                poi_types=[],
            )

        finally:
            conn.close()

    def calculate_all_proximities(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, ProximityResult]:
        """Calculate proximity for all POI categories.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude

        Returns:
            Dict mapping category to ProximityResult
        """
        categories = [
            "education", "transport", "transit",
            "commerce", "environnement", "nuisances",
        ]
        results = {}

        for category in categories:
            # Map category to type_poi in database
            type_poi = self._category_to_type_poi(category)
            results[category] = self.calculate_proximity(latitude, longitude, type_poi)

        return results

    def _category_to_type_poi(self, category: str) -> str:
        """Map category name to type_poi in database."""
        mapping = {
            "education": "ecole",
            "transport": "transport",
            "transit": "transit",
            "commerce": "commerce",
            "environnement": "environnement",
            "nuisances": "nuisance",
        }
        return mapping.get(category, category)
