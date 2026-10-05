"""Mixin pour les opérations transactions DVF (commune, parcelle, bbox)."""

import logging
from datetime import date, datetime
from decimal import Decimal

from app.domain.models import MutationAggregate, NatureMutation, Transaction

logger = logging.getLogger(__name__)


def _parse_mutation_date(val) -> date:
    """Parse date from result (string or date)."""
    if isinstance(val, str):
        return datetime.strptime(val, "%Y-%m-%d").date()
    return val


class DuckDBTransactionsMixin:
    """Mixin transactions: commune, bbox, radius, price stats."""

    async def get_transactions_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions for a commune using mutations_aggregated."""
        conn = self._get_connection()
        query = """
            SELECT m.id_mutation, m.date_mutation, m.nature_mutation, m.valeur_fonciere,
                   m.code_commune, unnest(m.parcelles) as id_parcelle,
                   NULL as type_local,
                   m.surface_habitable_totale as surface_reelle_bati,
                   m.nombre_locaux as nombre_pieces
            FROM mutations_aggregated m
            WHERE m.code_commune = ?
        """
        params: list = [code_commune]

        if date_from:
            query += " AND m.date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND m.date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        return [
            Transaction(
                id_mutation=r[0],
                date_mutation=_parse_mutation_date(r[1]),
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=None,
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8] if r[8] else 0,
            )
            for r in results
        ]

    async def get_mutations_by_commune(
        self,
        code_commune: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[MutationAggregate]:
        """Retrieve aggregated mutations (pre-computed by ETL)."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        query = """
            SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                   code_commune, parcelles, surface_habitable_totale, nombre_locaux
            FROM mutations_aggregated
            WHERE code_commune = ?
        """
        params: list = [code_commune]

        if date_from:
            query += " AND date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        return [
            MutationAggregate(
                id_mutation=r[0],
                date_mutation=_parse_mutation_date(r[1]),
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                parcelles=r[5],
                surface_habitable_totale=Decimal(str(r[6])),
                nombre_locaux=r[7],
            )
            for r in results
        ]

    async def get_transactions_in_bbox(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Transaction]:
        """Retrieve transactions within a bounding box."""
        conn = self._get_connection()
        query = """
            SELECT m.id_mutation, m.date_mutation, m.nature_mutation, m.valeur_fonciere,
                   m.code_commune, p.id_parcelle,
                   NULL as type_local,
                   m.surface_habitable_totale,
                   m.nombre_locaux
            FROM mutations_aggregated m
            CROSS JOIN UNNEST(m.parcelles) as t(pid)
            JOIN parcelles p ON t.pid = p.id_parcelle
            WHERE ST_Intersects(p.geometry, ST_MakeEnvelope(?, ?, ?, ?))
        """
        params: list = [min_x, min_y, max_x, max_y]

        if date_from:
            query += " AND m.date_mutation >= ?"
            params.append(date_from)
        if date_to:
            query += " AND m.date_mutation <= ?"
            params.append(date_to)

        results = conn.execute(query, params).fetchall()

        return [
            Transaction(
                id_mutation=r[0],
                date_mutation=_parse_mutation_date(r[1]),
                nature_mutation=NatureMutation(r[2]),
                valeur_fonciere=Decimal(str(r[3])),
                code_commune=r[4],
                id_parcelle=r[5],
                type_local=None,
                surface_reelle_bati=Decimal(str(r[7])) if r[7] else None,
                nombre_pieces=r[8] if r[8] else 0,
            )
            for r in results
        ]
