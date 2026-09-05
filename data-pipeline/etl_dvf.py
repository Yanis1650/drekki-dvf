"""Adaptateur historique du pipeline DVF.

Le point d'entrée de référence est désormais ``run_dvf_pipeline.py`` puis
``run_etl.py``. Cette classe est conservée temporairement pour les imports
existants, mais ne doit plus être utilisée pour créer une nouvelle base.
"""

import logging
import warnings
from pathlib import Path

import duckdb
import polars as pl

from app.services.cleaning_strategies import ICleaningStrategy, MericskayStrategy

logger = logging.getLogger(__name__)


class DvfEtlPipeline:
    """ETL pipeline for DVF data.

    Reads raw DVF CSV files, applies cleaning strategy,
    and writes to DuckDB with spatial indexing.
    """

    # DVF columns mapping (subset of official DVF schema)
    DVF_SCHEMA = {
        "id_mutation": pl.Utf8,
        "date_mutation": pl.Date,
        "nature_mutation": pl.Utf8,
        "valeur_fonciere": pl.Float64,
        "code_postal": pl.Utf8,
        "code_commune": pl.Utf8,
        "code_departement": pl.Utf8,
        "id_parcelle": pl.Utf8,
        "type_local": pl.Utf8,
        "surface_reelle_bati": pl.Float64,
        "nombre_pieces_principales": pl.Int32,
        "surface_terrain": pl.Float64,
        "longitude": pl.Float64,
        "latitude": pl.Float64,
    }

    def __init__(
        self,
        strategy: ICleaningStrategy | None = None,
        output_path: Path | str = "./data/foncier.duckdb",
    ) -> None:
        self._strategy = strategy or MericskayStrategy()
        self._output_path = Path(output_path)

    def extract(self, dvf_path: Path | str) -> pl.LazyFrame:
        """Extract DVF data from CSV using lazy scan.

        Args:
            dvf_path: Path to DVF CSV file or directory

        Returns:
            Lazy frame with raw DVF data
        """
        path = Path(dvf_path)

        if path.is_dir():
            # Scan all CSV files in directory
            pattern = str(path / "*.csv")
            logger.info(f"Scanning DVF files from: {pattern}")
            return pl.scan_csv(pattern, schema_overrides=self.DVF_SCHEMA)

        logger.info(f"Scanning DVF file: {path}")
        return pl.scan_csv(str(path), schema_overrides=self.DVF_SCHEMA)

    def transform(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """Apply cleaning strategy to transform data.

        Args:
            df: Raw DVF LazyFrame

        Returns:
            Cleaned and aggregated LazyFrame
        """
        logger.info(f"Applying strategy: {self._strategy.name}")
        return self._strategy.clean(df)

    def load(self, df: pl.LazyFrame) -> None:
        """Load transformed data into DuckDB.

        Args:
            df: Transformed LazyFrame
        """
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Collecting data and loading to: {self._output_path}")
        result = df.collect()

        conn = duckdb.connect(str(self._output_path))
        try:
            # Install and load spatial extension
            conn.execute("INSTALL spatial; LOAD spatial;")

            # Create mutations_aggregated table
            conn.execute("DROP TABLE IF EXISTS mutations_aggregated")
            conn.execute("""
                CREATE TABLE mutations_aggregated AS
                SELECT * FROM result
            """)

            # Create index on code_commune for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mutations_commune
                ON mutations_aggregated(code_commune)
            """)

            logger.info(f"Loaded {len(result)} mutations to DuckDB")

        finally:
            conn.close()

    def run(self, dvf_path: Path | str) -> int:
        """Execute full ETL pipeline.

        Args:
            dvf_path: Path to DVF CSV file or directory

        Returns:
            Number of mutations processed
        """
        warnings.warn(
            "DvfEtlPipeline est déprécié ; utilisez python data-pipeline/run_dvf_pipeline.py",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.info(f"Starting legacy DVF ETL pipeline with strategy: {self._strategy.name}")

        df = self.extract(dvf_path)
        df = self.transform(df)
        self.load(df)

        # Get count
        conn = duckdb.connect(str(self._output_path), read_only=True)
        count = conn.execute("SELECT COUNT(*) FROM mutations_aggregated").fetchone()[0]
        conn.close()

        logger.info(f"ETL complete: {count} mutations")
        return count


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python etl_dvf.py <dvf_path> [output_path]")
        sys.exit(1)

    dvf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "./data/foncier.duckdb"

    pipeline = DvfEtlPipeline(output_path=output_path)
    pipeline.run(dvf_path)
