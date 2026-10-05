"""Controles bloquants et rapport JSON pour une candidate DVF.

L'ossature du rapport vit dans `dvf_quality_report`, les mesures sur la base
dans `dvf_quality_metrics`. Ce module enchaine les gardes et decide quand
s'arreter : chaque echec ecrit le rapport avant de rendre la main.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
from dvf_quality_metrics import REQUIRED_COLUMNS, TABLE, collect_metrics
from dvf_quality_report import (
    MIN_MUTATION_COUNT_RATIO,
    REPORT_SCHEMA_VERSION,
    _base_report,
    _check,
    _compare_with_baseline,
    _complete_report,
    _write_report,
)

__all__ = [
    "MIN_MUTATION_COUNT_RATIO",
    "REPORT_SCHEMA_VERSION",
    "REQUIRED_COLUMNS",
    "TABLE",
    "evaluate_dvf_quality",
]


def evaluate_dvf_quality(
    candidate_path: Path,
    report_path: Path,
    release: str | None = None,
    baseline_report_path: Path | None = None,
) -> dict[str, Any]:
    """Valide une base DVF candidate et ecrit le rapport, y compris en echec."""
    candidate = Path(candidate_path)
    report = _base_report(candidate, release)
    exists = candidate.is_file() and candidate.stat().st_size > 0
    report["checks"].append(_check("candidate_exists", exists, candidate.stat().st_size if exists else 0, "> 0 bytes"))
    if not exists:
        _write_report(report_path, _complete_report(report))
        return report

    try:
        conn = duckdb.connect(str(candidate), read_only=True)
    except duckdb.Error as error:
        report["checks"].append(_check("database_readable", False, str(error), "DuckDB readable"))
        _write_report(report_path, _complete_report(report))
        return report

    try:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        has_table = TABLE in tables
        report["checks"].append(_check("mutations_table", has_table, sorted(tables), TABLE))
        if not has_table:
            _write_report(report_path, _complete_report(report))
            return report

        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [TABLE]
            ).fetchall()
        }
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        report["checks"].append(
            _check("required_columns", not missing_columns, missing_columns, "all canonical DVF columns")
        )
        if missing_columns:
            _write_report(report_path, _complete_report(report))
            return report
        count = collect_metrics(conn, report)
        if baseline_report_path is not None:
            _compare_with_baseline(report, count, Path(baseline_report_path))
    except duckdb.Error as error:
        report["checks"].append(_check("quality_queries", False, str(error), "quality queries succeed"))
    finally:
        conn.close()

    _write_report(report_path, _complete_report(report))
    return report
