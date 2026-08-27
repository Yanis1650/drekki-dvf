"""Mixin pour get_price_stats et get_mutations_in_radius."""

from datetime import date, datetime
from decimal import Decimal
from math import cos, radians

from app.domain.models import MutationAggregate, NatureMutation
from app.infrastructure.data_availability import column_exists, table_exists


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
        """Get price statistics for a commune (outliers exclus)."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        # Utilise france_foncier_test (joint spatial) pour bénéficier du flag is_outlier.
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

        # `type_local` a ete ajoute apres coup au pipeline : les bases
        # construites avant ne l'ont pas, et le selectionner ferait echouer
        # toute la requete au binding plutot que de laisser le champ vide.
        has_type_local = column_exists(conn, "mutations_aggregated", "type_local")
        type_local_select = "type_local" if has_type_local else "NULL AS type_local"

        # `is_outlier` est calcule par l'ETL dans france_foncier_test, pas dans
        # mutations_aggregated. Sans cette jointure, MutationAggregate.is_outlier
        # gardait sa valeur par defaut (False) pour *toutes* les mutations : le
        # prix moyen « hors aberrantes » n'excluait donc rien, et le compteur
        # d'aberrantes de la carte affichait 0 en permanence.
        has_outlier = table_exists(conn, "france_foncier_test") and column_exists(
            conn, "france_foncier_test", "is_outlier"
        )
        if has_outlier:
            outlier_select = "COALESCE(o.is_outlier, FALSE) AS is_outlier"
            outlier_join = """
                LEFT JOIN (
                    SELECT DISTINCT id_mutation, is_outlier
                    FROM france_foncier_test
                ) o ON o.id_mutation = m.id_mutation
            """
        else:
            outlier_select = "FALSE AS is_outlier"
            outlier_join = ""

        query = f"""
            WITH bbox_filtered AS (
                SELECT m.*, {outlier_select}
                FROM mutations_aggregated m
                {outlier_join}
                WHERE m.longitude IS NOT NULL
                  AND m.latitude IS NOT NULL
                  AND m.longitude BETWEEN ? AND ?
                  AND m.latitude BETWEEN ? AND ?
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
                prix_m2, longitude, latitude, distance_meters, {type_local_select},
                is_outlier
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
                type_local=r[12] if len(r) > 12 else None,
                is_outlier=bool(r[13]) if len(r) > 13 and r[13] is not None else False,
            )
            for r in results
        ]
