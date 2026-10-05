"""Acces HTTP a data.gouv, derriere un contrat injectable.

`DvfClient` est le protocole que l'ingestion consomme ; le remplacer par un
double suffit a tester toute la chaine sans trafic reseau.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import requests
from ingestion.dvf_models import (
    DVF_GEOLOCATED_DATASET_URL,
    DownloadReceipt,
    DvfResource,
)


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
