"""Ressources data.gouv et artefacts d'ingestion DVF.

Types et utilitaires purs, sans acces reseau ni ecriture : ils decrivent ce
que la source publie et ce qu'une ingestion produit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
