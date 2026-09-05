"""Tests du téléchargement DVF versionné, sans appel réseau réel."""

import json
from pathlib import Path

from ingestion.dvf import (
    DataGouvDvfClient,
    DownloadReceipt,
    DvfIngestionService,
    DvfResource,
)


class StubDvfClient:
    """Double de test : écrit un CSV déterministe à la place d'un téléchargement."""

    dataset_url = "https://example.test/api/datasets/dvf"

    def __init__(self) -> None:
        self.download_calls = 0

    def fetch_dataset(self) -> dict:
        return {
            "id": "dvf-geoloc-test",
            "title": "DVF géolocalisées",
            "last_modified": "2026-04-20T09:00:00+00:00",
        }

    def data_resources(self, dataset: dict) -> list[DvfResource]:
        return [
            DvfResource(
                identifier="resource-2025",
                url="https://example.test/dvf/full_2025.csv.gz",
                title="DVF géolocalisées 2025",
                format="csv",
                updated_at="2026-04-20T09:00:00+00:00",
                source_checksum={"type": "sha256", "value": "source-checksum"},
            )
        ]

    def download(self, resource: DvfResource, destination: Path) -> DownloadReceipt:
        self.download_calls += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"id_mutation,date_mutation\nM1,2025-01-01\n")
        return DownloadReceipt(
            sha256="ef4578dfac93c22e4546f4639f97b38e1b9eecf4ecce4a770105eabaf803fa42",
            size_bytes=40,
            etag='"example-etag"',
        )


def test_data_gouv_client_keeps_tabular_resources_only():
    client = DataGouvDvfClient(session=object())  # session inutilisée par data_resources
    resources = client.data_resources(
        {
            "resources": [
                {
                    "id": "csv-2025",
                    "url": "https://example.test/dvf-2025.csv.gz",
                    "title": "DVF 2025",
                    "format": "csv",
                },
                {
                    "id": "notice",
                    "url": "https://example.test/notice.pdf",
                    "title": "Notice DVF",
                    "format": "pdf",
                },
            ]
        }
    )

    assert len(resources) == 1
    assert resources[0].identifier == "csv-2025"
    assert resources[0].year == "2025"


def test_ingestion_writes_a_provenance_manifest_and_reuses_cache(tmp_path):
    client = StubDvfClient()
    service = DvfIngestionService(client, tmp_path / "raw")

    first = service.ingest()
    assert client.download_calls == 1
    assert first.release == "2026-04-20"
    assert first.manifest_path.is_file()
    assert len(first.resource_paths) == 1

    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["source"]["dataset_id"] == "dvf-geoloc-test"
    assert manifest["resources"][0]["status"] == "downloaded"
    assert manifest["resources"][0]["year"] == "2025"
    assert manifest["resources"][0]["local_path"].startswith("resources/")

    second = service.ingest()
    assert client.download_calls == 1
    assert second.resource_paths == first.resource_paths
    cached = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    assert cached["resources"][0]["status"] == "cached"
    assert cached["summary"] == {"total": 1, "downloaded": 0, "cached": 1}


def test_dry_run_does_not_write_a_manifest_or_download(tmp_path):
    client = StubDvfClient()
    result = DvfIngestionService(client, tmp_path / "raw").ingest(dry_run=True)

    assert client.download_calls == 0
    assert not result.manifest_path.exists()
    assert result.resource_paths == ()
