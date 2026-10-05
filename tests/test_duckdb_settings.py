"""Tests des bornes de ressources appliquees a l'ouverture des bases DuckDB."""

import duckdb
import pytest

from app.infrastructure.duckdb_settings import REGLAGES, connect_read_only


@pytest.fixture
def base(tmp_path):
    path = tmp_path / "base.duckdb"
    conn = duckdb.connect(str(path))
    conn.execute("CREATE TABLE t AS SELECT 1 AS x")
    conn.close()
    return path


@pytest.fixture(autouse=True)
def sans_bornes(monkeypatch):
    for variable in REGLAGES:
        monkeypatch.delenv(variable, raising=False)


def _reglage(conn, nom):
    return conn.execute(f"SELECT current_setting('{nom}')").fetchone()[0]


def test_applique_les_bornes_de_l_environnement(base, tmp_path, monkeypatch):
    monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "512MB")
    monkeypatch.setenv("DUCKDB_THREADS", "2")
    monkeypatch.setenv("DUCKDB_TEMP_DIRECTORY", str(tmp_path / "debord"))

    conn = connect_read_only(base)

    assert _reglage(conn, "memory_limit") == "488.2 MiB"
    assert _reglage(conn, "threads") == 2
    assert _reglage(conn, "temp_directory") == str(tmp_path / "debord")
    assert conn.execute("SELECT x FROM t").fetchone() == (1,)
    conn.close()


def test_sans_variable_duckdb_garde_ses_valeurs(base):
    defaut = duckdb.connect(":memory:")
    conn = connect_read_only(base)

    assert _reglage(conn, "threads") == _reglage(defaut, "threads")
    conn.close()
    defaut.close()


def test_la_connexion_reste_en_lecture_seule(base):
    conn = connect_read_only(base)

    with pytest.raises(duckdb.Error):
        conn.execute("CREATE TABLE u (y INTEGER)")
    conn.close()
