"""Tests pour DuckDBConnectionBase."""

from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from app.repositories.duckdb_base import DuckDBConnectionBase


class TestDuckDBConnectionBase:
    """Tests de la base de connexion DuckDB."""

    def test_dept_from_parcelle_without_pool_returns_none(self, tmp_path):
        db = tmp_path / "test.duckdb"
        duckdb.connect(str(db)).close()
        base = DuckDBConnectionBase(db_path=db)
        assert base._dept_from_parcelle("35238000AB0297") is None

    def test_dept_from_commune_without_pool_returns_none(self, tmp_path):
        db = tmp_path / "test.duckdb"
        duckdb.connect(str(db)).close()
        base = DuckDBConnectionBase(db_path=db)
        assert base._dept_from_commune("35238") is None

    def test_get_connection_uses_pool_when_dept(self, tmp_path):
        db = tmp_path / "test.duckdb"
        duckdb.connect(str(db)).close()
        pool = MagicMock()
        pool.get_connection.return_value = MagicMock()
        base = DuckDBConnectionBase(db_path=db, pool=pool)
        base._get_connection(dept="35")
        pool.get_connection.assert_called_once_with("35")

    def test_dept_from_parcelle_extracts_dept(self, tmp_path):
        db = tmp_path / "test.duckdb"
        duckdb.connect(str(db)).close()
        pool = MagicMock()
        base = DuckDBConnectionBase(db_path=db, pool=pool)
        dept = base._dept_from_parcelle("35238000AB0297")
        assert dept == "35"

    def test_close_clears_connection(self, tmp_path):
        db = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db))
        conn.close()
        base = DuckDBConnectionBase(db_path=db)
        base._conn = MagicMock()
        base.close()
        assert base._conn is None
