"""Vérifications post-migration avant ETL / déploiement.

Usage:
    python data-pipeline/preflight_check.py data/dept35.duckdb

Exit 0 si les colonnes attendues sont présentes avec le bon type (approximatif).
Exit 1 sinon (messages ERROR sur stderr).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_EXPECTED: list[tuple[str, str, str]] = [
    ("densification_scores", "plu_datappro", "DATE"),
    ("densification_scores", "zone_non_mutable", "BOOLEAN"),
    ("france_foncier_test", "is_outlier", "BOOLEAN"),
    ("plu_coverage_issues", "motif", "VARCHAR"),
]


def _col_type(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> str | None:
    row = conn.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = ?
          AND column_name = ?
        """,
        [table, column],
    ).fetchone()
    return row[0] if row else None


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [table],
    ).fetchone()
    return bool(row and row[0])


def _normalize(dtype: str) -> str:
    u = dtype.upper()
    if u.startswith("BOOL"):
        return "BOOLEAN"
    if u in ("STRING", "TEXT"):
        return "VARCHAR"
    return u


def run_checks(db_path: Path) -> bool:
    if not db_path.is_file():
        logger.error("Base DuckDB introuvable: %s", db_path)
        return False
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        for table, column, expected in _EXPECTED:
            if not _table_exists(conn, table):
                logger.error("Table manquante: %s", table)
                return False
            actual = _col_type(conn, table, column)
            if actual is None:
                logger.error("Colonne manquante: %s.%s", table, column)
                return False
            if _normalize(actual) != _normalize(expected):
                logger.error(
                    "Type inattendu pour %s.%s: %s (attendu %s)",
                    table,
                    column,
                    actual,
                    expected,
                )
                return False
    finally:
        conn.close()
    logger.info("Preflight OK: %s", db_path)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) != 2:
        print(
            "Usage: python data-pipeline/preflight_check.py <chemin_base.duckdb>",
            file=sys.stderr,
        )
        sys.exit(1)
    db = Path(sys.argv[1])
    sys.exit(0 if run_checks(db) else 1)


if __name__ == "__main__":
    main()
