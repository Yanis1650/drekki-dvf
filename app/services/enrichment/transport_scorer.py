"""Transport scorer implementation.

Calculates transport score based on proximity to stations.
"""

from decimal import Decimal
from math import cos, radians
from pathlib import Path

import duckdb

from app.services.enrichment.base_scorer import IScorer


class TransportScorer(IScorer):
    """Scorer for transport accessibility.

    Score calculation:
    - Distance to nearest station (primary factor)
    - Count of stations within 1km (secondary factor)
    - Bonus for transport type diversity (gare, metro, bus, tram)

    Score scale:
    - 0: No station within 2km
    - 5: Station within 500m-1km
    - 10: Multiple stations within 300m
    """

    def __init__(self, duckdb_path: Path | str = "./data/foncier.duckdb") -> None:
        self._duckdb_path = Path(duckdb_path)

    @property
    def name(self) -> str:
        return "transport"

    @property
    def poi_type(self) -> str:
        return "gare"

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get read-only DuckDB connection."""
        return duckdb.connect(str(self._duckdb_path), read_only=True)

    async def calculate_score(
        self,
        latitude: float,
        longitude: float,
    ) -> Decimal:
        """Calculate transport score for a location."""
        details = await self.calculate_score_with_details(latitude, longitude)
        return details["score"]

    async def calculate_score_with_details(
        self,
        latitude: float,
        longitude: float,
    ) -> dict:
        """Calculate transport score with detailed breakdown."""
        conn = self._get_connection()

        try:
            # Search within 2km radius
            lat_delta = 2000 / 111000
            lon_delta = 2000 / (111000 * abs(cos(radians(latitude))))

            # Query nearest stations with distance
            result = conn.execute("""
                WITH stations AS (
                    SELECT 
                        id,
                        nom,
                        sous_type,
                        longitude as lon,
                        latitude as lat,
                        6371000 * ACOS(
                            LEAST(1.0, GREATEST(-1.0,
                                COS(RADIANS(?)) * COS(RADIANS(latitude)) *
                                COS(RADIANS(longitude) - RADIANS(?)) +
                                SIN(RADIANS(?)) * SIN(RADIANS(latitude))
                            ))
                        ) AS distance_meters
                    FROM points_interet
                    WHERE type_poi = 'gare'
                      AND longitude BETWEEN ? AND ?
                      AND latitude BETWEEN ? AND ?
                )
                SELECT 
                    id, nom, sous_type, lon, lat, distance_meters
                FROM stations
                WHERE distance_meters <= 2000
                ORDER BY distance_meters ASC
                LIMIT 10
            """, [
                latitude, longitude, latitude,
                longitude - lon_delta, longitude + lon_delta,
                latitude - lat_delta, latitude + lat_delta,
            ]).fetchall()

            if not result:
                return {
                    "score": Decimal("0.0"),
                    "nearest_distance_m": None,
                    "stations_1km": 0,
                    "transport_types": [],
                }

            # Analyze results
            nearest_distance = result[0][5]
            stations_within_1km = sum(1 for r in result if r[5] <= 1000)
            transport_types = list(set(r[2] for r in result))

            # Calculate base score from nearest station distance
            if nearest_distance <= 200:
                base_score = 8
            elif nearest_distance <= 500:
                base_score = 6
            elif nearest_distance <= 1000:
                base_score = 4
            elif nearest_distance <= 1500:
                base_score = 2
            else:
                base_score = 1

            # Bonus for multiple stations (max 1.5 points)
            count_bonus = min(1.5, stations_within_1km * 0.3)

            # Diversity bonus (max 0.5 points)
            diversity_bonus = min(0.5, len(transport_types) * 0.15)

            total_score = min(10, base_score + count_bonus + diversity_bonus)
            final_score = Decimal(str(total_score)).quantize(Decimal("0.1"))

            return {
                "score": final_score,
                "nearest_distance_m": round(nearest_distance),
                "nearest_station": result[0][1] if result else None,
                "stations_1km": stations_within_1km,
                "transport_types": transport_types,
                "stations": [
                    {
                        "name": r[1],
                        "type": r[2],
                        "distance_m": round(r[5]),
                    }
                    for r in result[:5]
                ],
            }

        except Exception as e:
            # Return default score if POI table doesn't exist
            return {
                "score": Decimal("5.0"),
                "nearest_distance_m": None,
                "stations_1km": 0,
                "transport_types": [],
                "error": str(e),
            }

        finally:
            conn.close()
