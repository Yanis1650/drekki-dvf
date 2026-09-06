"""Transactions d'une parcelle donnee, en trois requetes en cascade.

`list_contains` sur `mutations_aggregated` d'abord ; un repli `UNNEST` si
cette fonction echoue sur la base ; puis `france_foncier_test` si rien n'a
ete trouve. Les trois chemins rendent des MutationAggregate, mais ne
selectionnent pas les memes colonnes — voir
`tests/test_duckdb_transactions.py`.
"""

import logging
from decimal import Decimal

from app.domain.models import MutationAggregate, NatureMutation
from app.repositories.duckdb.transactions_mixin import _parse_mutation_date

logger = logging.getLogger(__name__)


class DuckDBTransactionsParcelMixin:
    """Lecture des mutations couvrant une parcelle."""

    async def get_transactions_for_parcel(
        self, id_parcelle: str, limit: int = 100
    ) -> list[MutationAggregate]:
        """Retrieve DVF transactions that include a specific parcel."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        results = []

        try:
            tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
            if "mutations_aggregated" in tables:
                query = f"""
                    SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                           code_commune, parcelles, surface_habitable_totale, nombre_locaux,
                           prix_m2, longitude, latitude, NULL AS type_local
                    FROM mutations_aggregated
                    WHERE list_contains(parcelles, ?)
                    ORDER BY date_mutation DESC
                    LIMIT {limit}
                """
                try:
                    results = conn.execute(query, [id_parcelle]).fetchall()
                except Exception as e:
                    logger.debug("list_contains failed, UNNEST fallback: %s", e)
                    query_fb = f"""
                        SELECT m.id_mutation, m.date_mutation, m.nature_mutation,
                               m.valeur_fonciere, m.code_commune, m.parcelles,
                               m.surface_habitable_totale, m.nombre_locaux,
                               m.prix_m2, m.longitude, m.latitude, NULL AS type_local
                        FROM mutations_aggregated m, UNNEST(m.parcelles) AS p(pid)
                        WHERE p.pid = ? ORDER BY m.date_mutation DESC LIMIT {limit}
                    """
                    results = conn.execute(query_fb, [id_parcelle]).fetchall()

            if not results and "france_foncier_test" in tables:
                query_fft = f"""
                    SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                           code_commune, [cadastre_parcelle_id] AS parcelles,
                           surface_habitable_totale, COALESCE(nombre_locaux, 1) AS nombre_locaux,
                           prix_m2, longitude, latitude,
                           COALESCE(is_outlier, FALSE) AS is_outlier,
                           type_local
                    FROM france_foncier_test
                    WHERE cadastre_parcelle_id = ?
                    ORDER BY date_mutation DESC
                    LIMIT {limit}
                """
                results = conn.execute(query_fft, [id_parcelle]).fetchall()
        except Exception as e:
            logger.warning("get_transactions_for_parcel failed: %s", e)

        return [
            MutationAggregate(
                id_mutation=r[0],
                date_mutation=_parse_mutation_date(r[1]),
                nature_mutation=NatureMutation(r[2]) if r[2] else NatureMutation("Vente"),
                valeur_fonciere=Decimal(str(r[3])) if r[3] else Decimal("0"),
                code_commune=str(r[4]),
                parcelles=r[5] if r[5] else [],
                surface_habitable_totale=Decimal(str(r[6])) if r[6] else Decimal("0"),
                nombre_locaux=r[7] if r[7] else 0,
                longitude=r[9] if len(r) > 9 else None,
                latitude=r[10] if len(r) > 10 else None,
                is_outlier=bool(r[11]) if len(r) > 11 else False,
                type_local=r[12] if len(r) > 12 else None,
            )
            for r in results
        ]
