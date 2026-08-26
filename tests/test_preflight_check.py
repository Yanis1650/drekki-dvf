"""Tests pour data-pipeline/preflight_check.py (schéma post-migration)."""

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "data-pipeline" / "preflight_check.py"


@pytest.fixture
def duckdb_preflight_ok(tmp_path: Path) -> Path:
    db = tmp_path / "ok.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute(
        "CREATE TABLE densification_scores (plu_datappro DATE, zone_non_mutable BOOLEAN);"
    )
    conn.execute("CREATE TABLE france_foncier_test (is_outlier BOOLEAN);")
    conn.execute("CREATE TABLE plu_coverage_issues (motif VARCHAR);")
    conn.close()
    return db


def test_preflight_passes_when_schema_complete(duckdb_preflight_ok: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(PREFLIGHT), str(duckdb_preflight_ok)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


def test_preflight_fails_when_column_missing(tmp_path: Path) -> None:
    db = tmp_path / "bad.duckdb"
    conn = duckdb.connect(str(db))
    conn.execute("CREATE TABLE densification_scores (plu_datappro DATE);")
    conn.execute("CREATE TABLE france_foncier_test (is_outlier BOOLEAN);")
    conn.execute("CREATE TABLE plu_coverage_issues (motif VARCHAR);")
    conn.close()
    r = subprocess.run(
        [sys.executable, str(PREFLIGHT), str(db)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "zone_non_mutable" in r.stderr or "zone_non_mutable" in r.stdout
