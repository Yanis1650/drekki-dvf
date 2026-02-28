"""Tests unitaires pour le package etl_build_steps."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Ajouter data-pipeline au path pour importer etl_build_steps
sys.path.insert(0, str(Path(__file__).parent.parent / "data-pipeline"))

from etl_build_steps.config import (
    BDNB_PARQUET,
    DATA_DIR,
    GRID_SIZE,
    GPU_WFS_URL,
    MAIN_DB,
    W_BDNB,
    W_DENSIF,
    W_DVF,
    W_FRAICHEUR,
)
from etl_build_steps.utils import print_distribution, step_banner
from etl_build_steps.optimize import step_optimize


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
