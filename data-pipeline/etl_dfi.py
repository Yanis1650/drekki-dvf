"""ETL Pipeline for DFI (Documents de Filiation Informatisés).

Ingests parcel filiation data from TXT files into DuckDB.
Handles paired lines (type 1=mothers, type 2=daughters) and denormalizes
the 175 max parcel cells into individual relationships.

Memory constraint: Uses streaming to avoid loading entire files.
"""

import logging
from datetime import datetime
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


class DFIEtlPipeline:
    """ETL pipeline for DFI parcel filiation data."""

    def __init__(self, output_path: Path | str = "./data/foncier.duckdb") -> None:
        self._output_path = Path(output_path)

    def parse_dfi_line(self, line: str) -> dict | None:
        """Parse a single DFI line according to fixed format.

        Format: dept;commune;prefixe;id_dfi;nature;date;geometre;placeholder;lot;type;parcelles...
        Note: geometre field may contain spaces/newlines, placeholder is "XNUMX"

        Args:
            line: Raw line from DFI file

        Returns:
            Parsed dict or None if invalid
        """
        # Skip empty lines or lines with only whitespace
        if not line.strip():
            return None

        parts = line.split(";")

        # Need at least 10 fields (up to type field)
        if len(parts) < 10:
            logger.warning(f"Invalid DFI line (too few fields: {len(parts)}): {line[:80]}")
            return None

        try:
            # Parse date (format: YYYYMMDD)
            date_str = parts[5].strip()
            if len(date_str) == 8:
                date_validation = datetime.strptime(date_str, "%Y%m%d").date()
            else:
                logger.warning(f"Invalid date format: {date_str}")
                return None

            # Field 7 is placeholder "XNUMX", field 8 is real lot number
            numero_lot = parts[8].strip()

            # Field 9 is type (1 or 2)
            type_ligne = parts[9].strip()

            # Extract parcels (from field 10 onwards, max 175 cells)
            parcelles = []
            for p in parts[10:]:
                p_clean = p.strip()
                # Valid parcel: 2-6 chars (section + number, ex: "AC0026" or "A1200")
                if p_clean and 2 <= len(p_clean) <= 6:
                    parcelles.append(p_clean)

            return {
                "code_departement": parts[0].strip(),
                "code_commune": parts[1].strip(),
                "prefixe": parts[2].strip(),
                "id_dfi": parts[3].strip(),
                "nature_dfi": parts[4].strip(),
                "date_validation": date_validation,
                "numero_lot": numero_lot,
                "type_ligne": type_ligne,
                "parcelles": parcelles,
            }
        except Exception as e:
            logger.error(f"Error parsing DFI line: {e}, line: {line[:80]}")
            return None

    def process_dfi_file(self, file_path: Path) -> list[dict]:
        """Process a complete DFI file into mother-daughter relationships.

        DFI files have paired lines:
        - Line type 1: mother parcels
        - Line type 2: daughter parcels

        We create a cartesian product: each mother × each daughter.

        Args:
            file_path: Path to DFI TXT file

        Returns:
            List of filiation records
        """
        logger.info(f"Processing DFI file: {file_path}")

        filiations = []
        buffer = []

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                parsed = self.parse_dfi_line(line)
                if not parsed:
                    continue

                buffer.append(parsed)

                # Process paired lines (type 1 + type 2)
                if len(buffer) == 2:
                    line1, line2 = buffer

                    # Validate it's a proper pair
                    if (
                        line1["id_dfi"] == line2["id_dfi"]
                        and line1["numero_lot"] == line2["numero_lot"]
                    ):
                        # Determine which is mothers and which is daughters
                        if line1["type_ligne"] == "1" and line2["type_ligne"] == "2":
                            mothers = line1["parcelles"]
                            daughters = line2["parcelles"]
                        elif line1["type_ligne"] == "2" and line2["type_ligne"] == "1":
                            mothers = line2["parcelles"]
                            daughters = line1["parcelles"]
                        else:
                            logger.warning(f"Invalid pair types: {line1['type_ligne']}, {line2['type_ligne']}")
                            buffer = []
                            continue

                        # Cartesian product: mothers × daughters
                        for mother in mothers:
                            for daughter in daughters:
                                filiations.append({
                                    "code_departement": line1["code_departement"],
                                    "code_commune": line1["code_commune"],
                                    "prefixe": line1["prefixe"],
                                    "id_dfi": line1["id_dfi"],
                                    "nature_dfi": line1["nature_dfi"],
                                    "date_validation": line1["date_validation"],
                                    "numero_lot": line1["numero_lot"],
                                    "parcelle_mere": mother,
                                    "parcelle_fille": daughter,
                                })
                    else:
                        logger.warning(f"Mismatched pair at line {line_num}")

                    buffer = []

        logger.info(f"Extracted {len(filiations)} filiation relationships")
        return filiations

    def load_to_duckdb(self, filiations: list[dict]) -> None:
        """Load filiation data into DuckDB.

        Creates table with composite index for fast lookups.

        Args:
            filiations: List of filiation records
        """
        if not filiations:
            logger.warning("No filiations to load")
            return

        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Loading {len(filiations):,} filiations to DuckDB: {self._output_path}")

        conn = duckdb.connect(str(self._output_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dfi_filiations (
                    code_departement VARCHAR(3),
                    code_commune VARCHAR(3),
                    prefixe VARCHAR(3),
                    id_dfi VARCHAR(7),
                    nature_dfi VARCHAR(1),
                    date_validation DATE,
                    numero_lot VARCHAR(5),
                    parcelle_mere VARCHAR(6),
                    parcelle_fille VARCHAR(6)
                )
            """)

            # Insert par lots pour eviter les limites memoire
            batch_size = 50_000
            for i in range(0, len(filiations), batch_size):
                batch = filiations[i : i + batch_size]
                rows = [
                    (
                        r["code_departement"],
                        r["code_commune"],
                        r["prefixe"],
                        r["id_dfi"],
                        r["nature_dfi"],
                        r["date_validation"],
                        r["numero_lot"],
                        r["parcelle_mere"],
                        r["parcelle_fille"],
                    )
                    for r in batch
                ]
                conn.executemany(
                    """INSERT INTO dfi_filiations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                if (i + batch_size) % 100_000 == 0 or i + batch_size >= len(filiations):
                    logger.info(f"  Inserted {min(i + batch_size, len(filiations)):,} rows")

            # Create composite indexes for fast lookups
            logger.info("Creating indexes...")

            # Index for finding mothers (query by daughter)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dfi_fille
                ON dfi_filiations(code_commune, parcelle_fille)
            """)

            # Index for finding daughters (query by mother)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dfi_mere
                ON dfi_filiations(code_commune, parcelle_mere)
            """)

            # Verify
            count = conn.execute("SELECT COUNT(*) FROM dfi_filiations").fetchone()[0]
            logger.info(f"✓ Loaded {count:,} filiation relationships to DuckDB")

        finally:
            conn.close()

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


def _run_from_zip(zip_path: Path, pipeline: DFIEtlPipeline) -> int:
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
) -> None:
    """Process DFI from data_backup/*.txt.zip files.

    Args:
        backup_dir: Directory containing dfiano-dep*-date.txt.zip
        dept_filter: Optional dept (e.g. "35" or "035")
        replace: Truncate before load
    """
    backup_dir = Path(backup_dir)
    zip_files = sorted(backup_dir.glob("dfiano-dep*.txt.zip"))
    if dept_filter:
        dept_norm = dept_filter.zfill(3)
        zip_files = [f for f in zip_files if f"dep{dept_norm}" in f.name]

    if not zip_files:
        logger.warning(f"No ZIP files found in {backup_dir}")
        return

    pipeline = DFIEtlPipeline()
    if replace:
        _truncate_dfi_table(pipeline._output_path)

    total = 0
    for z in zip_files:
        try:
            total += _run_from_zip(z, pipeline)
        except Exception as e:
            logger.error(f"Failed {z.name}: {e}")
    logger.info(f"Total from ZIPs: {total:,}")


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

    args = parser.parse_args()
    path = Path(args.path)

    if not path.exists():
        print(f"Error: {path} does not exist")
        exit(1)

    if args.from_zips:
        run_dfi_etl_from_zips(path, dept_filter=args.dept, replace=args.replace)
    elif path.is_dir():
        run_dfi_etl_all_departments(path, dept_filter=args.dept, replace=args.replace)
    else:
        pipeline = DFIEtlPipeline()
        pipeline.run(path)
