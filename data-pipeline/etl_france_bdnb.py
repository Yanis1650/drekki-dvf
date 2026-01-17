"""ETL France BDNB - Extract building attributes via Polars Lazy.

Streams BDNB CSVs (138GB total) through Polars lazy evaluation
to extract only: parcelle_id, dpe_energie, annee_construction, hauteur_moyenne.

Memory constraint: <8GB RAM using lazy streaming.
"""

import time
from pathlib import Path

import polars as pl

# Configuration
BDNB_PATH = Path("data/open_data_millesime_2025-07-a_france_csv/csv")
OUTPUT_PATH = Path("data/bdnb_stats.parquet")

# BDNB files to process
DPE_FILE = BDNB_PATH / "batiment_groupe_dpe_representatif_logement.csv"
CSTR_FILE = BDNB_PATH / "batiment_construction.csv"
REL_FILE = BDNB_PATH / "rel_batiment_groupe_parcelle.csv"


def main():
    print("=" * 60)
    print("ETL France BDNB - Polars Lazy Streaming")
    print("=" * 60)

    start_time = time.time()

    # Verify files exist
    for f in [DPE_FILE, CSTR_FILE, REL_FILE]:
        if not f.exists():
            print(f"ERROR: {f} not found")
            return
        print(f"✓ Found: {f.name} ({f.stat().st_size / 1e9:.1f} GB)")

    print("\n--- Phase 1: Load relationship table ---")
    # Link batiment_groupe_id → parcelle_id
    rel_lazy = pl.scan_csv(
        str(REL_FILE),
        separator=";",
    ).select([
        "batiment_groupe_id",
        "parcelle_id",
    ])
    print(f"Schema: {rel_lazy.collect_schema().names()}")

    print("\n--- Phase 2: Load DPE data ---")
    # Extract DPE class
    dpe_lazy = pl.scan_csv(
        str(DPE_FILE),
        separator=";",
    ).select([
        "batiment_groupe_id",
        pl.col("classe_bilan_dpe").alias("dpe_energie"),
    ]).group_by("batiment_groupe_id").agg(
        pl.col("dpe_energie").first()  # Take first DPE if multiple
    )
    print(f"Schema: {dpe_lazy.collect_schema().names()}")

    print("\n--- Phase 3: Load Construction data ---")
    # Extract year and height
    cstr_lazy = pl.scan_csv(
        str(CSTR_FILE),
        separator=";",
        infer_schema_length=10000,
    )

    # Check available columns
    cstr_cols = cstr_lazy.collect_schema().names()
    print(f"Available columns: {cstr_cols[:20]}...")

    # Find relevant columns (may vary by BDNB version)
    year_col = None
    height_col = None
    bat_id_col = None

    for col in cstr_cols:
        if 'annee' in col.lower():
            year_col = col
        if 'hauteur' in col.lower() and 'fictive' not in col.lower():
            height_col = col
        if 'batiment_groupe_id' in col.lower():
            bat_id_col = col

    print(f"Using: year={year_col}, height={height_col}, id={bat_id_col}")

    if bat_id_col:
        select_cols = [bat_id_col]
        if year_col:
            select_cols.append(pl.col(year_col).alias("annee_construction"))
        if height_col:
            select_cols.append(pl.col(height_col).alias("hauteur_moyenne"))

        cstr_lazy = cstr_lazy.select(select_cols).group_by(bat_id_col).agg([
            pl.col("annee_construction").mean().cast(pl.Int32) if year_col else pl.lit(None).alias("annee_construction"),
            pl.col("hauteur_moyenne").mean() if height_col else pl.lit(None).alias("hauteur_moyenne"),
        ])

    print("\n--- Phase 4: Join all sources ---")
    # Join: rel → dpe → cstr
    joined = (
        rel_lazy
        .join(dpe_lazy, on="batiment_groupe_id", how="left")
        .join(cstr_lazy, on="batiment_groupe_id", how="left")
        .select([
            "parcelle_id",
            "dpe_energie",
            "annee_construction",
            "hauteur_moyenne",
        ])
        .group_by("parcelle_id").agg([
            pl.col("dpe_energie").first(),
            pl.col("annee_construction").mean().cast(pl.Int32),
            pl.col("hauteur_moyenne").mean(),
        ])
    )

    print("\n--- Phase 5: Sink to Parquet ---")
    print(f"Writing to {OUTPUT_PATH}...")

    # Use sink_parquet for memory-efficient streaming
    joined.sink_parquet(
        str(OUTPUT_PATH),
        compression="zstd",
    )

    # Verify output
    output_count = pl.scan_parquet(str(OUTPUT_PATH)).select(pl.count()).collect().item()
    output_size = OUTPUT_PATH.stat().st_size / 1e6

    elapsed = time.time() - start_time
    print(f"\n✅ BDNB extraction complete in {elapsed:.1f}s")
    print(f"   Output: {OUTPUT_PATH} ({output_size:.1f} MB, {output_count:,} rows)")


if __name__ == "__main__":
    main()
