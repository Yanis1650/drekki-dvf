"""POI/Enrichment Repository implementation.

Segregated from DVF for SOLID compliance.

Les lectures vivent dans `app/repositories/poi/` : scores d'enrichissement
d'un cote, requetes geographiques de l'autre. Cette classe ne porte plus que
la connexion.
"""

from pathlib import Path

import duckdb

from app.infrastructure.duckdb_pool import close_shared_connection, get_shared_connection
from app.repositories.interfaces import IEnrichmentRepository
from app.repositories.poi import PoiEnrichmentMixin, PoiSpatialMixin

__all__ = ["PoiRepository"]


class PoiRepository(PoiEnrichmentMixin, PoiSpatialMixin, IEnrichmentRepository):
    """DuckDB implementation for POI and enrichment data.

    Handles POI queries and enrichment scores.
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
