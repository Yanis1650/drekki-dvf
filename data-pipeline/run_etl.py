"""DVF ETL Runner Script.

Processes all DVF CSV files from data folder into DuckDB.
Usage: python run_etl.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
import polars as pl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Explicit schema to ensure consistency across all years
DVF_SCHEMA = {
    "id_mutation": pl.Utf8,
    "date_mutation": pl.Utf8,
    "nature_mutation": pl.Utf8,
    "valeur_fonciere": pl.Float64,
    "code_postal": pl.Utf8,
    "code_commune": pl.Utf8,
    "nom_commune": pl.Utf8,
    "code_departement": pl.Utf8,
    "id_parcelle": pl.Utf8,
    "type_local": pl.Utf8,
    "surface_reelle_bati": pl.Float64,
    "nombre_pieces_principales": pl.Int32,
    "surface_terrain": pl.Float64,
    "longitude": pl.Float64,
    "latitude": pl.Float64,
}

# Columns we need
COLUMNS_TO_SELECT = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "code_commune",
    "id_parcelle",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "longitude",
    "latitude",
]


def process_single_file(csv_file: Path) -> pl.DataFrame:
    """Process a single DVF CSV file."""
    logger.info(f"Processing: {csv_file.name}")

    df = pl.read_csv(
        csv_file,
        schema_overrides=DVF_SCHEMA,
        ignore_errors=True,
        infer_schema_length=10000,
    )

    # Select and cast columns
    available_cols = [c for c in COLUMNS_TO_SELECT if c in df.columns]
    df = df.select(available_cols)

    # Cast code_commune to string (may be int in some files)
    if "code_commune" in df.columns:
        df = df.with_columns(
            pl.col("code_commune").cast(pl.Utf8).str.zfill(5)
        )

    return df


def run_dvf_etl():
    """Process all DVF CSV files with Mericskay methodology."""

    data_dir = Path(__file__).parent.parent / "data"
    output_path = data_dir / "foncier.duckdb"

    # Find all CSV files in subdirectories
    csv_files = sorted(data_dir.glob("*_dvf/full_*.csv"))
    logger.info(f"Found {len(csv_files)} DVF files to process")

    if not csv_files:
        logger.error("No DVF CSV files found in data/*_dvf/")
        return

    # Process each file and concatenate
    all_dfs = []
    for csv_file in csv_files:
        try:
            df = process_single_file(csv_file)
            all_dfs.append(df)
        except Exception as e:
            logger.error(f"Failed to process {csv_file.name}: {e}")
            continue

    if not all_dfs:
        logger.error("No files successfully processed")
        return

    # Concatenate all dataframes
    logger.info("Concatenating all years...")
    combined = pl.concat(all_dfs, how="diagonal")
    logger.info(f"Total raw transactions: {len(combined):,}")

    # Apply Mericskay filters
    logger.info("Applying Mericskay methodology filters...")
    filtered = combined.filter(
        (pl.col("nature_mutation") == "Vente") &
        (pl.col("valeur_fonciere") > 1000) &
        (pl.col("type_local").is_in(["Maison", "Appartement"]))
    )
    logger.info(f"After filtering: {len(filtered):,} transactions")

    # Aggregate by id_mutation
    logger.info("Aggregating by mutation ID...")
    aggregated = filtered.group_by("id_mutation").agg(
        pl.first("date_mutation"),
        pl.first("nature_mutation"),
        pl.first("valeur_fonciere"),
        pl.first("code_commune"),
        pl.col("id_parcelle").unique().alias("parcelles"),
        pl.col("surface_reelle_bati").sum().alias("surface_habitable_totale"),
        pl.len().alias("nombre_locaux"),
        pl.first("longitude"),
        pl.first("latitude"),
    )

    # Calculate prix_m2 and filter min surface
    logger.info("Calculating price per m²...")
    final = aggregated.with_columns(
        pl.when(pl.col("surface_habitable_totale") > 9)
        .then(pl.col("valeur_fonciere") / pl.col("surface_habitable_totale"))
        .otherwise(None)
        .alias("prix_m2")
    ).filter(
        pl.col("surface_habitable_totale") > 9
    )

    logger.info(f"Final mutations: {len(final):,}")

    # Save to DuckDB
    logger.info(f"Saving to DuckDB: {output_path}")
    conn = duckdb.connect(str(output_path))

    try:
        conn.execute("INSTALL spatial; LOAD spatial;")
        conn.execute("DROP TABLE IF EXISTS mutations_aggregated")
        conn.register("result_df", final)
        conn.execute("""
            CREATE TABLE mutations_aggregated AS
            SELECT * FROM result_df
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mutations_commune
            ON mutations_aggregated(code_commune)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mutations_date
            ON mutations_aggregated(date_mutation)
        """)

        count = conn.execute("SELECT COUNT(*) FROM mutations_aggregated").fetchone()[0]
        logger.info(f"✓ Loaded {count:,} mutations to DuckDB")

    finally:
        conn.close()

    logger.info("ETL Complete!")


if __name__ == "__main__":
    run_dvf_etl()
