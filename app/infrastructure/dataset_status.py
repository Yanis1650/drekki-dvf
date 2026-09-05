"""Lecture non intrusive de l'etat de la base DuckDB servie par l'API."""

from dataclasses import dataclass
from pathlib import Path

import duckdb

CORE_APPLICATION_TABLES = (
    "mutations_aggregated",
    "france_foncier_test",
    "parcelles",
    "densification_scores",
    "confidence_scores",
)


@dataclass(frozen=True)
class DatasetStatus:
    """Etat minimal de la base departementale necessaire a l'application."""

    ready: bool
    missing_tables: list[str]
    reason: str | None = None


def inspect_dataset(database_path: Path) -> DatasetStatus:
    """Verifie le fichier et les tables coeur sans modifier la base.

    La sonde ne requiert volontairement pas les jeux optionnels (filiation,
    POI, risques) : leur absence est deja declaree par les routes concernees.
    """
    path = Path(database_path)
    if not path.is_file():
        return DatasetStatus(False, [], "database file is missing")

    try:
        conn = duckdb.connect(str(path), read_only=True)
        try:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        finally:
            conn.close()
    except duckdb.Error:
        return DatasetStatus(False, [], "database cannot be opened")

    missing_tables = [table for table in CORE_APPLICATION_TABLES if table not in tables]
    return DatasetStatus(not missing_tables, missing_tables)
