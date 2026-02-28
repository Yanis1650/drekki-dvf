"""Pytest fixtures shared across tests."""

from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for ETL/DB tests."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def duckdb_conn_inmemory():
    """In-memory DuckDB connection with spatial extension."""
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL spatial; LOAD spatial;")
    yield conn
    conn.close()


@pytest.fixture
def duckdb_conn_with_fixtures(duckdb_conn_inmemory):
    """DuckDB connection with france_foncier_test and parcelles for GeoJSON tests.

    Uses code_commune 35xxx (Rennes) to match hardcoded LIKE '35%' in duckdb_geojson.
    """
    conn = duckdb_conn_inmemory
    conn.execute("""
        CREATE TABLE france_foncier_test (
            id_mutation VARCHAR,
            longitude DOUBLE,
            latitude DOUBLE,
            prix_m2 DOUBLE,
            date_mutation DATE,
            valeur_fonciere DOUBLE,
            nature_mutation VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO france_foncier_test VALUES
        ('MUT001', -1.68, 48.11, 2500.0, '2024-01-15', 150000.0, 'Vente'),
        ('MUT002', -1.69, 48.12, 3000.0, '2023-06-20', 200000.0, 'Vente')
    """)
    conn.execute("""
        CREATE TABLE parcelles (
            code_commune VARCHAR,
            prefixe VARCHAR,
            section VARCHAR,
            numero VARCHAR,
            geometry GEOMETRY
        )
    """)
    conn.execute("""
        INSERT INTO parcelles VALUES
        ('35238', '000', 'AB', '0297',
         ST_GeomFromText('POLYGON((515000 6800000, 515050 6800000, 515050 6800050, 515000 6800050, 515000 6800000))', 2154))
    """)
    yield conn


@pytest.fixture
def duckdb_conn_densification(duckdb_conn_inmemory):
    """DuckDB connection with densification_scores for utils.print_distribution."""
    conn = duckdb_conn_inmemory
    conn.execute("""
        CREATE TABLE densification_scores (
            id_parcelle VARCHAR,
            code_commune VARCHAR,
            categorie VARCHAR,
            surface_parcelle_m2 DOUBLE
        )
    """)
    conn.execute("""
        INSERT INTO densification_scores VALUES
        ('35238000AB0297', '35238', 'FORT', 1000),
        ('35238000AB0298', '35238', 'MOYEN', 800),
        ('35238000AB0299', '35238', 'FAIBLE', 500),
        ('35238000AB0300', '35238', 'SATURE', 600)
    """)
    yield conn
