"""DuckDB connection base for repository implementations.

Shared connection logic and department routing for single-DB and multi-dept modes.
"""

from pathlib import Path

import duckdb

from app.infrastructure.duckdb_pool import DuckDBPool
from app.infrastructure.duckdb_spatial import ensure_spatial


class DuckDBConnectionBase:
    """Base class providing DuckDB connection and department routing."""

    def __init__(
        self,
        db_path: Path | str,
        pool: DuckDBPool | None = None,
        dept_prefix: str | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._pool = pool
        # Garde-fou optionnel quand une base unique couvre plusieurs departements
        # (ex. foncier.duckdb France entiere). None = pas de filtre.
        self._dept_prefix = dept_prefix
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_connection(self, dept: str | None = None) -> duckdb.DuckDBPyConnection:
        """Get connection, routing to per-dept DB when pool is available."""
        if self._pool and dept:
            return self._pool.get_connection(dept)

        if self._conn is None:
            self._conn = duckdb.connect(str(self._db_path), read_only=True)
            ensure_spatial(self._conn)
        return self._conn

    def _dept_from_parcelle(self, id_parcelle: str) -> str | None:
        if self._pool and id_parcelle and len(id_parcelle) >= 2:
            return DuckDBPool.extract_dept(id_parcelle)
        return None

    def _dept_from_commune(self, code_commune: str) -> str | None:
        if self._pool and code_commune and len(code_commune) >= 2:
            return DuckDBPool.extract_dept(code_commune)
        return None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
