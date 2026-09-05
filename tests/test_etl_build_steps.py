"""Tests unitaires pour le package etl_build_steps."""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from etl_build_dept import resolve_build_paths
from etl_build_steps.confidence import step_confidence

# Ajouter data-pipeline au path pour importer etl_build_steps
from etl_build_steps.config import (
    BDNB_PARQUET,
    DATA_DIR,
    GPU_WFS_URL,
    GRID_SIZE,
    MAIN_DB,
    W_BDNB,
    W_DENSIF,
    W_DVF,
    W_FRAICHEUR,
)
from etl_build_steps.optimize import step_optimize
from etl_build_steps.utils import print_distribution, step_banner


class TestConfig:
    """Tests des constantes de configuration."""

    def test_data_dir_is_path(self):
        assert isinstance(DATA_DIR, Path)
        assert DATA_DIR.name == "data"

    def test_main_db_path(self):
        assert MAIN_DB == DATA_DIR / "foncier.duckdb"

    def test_bdnb_parquet_path(self):
        assert BDNB_PARQUET == DATA_DIR / "bdnb_stats.parquet"

    def test_gpu_url(self):
        assert "geopf.fr" in GPU_WFS_URL

    def test_weights_sum_to_one(self):
        assert abs(W_BDNB + W_DVF + W_DENSIF + W_FRAICHEUR - 1.0) < 0.01

    def test_grid_size_positive(self):
        assert GRID_SIZE == 200


class TestStepBanner:
    """Tests de step_banner."""

    def test_step_banner_prints(self):
        out = StringIO()
        with patch("sys.stdout", out):
            step_banner(1, "Golden Join")
        s = out.getvalue()
        assert "Etape 1/7" in s
        assert "Golden Join" in s
        assert "=" in s


class TestPrintDistribution:
    """Tests de print_distribution avec connexion DuckDB."""

    def test_print_distribution_returns_rows(self, duckdb_conn_densification):
        rows = print_distribution(duckdb_conn_densification, "Test")
        assert len(rows) == 4
        categories = {r[0] for r in rows}
        assert "FORT" in categories
        assert "MOYEN" in categories

    def test_print_distribution_pct_sum(self, duckdb_conn_densification):
        rows = print_distribution(duckdb_conn_densification, "Test")
        total_pct = sum(r[2] for r in rows)
        assert abs(total_pct - 100.0) < 0.1


class TestStepOptimize:
    """Tests de step_optimize."""

    def test_step_optimize_runs(self, duckdb_conn_densification):
        step_optimize(duckdb_conn_densification, "35")
        tables = duckdb_conn_densification.execute("SHOW TABLES").fetchall()
        assert any(t[0] == "densification_scores" for t in tables)


class TestStepConfidence:
    def test_build_uses_the_canonical_densification_score_column(self, duckdb_conn_plain):
        conn = duckdb_conn_plain
        conn.execute("""
            CREATE TABLE densification_scores (
                id_parcelle VARCHAR,
                source_ces VARCHAR,
                zone_non_mutable BOOLEAN,
                code_commune VARCHAR
            )
        """)
        conn.execute("""
            INSERT INTO densification_scores VALUES
            ('35238000AB0297', 'plu_gpu', FALSE, '35238')
        """)
        conn.execute("""
            CREATE TABLE france_foncier_test (
                cadastre_parcelle_id VARCHAR,
                date_mutation VARCHAR,
                dpe_energie VARCHAR,
                annee_construction INTEGER,
                hauteur_moyenne DOUBLE
            )
        """)
        conn.execute("""
            INSERT INTO france_foncier_test VALUES
            ('35238000AB0297', '2025-01-15', 'C', 1985, 6.0)
        """)

        step_confidence(conn, "35")

        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'confidence_scores'"
            ).fetchall()
        }
        assert "score_densification" in columns
        assert "score_zan" not in columns


class TestDepartmentBuildPaths:
    def test_existing_target_is_preserved_without_replace_flag(self, tmp_path):
        output = tmp_path / "dept35.duckdb"
        output.write_text("existing database", encoding="utf-8")

        try:
            resolve_build_paths(output, replace=False)
        except FileExistsError as error:
            assert "--replace" in str(error)
        else:
            raise AssertionError("une base existante ne doit jamais etre ecrasee par defaut")

        assert output.read_text(encoding="utf-8") == "existing database"

    def test_build_uses_a_neighbouring_temporary_file(self, tmp_path):
        output, working = resolve_build_paths(tmp_path / "dept35.duckdb", replace=False)

        assert output.name == "dept35.duckdb"
        assert working.name == ".dept35.duckdb.building"
