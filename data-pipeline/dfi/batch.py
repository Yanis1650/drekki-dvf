"""Traitement en lot : un departement, un dossier, ou des archives ZIP.

`DFIEtlPipeline` est importe a l'appel et non en tete de module : ce paquet
est importe par `etl_dfi`, l'importer en retour ferait un cycle.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:  # pragma: no cover - annotation seule, pas d'import au runtime
    from etl_dfi import DFIEtlPipeline

logger = logging.getLogger(__name__)


def run_dfi_etl_all_departments(
    dfi_dir: Path | str,
    dept_filter: str | None = None,
    replace: bool = False,
    output_path: Path | str | None = None,
) -> None:
    """Process all DFI files in a directory.

    Args:
        dfi_dir: Directory containing DFI subdirectories (dfiano-depXXX-date.txt/)
        dept_filter: Optional dept code to load only (e.g. "035" for 35)
        replace: If True, truncate table before loading
        output_path: DuckDB output path (default: data/foncier.duckdb)
    """
    from etl_dfi import DFIEtlPipeline

    dfi_dir = Path(dfi_dir)
    if not dfi_dir.exists():
        raise FileNotFoundError(f"DFI directory not found: {dfi_dir}")

    pipeline = DFIEtlPipeline(output_path=output_path or "./data/foncier.duckdb")

    # Pattern: dfiano-dep035-19012025.txt/dfiano-dep035-19012025.txt
    dfi_files = sorted(dfi_dir.glob("dfiano-dep*/dfiano-dep*.txt"))

    if dept_filter:
        # Support dep035, dep35, dep350 (archives utilisent parfois dep350 pour dept 35)
        dept_clean = dept_filter.strip().upper().replace("2A", "2A0").replace("2B", "2B0")
        patterns = [
            f"dep{dept_clean.zfill(3)}",   # 35 -> dep035
            f"dep{dept_clean.lstrip('0') or '0'}",  # 35 -> dep35
            f"dep{dept_clean}0" if len(dept_clean) == 2 else "",  # 35 -> dep350
        ]
        patterns = [p for p in patterns if p]
        dfi_files = [f for f in dfi_files if any(p in f.as_posix() for p in patterns)]
        logger.info(f"Filtering dept {dept_filter}: {len(dfi_files)} files")

    logger.info(f"Found {len(dfi_files)} DFI files to process")

    if replace and dfi_files:
        _truncate_dfi_table(pipeline._output_path)

    total_filiations = 0
    for dfi_file in dfi_files:
        try:
            count = pipeline.run(dfi_file)
            total_filiations += count
        except Exception as e:
            logger.error(f"Failed to process {dfi_file.name}: {e}")
            continue

    logger.info(f"Total filiations processed: {total_filiations:,}")


def _truncate_dfi_table(db_path: Path) -> None:
    """Truncate dfi_filiations table."""
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("DROP TABLE IF EXISTS dfi_filiations")
        logger.info("Table dfi_filiations truncated")
    finally:
        conn.close()


def _run_from_zip(zip_path: Path, pipeline: "DFIEtlPipeline") -> int:
    """Extract and process a single DFI ZIP file."""
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".txt"):
                    zf.extract(name, tmp)
                    txt_path = Path(tmp) / name
                    return pipeline.run(txt_path)
    return 0


def run_dfi_etl_from_zips(
    backup_dir: Path | str,
    dept_filter: str | None = None,
    replace: bool = False,
    output_path: Path | str | None = None,
) -> None:
    """Process DFI from data_backup/*.txt.zip files.

    Args:
        backup_dir: Directory containing dfiano-dep*-date.txt.zip
        dept_filter: Optional dept (e.g. "35" or "035")
        replace: Truncate before load
        output_path: DuckDB output path (default: data/foncier.duckdb)
    """
    from etl_dfi import DFIEtlPipeline

    backup_dir = Path(backup_dir)
    zip_files = sorted(backup_dir.glob("dfiano-dep*.txt.zip"))
    if dept_filter:
        dept_norm = dept_filter.zfill(3)
        zip_files = [f for f in zip_files if f"dep{dept_norm}" in f.name]

    if not zip_files:
        logger.warning(f"No ZIP files found in {backup_dir}")
        return

    pipeline = DFIEtlPipeline(output_path=output_path or "./data/foncier.duckdb")
    if replace:
        _truncate_dfi_table(pipeline._output_path)

    total = 0
    for z in zip_files:
        try:
            total += _run_from_zip(z, pipeline)
        except Exception as e:
            logger.error(f"Failed {z.name}: {e}")
    logger.info(f"Total from ZIPs: {total:,}")
