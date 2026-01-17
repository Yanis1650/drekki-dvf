"""Education scorer implementation.

Calculates education score based on proximity to schools.
"""

from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb

from app.services.enrichment.base_scorer import IScorer


class EducationScorer(IScorer):
    """Scorer for education accessibility.

    Score calculation:
    - Count schools within 500m radius (weight: 2x)
    - Count schools within 1km radius (weight: 1x)
    - Bonus for school type diversity (maternelle, elementaire, college, lycee)

    Score scale:
    - 0: No schools within 1km
    - 5: Average accessibility (2-3 schools within 1km)
    - 10: Excellent accessibility (5+ schools within 500m)
    """

    def __init__(self, duckdb_path: Path | str = "./data/foncier.duckdb") -> None:
        self._duckdb_path = Path(duckdb_path)

    @property
    def name(self) -> str:
        return "education"

    @property
    def poi_type(self) -> str:
        return "ecole"

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get read-only DuckDB connection."""
        return duckdb.connect(str(self._duckdb_path), read_only=True)

    async def calculate_score(
        self,
        latitude: float,
        longitude: float,
    ) -> Decimal:
        """Calculate education score for a location."""
        details = await self.calculate_score_with_details(latitude, longitude)
        return details["score"]

    async def calculate_score_with_details(
        self,
        latitude: float,
        longitude: float,
    ) -> dict:
        """Calculate education score with detailed breakdown."""
        conn = self._get_connection()

        try:
            # Calculate bounding boxes for 500m and 1km
            lat_delta_500m = 500 / 111000
            lon_delta_500m = 500 / (111000 * abs(cos(radians(latitude))))
            lat_delta_1km = 1000 / 111000
            lon_delta_1km = 1000 / (111000 * abs(cos(radians(latitude))))

            # Query schools within 500m
            result_500m = conn.execute("""
                SELECT sous_type, COUNT(*) as count
                FROM points_interet
                WHERE type_poi = 'ecole'
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
                GROUP BY sous_type
            """, [
                longitude - lon_delta_500m, longitude + lon_delta_500m,
                latitude - lat_delta_500m, latitude + lat_delta_500m,
            ]).fetchall()

            # Query schools within 1km (excluding those in 500m)
            result_1km = conn.execute("""
                SELECT sous_type, COUNT(*) as count
                FROM points_interet
                WHERE type_poi = 'ecole'
                  AND longitude BETWEEN ? AND ?
                  AND latitude BETWEEN ? AND ?
                  AND NOT (
                      longitude BETWEEN ? AND ?
                      AND latitude BETWEEN ? AND ?
                  )
                GROUP BY sous_type
            """, [
                longitude - lon_delta_1km, longitude + lon_delta_1km,
                latitude - lat_delta_1km, latitude + lat_delta_1km,
                longitude - lon_delta_500m, longitude + lon_delta_500m,
                latitude - lat_delta_500m, latitude + lat_delta_500m,
            ]).fetchall()

            # Aggregate counts
            schools_500m = {r[0]: r[1] for r in result_500m}
            schools_1km = {r[0]: r[1] for r in result_1km}

            total_500m = sum(schools_500m.values())
            total_1km = sum(schools_1km.values())
            total_all = total_500m + total_1km

            # Calculate score
            # Base score from counts (max 7 points)
            score = min(7, (total_500m * 2 + total_1km * 1) / 2)

            # Diversity bonus (max 3 points)
            school_types = set(schools_500m.keys()) | set(schools_1km.keys())
            diversity_bonus = min(3, len(school_types))
            score += diversity_bonus

            # Ensure score is between 0 and 10
            final_score = Decimal(str(min(10, max(0, score)))).quantize(Decimal("0.1"))

            return {
                "score": final_score,
                "schools_500m": total_500m,
                "schools_1km": total_1km,
                "school_types": list(school_types),
                "breakdown": {
                    "in_500m": schools_500m,
                    "in_1km": schools_1km,
                },
            }

        except Exception as e:
            # Return default score if POI table doesn't exist
            return {
                "score": Decimal("5.0"),
                "schools_500m": 0,
                "schools_1km": 0,
                "school_types": [],
                "error": str(e),
            }

        finally:
            conn.close()
