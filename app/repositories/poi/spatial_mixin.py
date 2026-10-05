"""Requetes geographiques sur `points_interet`.

Chacune pre-filtre par une emprise rectangulaire avant de calculer la
distance Haversine — voir `geo.emprise` pour ce que cette approximation
implique.
"""

from app.repositories.poi.geo import emprise


class PoiSpatialMixin:
    """Comptage et recherche de POI autour d'un point."""

    async def get_poi_count_in_radius(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        type_poi: str | None = None,
    ) -> int:
        """Count POI within a radius."""
        conn = self._get_connection()


        query = """
            SELECT COUNT(*)
            FROM points_interet
            WHERE longitude BETWEEN ? AND ?
              AND latitude BETWEEN ? AND ?
        """
        params = emprise(lat, lon, radius_meters)

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
            *emprise(lat, lon, max_distance_m),
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
        params = [lat, lon, lat, *emprise(lat, lon, radius_meters)]

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
