"""ETL France BDNB - Extract building attributes via Polars Lazy.

Sources (BDNB millesime 2025-07):
  - rel_batiment_groupe_parcelle.csv    : batiment_groupe_id -> parcelle_id
  - batiment_groupe_dpe_representatif   : DPE energy class
  - batiment_construction.csv           : hauteur (height)
  - batiment_groupe_ffo_bat.csv         : annee_construction, nb_niveau, usage, nb_log

Output: data/bdnb_stats.parquet (parcelle_id as key)
Memory constraint: <8GB RAM using Polars lazy streaming.
"""

import time
from pathlib import Path

import polars as pl

BDNB_PATH = Path("data/open_data_millesime_2025-07-a_france_csv/csv")
OUTPUT_PATH = Path("data/bdnb_stats.parquet")

REL_FILE = BDNB_PATH / "rel_batiment_groupe_parcelle.csv"
DPE_FILE = BDNB_PATH / "batiment_groupe_dpe_representatif_logement.csv"
CSTR_FILE = BDNB_PATH / "batiment_construction.csv"
FFO_FILE = BDNB_PATH / "batiment_groupe_ffo_bat.csv"


def main():
    print("=" * 60)
    print("ETL France BDNB - Polars Lazy Streaming")
    print("=" * 60)

    start_time = time.time()

    required = [REL_FILE, DPE_FILE, CSTR_FILE, FFO_FILE]
    for f in required:
        if not f.exists():
            print(f"ERROR: {f} not found")
            return
        print(f"  {f.name:55s} {f.stat().st_size / 1e9:.1f} GB")

    # ── Phase 1: Relationship table (batiment_groupe -> parcelle) ─────
    print("\n--- Phase 1: rel_batiment_groupe_parcelle ---")
    rel_lazy = pl.scan_csv(str(REL_FILE), separator=";").select([
        "batiment_groupe_id",
        "parcelle_id",
    ])
    print(f"  Columns: {rel_lazy.collect_schema().names()}")

    # ── Phase 2: DPE representative ──────────────────────────────────
    print("\n--- Phase 2: DPE representatif logement ---")
    dpe_lazy = (
        pl.scan_csv(str(DPE_FILE), separator=";")
        .select(["batiment_groupe_id", pl.col("classe_bilan_dpe").alias("dpe_energie")])
        .group_by("batiment_groupe_id")
        .agg(pl.col("dpe_energie").first())
    )
    print(f"  Columns: {dpe_lazy.collect_schema().names()}")

    # ── Phase 3: Construction geometry (height + footprint) ─────────
    print("\n--- Phase 3: batiment_construction (hauteur + emprise) ---")
    cstr_lazy = (
        pl.scan_csv(str(CSTR_FILE), separator=";", infer_schema_length=10000)
        .select([
            "batiment_groupe_id",
            pl.col("hauteur").alias("hauteur_moyenne"),
            pl.col("s_geom_cstr").cast(pl.Float64, strict=False).alias("emprise_sol_m2"),
        ])
        .group_by("batiment_groupe_id")
        .agg([
            pl.col("hauteur_moyenne").mean(),
            pl.col("emprise_sol_m2").sum(),
        ])
    )
    print(f"  Columns: {cstr_lazy.collect_schema().names()}")

    # ── Phase 4: FFO BAT (annee_construction, nb_niveau, usage) ──────
    print("\n--- Phase 4: batiment_groupe_ffo_bat (annee, usage, niveaux) ---")
    ffo_lazy = (
        pl.scan_csv(str(FFO_FILE), separator=";", infer_schema_length=5000)
        .select([
            "batiment_groupe_id",
            pl.col("annee_construction").cast(pl.Int32, strict=False),
            pl.col("nb_niveau").cast(pl.Int32, strict=False),
            pl.col("usage_niveau_1_txt").alias("type_usage"),
            pl.col("nb_log").cast(pl.Int32, strict=False),
        ])
        .group_by("batiment_groupe_id")
        .agg([
            pl.col("annee_construction").min(),
            pl.col("nb_niveau").max(),
            pl.col("type_usage").first(),
            pl.col("nb_log").sum(),
        ])
    )
    print(f"  Columns: {ffo_lazy.collect_schema().names()}")

    # ── Phase 5: Join all sources ────────────────────────────────────
    print("\n--- Phase 5: Join all sources ---")
    joined = (
        rel_lazy
        .join(dpe_lazy, on="batiment_groupe_id", how="left")
        .join(cstr_lazy, on="batiment_groupe_id", how="left")
        .join(ffo_lazy, on="batiment_groupe_id", how="left")
        .select([
            "parcelle_id",
            "dpe_energie",
            "annee_construction",
            "hauteur_moyenne",
            "emprise_sol_m2",
            "nb_niveau",
            "type_usage",
            "nb_log",
        ])
        .group_by("parcelle_id")
        .agg([
            pl.col("dpe_energie").first(),
            pl.col("annee_construction").min(),
            pl.col("hauteur_moyenne").mean(),
            pl.col("emprise_sol_m2").sum(),
            pl.col("nb_niveau").max(),
            pl.col("type_usage").first(),
            pl.col("nb_log").sum(),
        ])
    )

    # ── Phase 6: Write to parquet ────────────────────────────────────
    print("\n--- Phase 6: Sink to Parquet ---")
    print(f"  Writing to {OUTPUT_PATH}...")

    joined.sink_parquet(str(OUTPUT_PATH), compression="zstd")

    output_count = pl.scan_parquet(str(OUTPUT_PATH)).select(pl.len()).collect().item()
    output_size = OUTPUT_PATH.stat().st_size / 1e6

    # ── Phase 7: Verification ────────────────────────────────────────
    print("\n--- Phase 7: Verification ---")
    lf = pl.scan_parquet(str(OUTPUT_PATH))
    for col in [
        "dpe_energie", "annee_construction", "hauteur_moyenne",
        "emprise_sol_m2", "nb_niveau", "type_usage", "nb_log",
    ]:
        null_rate = lf.select(pl.col(col).is_null().mean()).collect().item()
        print(f"  {col:25s} null={null_rate:.1%}")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Output: {OUTPUT_PATH} ({output_size:.1f} MB, {output_count:,} rows)")


if __name__ == "__main__":
    main()
