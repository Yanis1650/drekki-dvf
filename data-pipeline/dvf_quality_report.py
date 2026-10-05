"""Ossature du rapport qualite : redaction, verdicts, comparaison au precedent.

Aucune connaissance du schema DVF ici — seulement la forme du rapport et la
regle de non-regression de volume entre deux releases.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = 2
MIN_MUTATION_COUNT_RATIO = 0.75


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
