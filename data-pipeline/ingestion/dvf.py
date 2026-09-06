"""Client data.gouv et ingestion versionnée des DVF géolocalisées.

La source est interrogée via son API de métadonnées, puis chaque ressource est
archivée sans écrasement dans une couche ``raw``. Le manifeste produit par run
est le lien entre les données servies et leur publication d'origine.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from ingestion.dvf_client import DataGouvDvfClient, DvfClient
from ingestion.dvf_models import (
    DVF_GEOLOCATED_DATASET_URL,
    MANIFEST_SCHEMA_VERSION,
    DownloadReceipt,
    DvfResource,
    IngestionResult,
    _safe_component,
    _sha256,
    _utc_now,
)

__all__ = [
    "DVF_GEOLOCATED_DATASET_URL",
    "DataGouvDvfClient",
    "DownloadReceipt",
    "DvfClient",
    "DvfIngestionService",
    "DvfResource",
    "IngestionResult",
]


class DvfIngestionService:
    """Archive une publication DVF et écrit son manifeste de provenance."""

    def __init__(self, client: DvfClient, raw_root: Path) -> None:
        self._client = client
        self._raw_root = raw_root

    def ingest(self, release: str | None = None, dry_run: bool = False) -> IngestionResult:
        dataset = self._client.fetch_dataset()
        resources = self._client.data_resources(dataset)
        release_id = _safe_component(release or self._release_from_dataset(dataset))
        run_id = str(uuid.uuid4())
        run_dir = self._raw_root / "dvf-geolocated" / f"release={release_id}"
        manifest_path = run_dir / "run_manifest.json"
        previous = self._read_manifest(manifest_path)
        entries: list[dict[str, Any]] = []
        resource_paths: list[Path] = []

        for resource in resources:
            relative_path = Path("resources") / resource.filename
            target = run_dir / relative_path
            cached = self._cached_entry(previous, resource, target)
            if cached:
                entry = {**cached, "status": "cached"}
            elif dry_run:
                entry = self._entry(resource, relative_path, status="planned")
            else:
                receipt = self._client.download(resource, target)
                entry = self._entry(
                    resource,
                    relative_path,
                    status="downloaded",
                    sha256=receipt.sha256,
                    size_bytes=receipt.size_bytes,
                    etag=receipt.etag,
                )
            entries.append(entry)
            if entry["status"] != "planned":
                resource_paths.append(target)

        if not dry_run:
            manifest = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "run_id": run_id,
                "release": release_id,
                "created_at": _utc_now(),
                "source": {
                    "dataset_url": self._client.dataset_url,
                    "dataset_id": dataset.get("id"),
                    "dataset_title": dataset.get("title"),
                    "dataset_last_modified": dataset.get("last_modified"),
                },
                "resources": entries,
                "summary": {
                    "total": len(entries),
                    "downloaded": sum(entry["status"] == "downloaded" for entry in entries),
                    "cached": sum(entry["status"] == "cached" for entry in entries),
                },
            }
            self._write_manifest(manifest_path, manifest)
        return IngestionResult(release_id, run_id, manifest_path, tuple(resource_paths))

    @staticmethod
    def _release_from_dataset(dataset: dict[str, Any]) -> str:
        return str(dataset.get("last_modified") or dataset.get("created_at") or "unknown")[:10]

    @staticmethod
    def _entry(
        resource: DvfResource,
        relative_path: Path,
        status: str,
        sha256: str | None = None,
        size_bytes: int | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        return {
            "resource": resource.fingerprint,
            "title": resource.title,
            "year": resource.year,
            "local_path": relative_path.as_posix(),
            "status": status,
            "sha256": sha256,
            "size_bytes": size_bytes,
            "etag": etag,
        }

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            with path.open(encoding="utf-8") as source:
                payload = json.load(source)
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _cached_entry(previous: dict[str, Any], resource: DvfResource, target: Path) -> dict[str, Any] | None:
        for entry in previous.get("resources", []):
            if entry.get("resource") != resource.fingerprint or not target.is_file():
                continue
            if entry.get("sha256") and entry["sha256"] == _sha256(target):
                return entry
        return None

    @staticmethod
    def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
