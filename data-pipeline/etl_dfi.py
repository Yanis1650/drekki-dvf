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
import polars as pl

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

        # Convert to Polars DataFrame for efficient loading
        df = pl.DataFrame(filiations)

        logger.info(f"Loading {len(df)} filiations to DuckDB: {self._output_path}")

        conn = duckdb.connect(str(self._output_path))
        try:
            # Create table if not exists
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

            # Register DataFrame and insert
            conn.register("filiations_df", df)
            conn.execute("""
                INSERT INTO dfi_filiations
                SELECT * FROM filiations_df
            """)

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


def run_dfi_etl_all_departments(dfi_dir: Path | str) -> None:
    """Process all DFI files in a directory.
    
    Args:
        dfi_dir: Directory containing DFI subdirectories
    """
    dfi_dir = Path(dfi_dir)
    pipeline = DFIEtlPipeline()

    # Find all DFI files (pattern: dfiano-dep*.txt/dfiano-dep*.txt)
    dfi_files = list(dfi_dir.glob("dfiano-dep*/dfiano-dep*.txt"))

    logger.info(f"Found {len(dfi_files)} DFI files to process")

    total_filiations = 0
    for dfi_file in sorted(dfi_files):
        try:
            count = pipeline.run(dfi_file)
            total_filiations += count
        except Exception as e:
            logger.error(f"Failed to process {dfi_file.name}: {e}")
            continue

    logger.info(f"✓ Total filiations processed: {total_filiations:,}")


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) < 2:
        print("Usage: python etl_dfi.py <dfi_file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_dir():
        run_dfi_etl_all_departments(path)
    else:
        pipeline = DFIEtlPipeline()
        pipeline.run(path)
