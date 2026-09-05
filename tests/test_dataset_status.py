"""Contrat de disponibilite de la base departementale servie par l'API."""

import duckdb

from app.infrastructure.dataset_status import inspect_dataset


def test_dataset_status_requires_the_core_application_tables(tmp_path):
    path = tmp_path / "dept35.duckdb"
    conn = duckdb.connect(str(path))
    for table in (
        "mutations_aggregated",
        "france_foncier_test",
        "parcelles",
        "densification_scores",
        "confidence_scores",
    ):
        conn.execute(f"CREATE TABLE {table} (id INTEGER)")
    conn.close()

    status = inspect_dataset(path)

    assert status.ready is True
    assert status.missing_tables == []


def test_dataset_status_explains_a_missing_database_without_raising(tmp_path):
    status = inspect_dataset(tmp_path / "missing.duckdb")

    assert status.ready is False
    assert status.missing_tables == []
    assert status.reason == "database file is missing"
