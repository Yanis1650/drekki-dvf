"""DVF Repository implementation (Mutations & Transactions).

Segregated from enrichment for SOLID compliance.

Les requetes vivent dans `app/repositories/dvf/`, un mixin par famille de
lecture ; cette classe ne porte plus que la connexion et sa composition.
"""

import logging
from pathlib import Path

import duckdb

from app.infrastructure.duckdb_pool import close_shared_connection, get_shared_connection
from app.repositories.dvf import (
    DvfGeojsonMixin,
    DvfMutationsMixin,
    DvfStatsMixin,
    DvfTransactionsMixin,
)
from app.repositories.interfaces import ITransactionRepository

logger = logging.getLogger(__name__)


class DvfRepository(
    DvfTransactionsMixin,
    DvfMutationsMixin,
    DvfStatsMixin,
    DvfGeojsonMixin,
    ITransactionRepository,
):
    """DuckDB implementation for DVF transaction data.

    Handles mutations and transactions queries.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Lazy connection initialization."""
        if self._conn is None:
            self._conn = get_shared_connection(self._db_path)
        return self._conn

    def close(self) -> None:
        """Relache la connexion partagee de ce fichier."""
        close_shared_connection(self._db_path)
        self._conn = None
