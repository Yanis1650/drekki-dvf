"""Mixin des transactions DVF : par commune et par emprise rectangulaire."""

from datetime import date

from app.domain.models import Transaction
from app.repositories.dvf.mapping import (
    COLONNES_TRANSACTION,
    appliquer_bornes,
    prefixer,
    vers_transactions,
)


class DvfTransactionsMixin:
    """Lectures de la table `transactions`."""

    async def get_transactions_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions for a commune."""
        conn = self._get_connection()
        query = f"""
            SELECT {COLONNES_TRANSACTION}
            FROM transactions
            WHERE code_commune = ?
        """
        params: list = [code_commune]
        query = appliquer_bornes(query, params, date_from, date_to)

        return vers_transactions(conn.execute(query, params).fetchall())

    async def get_transactions_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions within a bounding box.

        Exige l'extension spatiale : la jointure passe par la geometrie des
        parcelles.
        """
        conn = self._get_connection()
        query = f"""
            SELECT {prefixer(COLONNES_TRANSACTION, "t")}
            FROM transactions t
            JOIN parcelles p ON t.id_parcelle = p.id_parcelle
            WHERE ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
        """
        params: list = [min_x, min_y, max_x, max_y]
        query = appliquer_bornes(
            query, params, date_from, date_to, colonne="t.date_mutation"
        )

        return vers_transactions(conn.execute(query, params).fetchall())
