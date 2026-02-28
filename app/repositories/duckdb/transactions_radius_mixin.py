"""Mixin pour get_price_stats et get_mutations_in_radius."""

from datetime import date, datetime
from decimal import Decimal
from math import cos, radians

from app.domain.models import MutationAggregate, NatureMutation


def _parse_mutation_date(val) -> date:
    """Parse date from result (string or date)."""
    if isinstance(val, str):
        return datetime.strptime(val, "%Y-%m-%d").date()
    return val


class DuckDBTransactionsRadiusMixin:
    """Mixin pour statistiques prix et recherche par rayon."""

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
        """Retrieve mutations within a radius using Haversine."""
        conn = self._get_connection()

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

        return [
            MutationAggregate(
                id_mutation=r[0],
                date_mutation=_parse_mutation_date(r[1]),
                nature_mutation=NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
                longitude=r[9],
                latitude=r[10],
            )
            for r in results
        ]
