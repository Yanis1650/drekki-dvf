"""Contrat des controles qualite et de la promotion DVF versionnee."""

import json

import duckdb
import pytest
from dvf_promotion import promote_release
from dvf_quality import evaluate_dvf_quality
from run_dvf_pipeline import resolve_baseline_quality_report


def _create_candidate(path, *, duplicate=False, invalid=False):
    path.unlink(missing_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(
        """
        CREATE TABLE mutations_aggregated (
            id_mutation VARCHAR, date_mutation VARCHAR, nature_mutation VARCHAR,
            valeur_fonciere DOUBLE, code_commune VARCHAR, parcelles VARCHAR[],
            surface_habitable_totale DOUBLE, nombre_locaux INTEGER,
            longitude DOUBLE, latitude DOUBLE, type_local VARCHAR, prix_m2 DOUBLE
        )
        """
    )
    second_id = "MUT001" if duplicate else "MUT002"
    second_value = 500.0 if invalid else 180000.0
    conn.execute(
        """
        INSERT INTO mutations_aggregated VALUES
        ('MUT001', '2025-01-15', 'Vente', 250000.0, '35238', ['35238000AB0297'],
         100.0, 1, -1.6778, 48.1173, 'Maison', 2500.0),
        (?, '2024-06-20', 'Vente', ?, '35238', ['35238000AB0298'],
         60.0, 1, -1.6790, 48.1180, 'Appartement', 3000.0)
        """,
        [second_id, second_value],
    )
    conn.close()


def test_quality_report_accepts_a_valid_candidate_and_is_json(tmp_path):
    candidate = tmp_path / "foncier-2026-04-20.duckdb"
    report_path = tmp_path / "foncier-2026-04-20.quality.json"
    _create_candidate(candidate)

    report = evaluate_dvf_quality(candidate, report_path, release="2026-04-20")

    assert report["schema_version"] == 2
    assert report["summary"] == {"passed": True, "total": 10, "failed": 0}
    assert report["metrics"]["mutation_count"] == 2
    assert report["metrics"]["date_range"] == {"min": "2024-06-20", "max": "2025-01-15"}
    assert report["metrics"]["geolocation"]["rate"] == 1.0
    assert report["metrics"]["parcel_links"]["rate"] == 1.0
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_quality_report_lists_dvf_anomalies_without_skipping_the_report(tmp_path):
    candidate = tmp_path / "candidate.duckdb"
    report_path = tmp_path / "quality.json"
    _create_candidate(candidate, duplicate=True, invalid=True)

    report = evaluate_dvf_quality(candidate, report_path)

    assert report["summary"]["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert {"unique_mutation_ids", "valid_transaction_values"} <= failed
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"]["passed"] is False


def test_quality_report_blocks_a_large_regression_against_an_approved_baseline(tmp_path):
    baseline_candidate = tmp_path / "baseline.duckdb"
    baseline_report = tmp_path / "baseline.quality.json"
    candidate = tmp_path / "candidate.duckdb"
    report_path = tmp_path / "candidate.quality.json"
    _create_candidate(baseline_candidate)
    baseline = evaluate_dvf_quality(baseline_candidate, baseline_report, release="2026-01-01")
    assert baseline["summary"]["passed"] is True

    _create_candidate(candidate)
    conn = duckdb.connect(str(candidate))
    conn.execute("DELETE FROM mutations_aggregated WHERE id_mutation = 'MUT002'")
    conn.close()

    report = evaluate_dvf_quality(
        candidate,
        report_path,
        release="2026-02-01",
        baseline_report_path=baseline_report,
    )

    assert report["summary"] == {"passed": False, "total": 11, "failed": 1}
    assert report["comparison"] == {
        "baseline_release": "2026-01-01",
        "baseline_mutation_count": 2,
        "mutation_count_ratio": 0.5,
        "minimum_ratio": 0.75,
    }
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert failed == {"previous_release_volume"}


def test_pipeline_uses_the_current_immutable_quality_report_as_baseline(tmp_path):
    releases = tmp_path / "releases"
    releases.mkdir()
    report = releases / "foncier-2026-01-01.quality.json"
    manifest = releases / "foncier-2026-01-01.release.json"
    report.write_text('{"summary": {"passed": true}}\n', encoding="utf-8")
    manifest.write_text(
        '{"quality_report": "foncier-2026-01-01.quality.json"}\n', encoding="utf-8"
    )
    (releases / "current.json").write_text(
        '{"manifest": "foncier-2026-01-01.release.json"}\n', encoding="utf-8"
    )

    baseline = resolve_baseline_quality_report(None, releases)

    assert baseline == report.resolve()


def test_promotion_keeps_an_immutable_release_and_current_pointer(tmp_path):
    candidate = tmp_path / "candidate.duckdb"
    quality_report = tmp_path / "quality.json"
    source_manifest = tmp_path / "ingestion.json"
    _create_candidate(candidate)
    evaluate_dvf_quality(candidate, quality_report, release="2026-04-20")
    source_manifest.write_text('{"release": "2026-04-20"}\n', encoding="utf-8")

    result = promote_release(
        candidate,
        quality_report,
        release="2026-04-20",
        releases_root=tmp_path / "releases",
        source_manifest=source_manifest,
    )

    assert result.already_promoted is False
    assert result.database_path.name == "foncier-2026-04-20.duckdb"
    assert result.database_path.read_bytes() == candidate.read_bytes()
    pointer = json.loads((tmp_path / "releases" / "current.json").read_text(encoding="utf-8"))
    assert pointer["release"] == "2026-04-20"
    assert pointer["database"] == result.database_path.name
    assert result.manifest_path.is_file()

    repeat = promote_release(
        candidate,
        quality_report,
        release="2026-04-20",
        releases_root=tmp_path / "releases",
        source_manifest=source_manifest,
    )
    assert repeat.already_promoted is True


def test_promotion_refuses_a_failed_or_tampered_candidate(tmp_path):
    candidate = tmp_path / "candidate.duckdb"
    report_path = tmp_path / "quality.json"
    _create_candidate(candidate, invalid=True)
    evaluate_dvf_quality(candidate, report_path)

    with pytest.raises(ValueError, match="qualite"):
        promote_release(candidate, report_path, "2026-04-20", tmp_path / "releases")

    _create_candidate(candidate)
    evaluate_dvf_quality(candidate, report_path)
    candidate.write_bytes(b"modified after validation")

    with pytest.raises(ValueError, match="hash"):
        promote_release(candidate, report_path, "2026-04-20", tmp_path / "releases")
