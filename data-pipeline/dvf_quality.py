"""Controles bloquants et rapport JSON pour une candidate DVF."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain.dvf_methodology import (  # noqa: E402
    MIN_HABITABLE_SURFACE_M2,
    MIN_TRANSACTION_VALUE_EUR,
    SALE_NATURE,
)

REPORT_SCHEMA_VERSION = 2
TABLE = "mutations_aggregated"
MIN_MUTATION_COUNT_RATIO = 0.75
REQUIRED_COLUMNS = {
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "parcelles",
    "surface_habitable_totale",
    "nombre_locaux",
    "longitude",
    "latitude",
    "type_local",
    "prix_m2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(name: str, passed: bool, observed: Any, expected: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "observed": observed, "expected": expected}


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _base_report(candidate: Path, release: str | None) -> dict[str, Any]:
    database: dict[str, Any] = {"path": str(candidate), "exists": candidate.is_file()}
    if candidate.is_file():
        database.update({"sha256": _sha256(candidate), "size_bytes": candidate.stat().st_size})
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "release": release,
        "generated_at": datetime.now(UTC).isoformat(),
        "database": database,
        "checks": [],
        "metrics": {},
    }


def _complete_report(report: dict[str, Any]) -> dict[str, Any]:
    failed = sum(not check["passed"] for check in report["checks"])
    report["summary"] = {"passed": failed == 0, "total": len(report["checks"]), "failed": failed}
    return report


def _compare_with_baseline(
    report: dict[str, Any], candidate_count: int, baseline_report_path: Path
) -> None:
    """Ajoute un garde-fou de volume contre une release precedemment approuvee.

    Le controle reste opt-in : une premiere release n'a pas de reference fiable.
    Quand une reference est fournie, elle doit elle-meme etre un rapport valide ;
    autrement la candidate ne peut pas etre promue sur la foi d'une comparaison
    incomprehensible.
    """
    try:
        baseline = json.loads(Path(baseline_report_path).read_text(encoding="utf-8"))
        summary = baseline.get("summary", {})
        baseline_count = baseline.get("metrics", {}).get("mutation_count")
        if summary.get("passed") is not True or not isinstance(baseline_count, int) or baseline_count <= 0:
            raise ValueError("rapport non valide ou sans volume de mutations exploitable")
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as error:
        report["comparison"] = {"error": str(error)}
        report["checks"].append(
            _check(
                "previous_release_volume",
                False,
                str(error),
                "a passing baseline quality report with a positive mutation count",
            )
        )
        return

    ratio = round(candidate_count / baseline_count, 4)
    report["comparison"] = {
        "baseline_release": baseline.get("release"),
        "baseline_mutation_count": baseline_count,
        "mutation_count_ratio": ratio,
        "minimum_ratio": MIN_MUTATION_COUNT_RATIO,
    }
    report["checks"].append(
        _check(
            "previous_release_volume",
            ratio >= MIN_MUTATION_COUNT_RATIO,
            {"candidate": candidate_count, "baseline": baseline_count, "ratio": ratio},
            f">= {MIN_MUTATION_COUNT_RATIO:.0%} of the approved baseline mutation count",
        )
    )


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

        validation_params = [SALE_NATURE, MIN_TRANSACTION_VALUE_EUR, MIN_HABITABLE_SURFACE_M2]
        (
            count,
            duplicate_count,
            incomplete_count,
            invalid_values,
            invalid_dates,
            invalid_prices,
            missing_coordinates,
            invalid_coordinates,
            missing_parcel_links,
        ) = conn.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) - COUNT(DISTINCT id_mutation),
                COUNT(*) FILTER (WHERE id_mutation IS NULL OR TRIM(id_mutation) = ''
                    OR date_mutation IS NULL OR nature_mutation IS NULL OR TRIM(nature_mutation) = ''
                    OR valeur_fonciere IS NULL OR code_commune IS NULL OR TRIM(code_commune) = ''
                    OR parcelles IS NULL OR ARRAY_LENGTH(parcelles) = 0
                    OR surface_habitable_totale IS NULL OR nombre_locaux IS NULL
                    OR longitude IS NULL OR latitude IS NULL
                    OR type_local IS NULL OR TRIM(type_local) = ''
                    OR prix_m2 IS NULL),
                COUNT(*) FILTER (WHERE nature_mutation IS NULL OR nature_mutation <> ?
                    OR valeur_fonciere IS NULL OR valeur_fonciere <= ?
                    OR surface_habitable_totale IS NULL OR surface_habitable_totale <= ?),
                COUNT(*) FILTER (WHERE TRY_CAST(date_mutation AS DATE) IS NULL),
                COUNT(*) FILTER (WHERE prix_m2 IS NULL OR prix_m2 <= 0),
                COUNT(*) FILTER (WHERE longitude IS NULL OR latitude IS NULL),
                COUNT(*) FILTER (WHERE longitude IS NOT NULL AND latitude IS NOT NULL
                    AND (longitude < -180 OR longitude > 180 OR latitude < -90 OR latitude > 90)),
                COUNT(*) FILTER (WHERE parcelles IS NULL OR ARRAY_LENGTH(parcelles) = 0)
            FROM mutations_aggregated
            """,
            validation_params,
        ).fetchone()
        date_range = conn.execute(
            """
            SELECT MIN(TRY_CAST(date_mutation AS DATE)), MAX(TRY_CAST(date_mutation AS DATE))
            FROM mutations_aggregated
            """
        ).fetchone()
        yearly_counts = {
            str(year): int(year_count)
            for year, year_count in conn.execute(
                """
                SELECT YEAR(TRY_CAST(date_mutation AS DATE)), COUNT(*)
                FROM mutations_aggregated
                GROUP BY 1
                ORDER BY 1
                """
            ).fetchall()
            if year is not None
        }
        price_by_type = {
            local_type: {
                "mutation_count": int(type_count),
                "median_prix_m2": float(median_price) if median_price is not None else None,
            }
            for local_type, type_count, median_price in conn.execute(
                """
                SELECT type_local, COUNT(*), QUANTILE_CONT(prix_m2, 0.5)
                FROM mutations_aggregated
                GROUP BY 1
                ORDER BY 1
                """
            ).fetchall()
        }
        report["metrics"] = {
            "mutation_count": count,
            "date_range": {
                "min": str(date_range[0]) if date_range[0] else None,
                "max": str(date_range[1]) if date_range[1] else None,
            },
            "commune_count": conn.execute(
                "SELECT COUNT(DISTINCT code_commune) FROM mutations_aggregated"
            ).fetchone()[0],
            "yearly_mutation_counts": yearly_counts,
            "geolocation": {
                "complete": count - missing_coordinates,
                "rate": round((count - missing_coordinates) / count, 4) if count else 0.0,
            },
            "parcel_links": {
                "complete": count - missing_parcel_links,
                "rate": round((count - missing_parcel_links) / count, 4) if count else 0.0,
            },
            "price_per_sqm_by_local_type": price_by_type,
        }
        report["checks"].extend(
            [
                _check("non_empty_dataset", count > 0, count, "> 0 mutations"),
                _check("unique_mutation_ids", duplicate_count == 0, duplicate_count, "0 duplicates"),
                _check("complete_required_values", incomplete_count == 0, incomplete_count, "0 missing values"),
                _check(
                    "valid_transaction_values",
                    invalid_values == 0,
                    invalid_values,
                    f"{SALE_NATURE}, value > {MIN_TRANSACTION_VALUE_EUR}, surface > {MIN_HABITABLE_SURFACE_M2}",
                ),
                _check("valid_mutation_dates", invalid_dates == 0, invalid_dates, "0 invalid dates"),
                _check("valid_prices_per_sqm", invalid_prices == 0, invalid_prices, "0 null or non-positive prices"),
                _check(
                    "valid_geolocation_coordinates",
                    invalid_coordinates == 0,
                    invalid_coordinates,
                    "0 coordinates outside longitude [-180, 180] or latitude [-90, 90]",
                ),
            ]
        )
        if baseline_report_path is not None:
            _compare_with_baseline(report, count, Path(baseline_report_path))
    except duckdb.Error as error:
        report["checks"].append(_check("quality_queries", False, str(error), "quality queries succeed"))
    finally:
        conn.close()

    _write_report(report_path, _complete_report(report))
    return report
