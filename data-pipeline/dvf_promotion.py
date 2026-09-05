"""Promotion atomique d'une candidate DVF validee vers une release immuable."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_release(release: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "-", release).strip(".-")
    if not safe:
        raise ValueError("Identifiant de release vide ou invalide")
    return safe


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Rapport JSON invalide : {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Rapport JSON invalide : {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _copy_immutable(source: Path, destination: Path) -> bool:
    if destination.exists():
        if _sha256(source) != _sha256(destination):
            raise ValueError(f"La release existe deja avec un contenu different : {destination.name}")
        return True
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return False


@dataclass(frozen=True)
class PromotionResult:
    """Artefacts d'une promotion DVF."""

    database_path: Path
    manifest_path: Path
    already_promoted: bool


def promote_release(
    candidate_path: Path,
    quality_report_path: Path,
    release: str,
    releases_root: Path,
    source_manifest: Path | None = None,
) -> PromotionResult:
    """Archive une candidate qualifiee et positionne le pointeur ``current``."""
    candidate = Path(candidate_path)
    quality_report = _read_json(Path(quality_report_path))
    if quality_report.get("summary", {}).get("passed") is not True:
        raise ValueError("La qualite DVF doit etre validee avant promotion")
    expected_hash = quality_report.get("database", {}).get("sha256")
    if not candidate.is_file() or expected_hash != _sha256(candidate):
        raise ValueError("Le hash de la candidate ne correspond pas au rapport qualite")

    release_id = _safe_release(release)
    report_release = quality_report.get("release")
    if report_release is not None and _safe_release(str(report_release)) != release_id:
        raise ValueError("Le rapport qualite ne correspond pas a la release a promouvoir")
    source = Path(source_manifest) if source_manifest else None
    if source and not source.is_file():
        raise ValueError(f"Manifeste d'ingestion introuvable : {source}")

    root = Path(releases_root)
    root.mkdir(parents=True, exist_ok=True)
    database = root / f"foncier-{release_id}.duckdb"
    promoted_before = _copy_immutable(candidate, database)
    immutable_report = root / f"foncier-{release_id}.quality.json"
    immutable_source = None
    if source:
        immutable_source = root / f"foncier-{release_id}.ingestion.json"
    manifest_path = root / f"foncier-{release_id}.release.json"
    if promoted_before:
        required = [immutable_report, manifest_path]
        if immutable_source:
            required.append(immutable_source)
        if any(not path.is_file() for path in required):
            raise ValueError(f"Release existante incomplete : {release_id}")
    else:
        _copy_immutable(Path(quality_report_path), immutable_report)
        if source and immutable_source:
            _copy_immutable(source, immutable_source)
        _write_json(
            manifest_path,
            {
                "schema_version": 1,
                "release": release_id,
                "promoted_at": datetime.now(UTC).isoformat(),
                "database": {"path": database.name, "sha256": _sha256(database)},
                "quality_report": immutable_report.name,
                "ingestion_manifest": immutable_source.name if immutable_source else None,
            },
        )
    _write_json(
        root / "current.json",
        {"release": release_id, "database": database.name, "manifest": manifest_path.name},
    )
    return PromotionResult(database, manifest_path, promoted_before)
