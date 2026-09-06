"""ETL Pipeline for DFI (Documents de Filiation Informatisés).

Ingests parcel filiation data from TXT files into DuckDB.
Handles paired lines (type 1=mothers, type 2=daughters) and denormalizes
the 175 max parcel cells into individual relationships.

Memory constraint: Uses streaming to avoid loading entire files.

La lecture du format vit dans `dfi/parsing.py`, l'ecriture dans
`dfi/loading.py`, et les traitements en lot dans `dfi/batch.py`. Ce module
garde la classe, son enchainement, et la ligne de commande.
"""

import logging
from pathlib import Path

import duckdb
from dfi import (
    DfiLoadingMixin,
    DfiParsingMixin,
    run_dfi_etl_all_departments,
    run_dfi_etl_from_zips,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DFIEtlPipeline",
    "run_dfi_etl_all_departments",
    "run_dfi_etl_from_zips",
]


class DFIEtlPipeline(DfiParsingMixin, DfiLoadingMixin):
    """ETL pipeline for DFI parcel filiation data."""

    def __init__(
        self,
        output_path: Path | str = "./data/foncier.duckdb",
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        """
        Args:
            output_path: base DuckDB cible, ouverte à la demande.
            conn: connexion déjà ouverte à réutiliser. Indispensable quand le
                pipeline tourne au sein d'`etl_build_dept.py` : DuckDB refuse
                une seconde connexion au même fichier depuis le même processus
                (« Can't open a connection to same database file »).
        """
        self._output_path = Path(output_path)
        self._conn = conn

    def run(self, dfi_path: Path | str) -> int:
        """Execute full ETL pipeline for a DFI file.

        Args:
            dfi_path: Path to DFI TXT file

        Returns:
            Number of filiation relationships processed
        """
        path = Path(dfi_path)

        if not path.exists():
            raise FileNotFoundError(f"DFI file not found: {path}")

        logger.info(f"Starting DFI ETL pipeline: {path.name}")

        # Extract
        filiations = self.process_dfi_file(path)

        # Load
        self.load_to_duckdb(filiations)

        logger.info("DFI ETL complete!")
        return len(filiations)


# Chemin par defaut des DFI (structure cadastre.gouv.fr janvier 2025)
def _find_default_dfi_dir() -> Path:
    """Recherche le dossier DFI dans data/ (evite problemes d'encodage du nom)."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    if not data_dir.exists():
        return data_dir / "Documents de filiation informatisés (situation janvier 2025) - dept 2A0 à dept 580"
    for d in data_dir.iterdir():
        if d.is_dir() and "filiation" in d.name.lower() and "dept" in d.name.lower():
            return d
    return data_dir / "Documents de filiation informatisés (situation janvier 2025) - dept 2A0 à dept 580"


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="ETL DFI (Documents de Filiation Informatisés) -> DuckDB"
    )
    default_dir = _find_default_dfi_dir()
    parser.add_argument(
        "path",
        nargs="?",
        default=str(default_dir),
        help="File, directory or ZIP folder (default: auto-detect in data/)",
    )
    parser.add_argument(
        "--dept",
        metavar="XX",
        help="Load only this department (e.g. 35 for Ille-et-Vilaine)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate dfi_filiations before loading",
    )
    parser.add_argument(
        "--from-zips",
        action="store_true",
        help="Use data_backup/*.zip instead of extracted folders",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="Base DuckDB cible (defaut: data/foncier.duckdb). "
             "Utiliser data/dept35.duckdb pour alimenter la base servie par l'API.",
    )

    args = parser.parse_args()
    path = Path(args.path)

    if not path.exists():
        print(f"Error: {path} does not exist")
        exit(1)

    if args.from_zips:
        run_dfi_etl_from_zips(
            path, dept_filter=args.dept, replace=args.replace, output_path=args.db
        )
    elif path.is_dir():
        run_dfi_etl_all_departments(
            path, dept_filter=args.dept, replace=args.replace, output_path=args.db
        )
    else:
        pipeline = DFIEtlPipeline(output_path=args.db or "./data/foncier.duckdb")
        pipeline.run(path)
