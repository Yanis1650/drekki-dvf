"""Point d'entrée DVF de bout en bout : ingestion versionnée puis DuckDB."""

from __future__ import annotations

import argparse
from pathlib import Path

from dvf_promotion import promote_release
from dvf_quality import evaluate_dvf_quality
from ingestion import DataGouvDvfClient, DvfIngestionService
from run_etl import run_dvf_etl

ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline DVF canonique Foncier Express")
    parser.add_argument("--release", help="Identifiant de release, ex. 2026-04-20")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument(
        "--output",
        type=Path,
        help="Base DuckDB candidate. Par défaut : data/candidates/foncier-<release>.duckdb",
    )
    parser.add_argument(
        "--quality-report",
        type=Path,
        help="Rapport JSON. Par défaut : voisin de la candidate avec suffixe .quality.json",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Archive la candidate validee dans data/releases et actualise le pointeur current.json",
    )
    parser.add_argument(
        "--releases-root",
        type=Path,
        default=ROOT / "data" / "releases",
        help="Repertoire des releases immuables (defaut : data/releases)",
    )
    parser.add_argument("--dataset-url", help="Endpoint API data.gouv à utiliser")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = DataGouvDvfClient(dataset_url=args.dataset_url) if args.dataset_url else DataGouvDvfClient()
    ingestion = DvfIngestionService(client, args.raw_root).ingest(args.release)
    output = args.output or ROOT / "data" / "candidates" / f"foncier-{ingestion.release}.duckdb"
    supported = [
        path for path in ingestion.resource_paths if "".join(path.suffixes).lower().endswith((".csv", ".csv.gz"))
    ]
    if not supported:
        raise ValueError("La release téléchargée ne contient pas de CSV exploitable par le pipeline canonique")
    mutations = run_dvf_etl(input_files=supported, output_path=output)
    quality_report = args.quality_report or output.with_suffix(".quality.json")
    quality = evaluate_dvf_quality(output, quality_report, ingestion.release)
    print(f"release={ingestion.release} mutations={mutations} output={output}")
    print(f"manifest={ingestion.manifest_path}")
    print(f"quality_report={quality_report} passed={quality['summary']['passed']}")
    if not quality["summary"]["passed"]:
        raise SystemExit("Candidate DVF non promue : controles qualite en echec")
    if args.promote:
        promotion = promote_release(
            output,
            quality_report,
            ingestion.release,
            args.releases_root,
            source_manifest=ingestion.manifest_path,
        )
        print(
            f"promoted_release={promotion.database_path} "
            f"already_promoted={promotion.already_promoted}"
        )


if __name__ == "__main__":
    main()
