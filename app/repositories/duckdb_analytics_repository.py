"""DuckDB Analytics Repository.

Dedicated repository for market trends and analytics queries.
Separated from main repository to maintain 400-line limit (SRP).
"""

import logging
from datetime import datetime
from pathlib import Path

import duckdb

from app.infrastructure.data_availability import column_exists
from app.infrastructure.duckdb_pool import (
    DuckDBPool,
    close_shared_connection,
    get_shared_connection,
)
from app.repositories.duckdb.analytics_trends_mixin import AnalyticsTrendsMixin

logger = logging.getLogger(__name__)


class DuckDBAnalyticsRepository(AnalyticsTrendsMixin):
    """Analytics repository for market trends analysis.

    Handles complex temporal and spatial aggregations for market insights.
    Uses DuckDB's analytical functions for efficient yearly grouping.
    Supports multi-dept pool routing for get_parcel_history.
    """

    def __init__(self, db_path: Path | str, pool: DuckDBPool | None = None) -> None:
        self._db_path = Path(db_path)
        self._pool = pool
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_main_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection to main/legacy DB (for trends spanning many depts)."""
        if self._conn is None:
            self._conn = get_shared_connection(self._db_path)
        return self._conn

    def _get_dept_connection(self, parcel_id: str) -> duckdb.DuckDBPyConnection:
        """Route to the correct dept DB via pool, or fall back to main DB."""
        if self._pool is not None:
            try:
                return self._pool.get_for_parcelle(parcel_id)
            except Exception as error:
                logger.debug("Routage departemental indisponible pour %s: %s", parcel_id, error)
        return self._get_main_connection()

    def _available_tables(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
        """List tables in the given connection."""
        try:
            return [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        except Exception:
            return []

    async def get_parcel_history(
        self,
        parcel_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get transaction history for a specific parcel.

        Routes to the correct dept DB via pool when available,
        so france_foncier_test (which only exists in dept DBs) is found.

        Args:
            parcel_id: Cadastral parcel ID (14 chars: commune(5) + prefixe(3) + section(2) + numero(4))
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dicts with date, price, price_m2, surface, type_local
        """
        conn = self._get_dept_connection(parcel_id)

        logger.debug("get_parcel_history: parcel_id=%s (len=%d)", parcel_id, len(parcel_id))

        tables = self._available_tables(conn)

        # `type_local` a ete ajoute au pipeline apres coup : les bases buildees
        # par une version anterieure ne l'ont pas, et le selectionner faisait
        # echouer la requete entiere au binding (historique vide, sans erreur
        # visible cote client).
        def type_local_select(table: str) -> str:
            if column_exists(conn, table, "type_local"):
                return "type_local"
            return "NULL AS type_local"

        if len(parcel_id) == 14:
            # Extract components
            base_id = parcel_id[:10]  # commune + prefixe + section
            numero_padded = parcel_id[10:]  # 4-char numero with leading zeros
            numero_stripped = numero_padded.lstrip('0') or '0'  # Remove leading zeros
            alt_id_short = base_id + numero_stripped

            logger.debug("Recherche des identifiants %s ou %s", parcel_id, alt_id_short)

            if "france_foncier_test" in tables:
                query = f"""
                    SELECT
                        date_mutation,
                        valeur_fonciere,
                        prix_m2,
                        surface_habitable_totale,
                        cadastre_parcelle_id,
                        COALESCE(is_outlier, FALSE) AS is_outlier,
                        {type_local_select("france_foncier_test")}
                    FROM france_foncier_test
                    WHERE cadastre_parcelle_id IN (?, ?)
                      AND valeur_fonciere > 0
                    ORDER BY date_mutation DESC
                    LIMIT ?
                """
                params = [parcel_id, alt_id_short, limit]
            elif "mutations_aggregated" in tables:
                # Fallback: search by parcel in dvf_parcelles list
                query = f"""
                    SELECT
                        date_mutation,
                        valeur_fonciere,
                        prix_m2,
                        surface_habitable_totale,
                        NULL AS cadastre_parcelle_id,
                        FALSE AS is_outlier,
                        {type_local_select("mutations_aggregated")}
                    FROM mutations_aggregated
                    WHERE list_contains(parcelles, ?)
                      AND valeur_fonciere > 0
                    ORDER BY date_mutation DESC
                    LIMIT ?
                """
                params = [parcel_id, limit]
            else:
                logger.warning("Aucune table de transactions dans cette base")
                return []
        else:
            logger.debug("Recherche de l'identifiant exact %s", parcel_id)

            if "france_foncier_test" in tables:
                query = f"""
                    SELECT
                        date_mutation,
                        valeur_fonciere,
                        prix_m2,
                        surface_habitable_totale,
                        cadastre_parcelle_id,
                        COALESCE(is_outlier, FALSE) AS is_outlier,
                        {type_local_select("france_foncier_test")}
                    FROM france_foncier_test
                    WHERE cadastre_parcelle_id = ?
                      AND valeur_fonciere > 0
                    ORDER BY date_mutation DESC
                    LIMIT ?
                """
                params = [parcel_id, limit]
            else:
                logger.warning("Aucune table de transactions dans cette base")
                return []

        try:
            results = conn.execute(query, params).fetchall()
            logger.debug("%d transactions trouvees", len(results))
        except Exception as e:
            logger.exception("get_parcel_history a echoue pour %s: %s", parcel_id, e)
            return []

        history = []
        for r in results:
            mutation_date = r[0]
            if isinstance(mutation_date, str):
                mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

            history.append({
                "date": str(mutation_date),
                "price": float(r[1]),
                "price_m2": float(r[2]) if r[2] else None,
                "surface": float(r[3]) if r[3] else None,
                "is_outlier": bool(r[5]),
                "type_local": r[6] if len(r) > 6 else None,
            })

        return history

    def close(self) -> None:
        """Relache la connexion partagee (celles du pool restent au pool)."""
        close_shared_connection(self._db_path)
        self._conn = None
