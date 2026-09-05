"""Télécharge et versionne une publication DVF géolocalisée depuis data.gouv."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from ingestion import DataGouvDvfClient, DvfIngestionService

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingestion versionnée des DVF géolocalisées")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--release", help="Identifiant de release, ex. 2026-04-20")
    parser.add_argument("--dataset-url", help="Endpoint API data.gouv à utiliser")
    parser.add_argument("--dry-run", action="store_true", help="Liste les ressources sans écrire de fichier")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    client = DataGouvDvfClient(dataset_url=args.dataset_url) if args.dataset_url else DataGouvDvfClient()
    result = DvfIngestionService(client, args.raw_root).ingest(args.release, args.dry_run)
    print(f"release={result.release} run_id={result.run_id}")
    if args.dry_run:
        print("dry-run : aucune ressource n'a été écrite")
    else:
        print(f"manifest={result.manifest_path}")
        print(f"resources={len(result.resource_paths)}")


if __name__ == "__main__":
    main()
