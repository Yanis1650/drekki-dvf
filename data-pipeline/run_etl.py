"""Pipeline DVF canonique : fichiers géolocalisés vers DuckDB.

Ce module est la seule implémentation de référence du nettoyage et de
l'agrégation DVF. Les données peuvent provenir de l'ingestion versionnée ou,
pour compatibilité, de l'arborescence historique ``data/*_dvf``.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
import polars as pl
from dvf_io import discover_input_files, process_single_file

from app.domain.dvf_methodology import (
    HABITABLE_LOCAL_TYPES,
    MIN_HABITABLE_SURFACE_M2,
    MIN_TRANSACTION_VALUE_EUR,
    SALE_NATURE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_dvf_etl(
    input_files: list[Path] | None = None,
    output_path: Path | None = None,
    input_glob: str | None = None,
) -> int:
    """Construit ``mutations_aggregated`` avec la méthodologie Mericskay.

    Args:
        input_files: Ressources CSV/CSV.GZ explicites. Prioritaire sur le glob.
        output_path: Base DuckDB cible.
        input_glob: Glob relatif à ``data/`` pour un run manuel.

    Returns:
        Nombre de mutations finales écrites dans DuckDB.
    """

    data_dir = Path(__file__).parent.parent / "data"
    target_path = output_path or data_dir / "foncier.duckdb"

    csv_files = input_files or discover_input_files(data_dir, input_glob)
    logger.info(f"Found {len(csv_files)} DVF files to process")

    if not csv_files:
        raise ValueError("Aucun fichier DVF trouvé. Lancez run_dvf_ingestion.py ou fournissez --input-glob.")

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
        raise RuntimeError("Aucun fichier DVF n'a pu être traité")

    # Concatenate all dataframes
    logger.info("Concatenating all years...")
    combined = pl.concat(all_dfs, how="diagonal")
    logger.info(f"Total raw transactions: {len(combined):,}")

    # Apply Mericskay filters
    logger.info("Applying Mericskay methodology filters...")
    filtered = combined.filter(
        (pl.col("nature_mutation") == SALE_NATURE)
        & (pl.col("valeur_fonciere") > float(MIN_TRANSACTION_VALUE_EUR))
        & (pl.col("type_local").is_in(HABITABLE_LOCAL_TYPES))
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
        pl.first("type_local"),
    )

    # Calculate prix_m2 and filter min surface
    logger.info("Calculating price per m²...")
    final = aggregated.with_columns(
        pl.when(pl.col("surface_habitable_totale") > float(MIN_HABITABLE_SURFACE_M2))
        .then(pl.col("valeur_fonciere") / pl.col("surface_habitable_totale"))
        .otherwise(None)
        .alias("prix_m2")
    ).filter(pl.col("surface_habitable_totale") > float(MIN_HABITABLE_SURFACE_M2))

    logger.info(f"Final mutations: {len(final):,}")

    # Save to DuckDB
    logger.info(f"Saving to DuckDB: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(target_path))

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
    return len(final)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transforme les DVF géolocalisées vers DuckDB")
    parser.add_argument(
        "--input-glob",
        help="Glob relatif à data/, ex. raw/dvf-geolocated/release=*/resources/*.csv.gz",
    )
    parser.add_argument("--output", type=Path, help="Chemin de la base DuckDB cible")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_dvf_etl(output_path=args.output, input_glob=args.input_glob)
