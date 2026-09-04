"""Client data.gouv et ingestion versionnée des DVF géolocalisées.

La source est interrogée via son API de métadonnées, puis chaque ressource est
archivée sans écrasement dans une couche ``raw``. Le manifeste produit par run
est le lien entre les données servies et leur publication d'origine.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

DVF_GEOLOCATED_DATASET_URL = "https://www.data.gouv.fr/api/1/datasets/demandes-de-valeurs-foncieres-geolocalisees/"
MANIFEST_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_component(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._=-]+", "-", value).strip(".-")
    if not safe:
        raise ValueError("Identifiant de release vide ou invalide")
    return safe


@dataclass(frozen=True)
class DvfResource:
    """Ressource tabulaire publiée dans les métadonnées data.gouv."""

    identifier: str
    url: str
    title: str
    format: str | None
    updated_at: str | None
    source_checksum: Any

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> DvfResource:
        url = str(payload.get("url") or "")
        if not url:
            raise ValueError("Une ressource data.gouv ne possède pas d'URL")
        identifier = str(payload.get("id") or hashlib.sha256(url.encode()).hexdigest()[:12])
        return cls(
            identifier=identifier,
            url=url,
            title=str(payload.get("title") or payload.get("name") or identifier),
            format=str(payload["format"]).lower() if payload.get("format") else None,
            updated_at=payload.get("last_modified") or payload.get("created_at"),
            source_checksum=payload.get("checksum"),
        )

    @property
    def year(self) -> str | None:
        match = re.search(r"(?:19|20)\d{2}", f"{self.title} {self.url}")
        return match.group(0) if match else None

    @property
    def filename(self) -> str:
        source_name = Path(urlparse(self.url).path).name or self.identifier
        source_name = _safe_component(source_name)
        return f"{self.year or 'all'}-{self.identifier[:12]}-{source_name}"

    @property
    def fingerprint(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "url": self.url,
            "updated_at": self.updated_at,
            "checksum": self.source_checksum,
        }


@dataclass(frozen=True)
class DownloadReceipt:
    """Trace minimale du téléchargement d'une ressource."""

    sha256: str
    size_bytes: int
    etag: str | None


@dataclass(frozen=True)
class IngestionResult:
    """Artefacts produits par une ingestion DVF."""

    release: str
    run_id: str
    manifest_path: Path
    resource_paths: tuple[Path, ...]


class DvfClient(Protocol):
    """Contrat injectable pour tester l'ingestion sans trafic réseau."""

    dataset_url: str

    def fetch_dataset(self) -> dict[str, Any]: ...

    def data_resources(self, dataset: dict[str, Any]) -> list[DvfResource]: ...

    def download(self, resource: DvfResource, destination: Path) -> DownloadReceipt: ...


class DataGouvDvfClient:
    """Accès HTTP résilient aux métadonnées et fichiers DVF géolocalisés."""

    def __init__(
        self,
        dataset_url: str = DVF_GEOLOCATED_DATASET_URL,
        timeout_seconds: int = 90,
        session: requests.Session | None = None,
    ) -> None:
        self.dataset_url = dataset_url
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def fetch_dataset(self) -> dict[str, Any]:
        response = self._session.get(self.dataset_url, timeout=self._timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("resources"), list):
            raise ValueError("Contrat data.gouv invalide : champ resources absent")
        return payload

    def data_resources(self, dataset: dict[str, Any]) -> list[DvfResource]:
        resources = [DvfResource.from_payload(item) for item in dataset["resources"]]
        tabular = [resource for resource in resources if self._is_tabular(resource)]
        if not tabular:
            raise ValueError("Aucune ressource DVF tabulaire trouvée dans les métadonnées data.gouv")
        return sorted(tabular, key=lambda resource: (resource.year or "", resource.identifier))

    @staticmethod
    def _is_tabular(resource: DvfResource) -> bool:
        suffixes = Path(urlparse(resource.url).path).suffixes
        extension = "".join(suffixes).lower()
        return resource.format in {"csv", "txt"} or extension.endswith((".csv", ".csv.gz", ".txt", ".txt.gz"))

    def download(self, resource: DvfResource, destination: Path) -> DownloadReceipt:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.part")
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with self._session.get(resource.url, stream=True, timeout=self._timeout_seconds) as response:
                response.raise_for_status()
                etag = response.headers.get("ETag")
                with temporary.open("wb") as target:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            target.write(chunk)
                            digest.update(chunk)
                            size_bytes += len(chunk)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return DownloadReceipt(sha256=digest.hexdigest(), size_bytes=size_bytes, etag=etag)


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
