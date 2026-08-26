"""Tests pour DuckDBPool et extraction département."""


import pytest

from app.infrastructure.duckdb_pool import DuckDBPool


class TestExtractDept:
    """Tests de DuckDBPool.extract_dept."""

    def test_dept_metropole_2_chiffres(self):
        assert DuckDBPool.extract_dept("35238000AB0297") == "35"
        assert DuckDBPool.extract_dept("35238") == "35"

    def test_dept_corse_2a(self):
        assert DuckDBPool.extract_dept("2A123456789012") == "2A"

    def test_dept_corse_2b(self):
        assert DuckDBPool.extract_dept("2B123456789012") == "2B"

    def test_dept_dom_971(self):
        assert DuckDBPool.extract_dept("97112345678901") == "971"

    def test_dept_dom_972(self):
        assert DuckDBPool.extract_dept("97212345678901") == "972"

    def test_dept_dom_974(self):
        assert DuckDBPool.extract_dept("97412345678901") == "974"

    def test_dept_dom_976(self):
        assert DuckDBPool.extract_dept("97612345678901") == "976"

    def test_extract_dept_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot extract dept"):
            DuckDBPool.extract_dept("")

    def test_extract_dept_single_char_raises(self):
        with pytest.raises(ValueError, match="Cannot extract dept"):
            DuckDBPool.extract_dept("3")


class TestDuckDBPool:
    """Tests du pool de connexions."""

    def test_resolve_path_dept_file(self, tmp_data_dir):
        dept_db = tmp_data_dir / "dept35.duckdb"
        dept_db.touch()
        pool = DuckDBPool(tmp_data_dir)
        path = pool._resolve_path("35")
        assert path == dept_db

    def test_resolve_path_fallback_legacy(self, tmp_data_dir):
        legacy = tmp_data_dir / "foncier.duckdb"
        legacy.touch()
        pool = DuckDBPool(tmp_data_dir, legacy_path=legacy)
        path = pool._resolve_path("99")
        assert path == legacy

    def test_resolve_path_not_found_raises(self, tmp_data_dir):
        pool = DuckDBPool(tmp_data_dir)
        with pytest.raises(FileNotFoundError, match="Aucune base"):
            pool._resolve_path("99")

    def test_available_depts(self, tmp_data_dir):
        (tmp_data_dir / "dept35.duckdb").touch()
        (tmp_data_dir / "dept29.duckdb").touch()
        pool = DuckDBPool(tmp_data_dir)
        depts = pool.available_depts
        assert "35" in depts
        assert "29" in depts
