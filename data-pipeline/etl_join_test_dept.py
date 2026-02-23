"""ETL Golden Join - TEST on Département 35 only.

Spatial join: mutations_aggregated x parcelles x BDNB.
Parcelle table contains hierarchical geometries (commune, section, parcel)
so we filter to leaf-level parcels only (section + numero NOT NULL)
and use ROW_NUMBER to keep the smallest (most specific) match per mutation.
"""

import time
from pathlib import Path

import duckdb

# Configuration
DUCKDB_PATH = Path("data/foncier.duckdb")
BDNB_STATS_PATH = Path("data/bdnb_stats.parquet")
TEST_DEPT = "35"  # Ille-et-Vilaine (Rennes)

GOLDEN_JOIN_SQL = """
    CREATE TABLE france_foncier_test AS

    WITH mutations_dept AS (
        SELECT
            m.*,
            ST_Transform(
                ST_Point(m.latitude, m.longitude),
                'EPSG:4326', 'EPSG:2154'
            ) AS point_geom
        FROM mutations_aggregated m
        WHERE m.code_commune LIKE '{dept}%'
          AND m.longitude IS NOT NULL
          AND m.latitude IS NOT NULL
    ),

    -- Only keep leaf-level parcels (exclude commune/section/prefix geometries)
    parcelles_dept AS (
        SELECT *
        FROM parcelles
        WHERE code_commune LIKE '{dept}%'
          AND section IS NOT NULL
          AND numero IS NOT NULL
    ),

    -- Spatial join + rank by smallest area (most specific parcel wins)
    mutation_parcelle_ranked AS (
        SELECT
            md.*,
            pd.id_parcelle,
            pd.geometry AS parcelle_geometry,
            ROW_NUMBER() OVER (
                PARTITION BY md.id_mutation
                ORDER BY ST_Area(pd.geometry) ASC
            ) AS rn
        FROM mutations_dept md
        LEFT JOIN parcelles_dept pd
            ON md.code_commune = pd.code_commune
            AND ST_Contains(pd.geometry, md.point_geom)
    ),

    -- Keep only best match per mutation
    mutation_parcelle AS (
        SELECT * FROM mutation_parcelle_ranked WHERE rn = 1
    )

    SELECT
        mp.id_mutation,
        mp.date_mutation,
        mp.nature_mutation,
        mp.valeur_fonciere,
        mp.code_commune,
        mp.parcelles AS dvf_parcelles,
        mp.surface_habitable_totale,
        mp.nombre_locaux,
        mp.prix_m2,
        mp.longitude,
        mp.latitude,
        mp.id_parcelle AS cadastre_parcelle_id,
        mp.parcelle_geometry AS geometry,
        {bdnb_cols}
    FROM mutation_parcelle mp
    {bdnb_join}
"""


def main():
    print("=" * 60)
    print(f"ETL Golden Join - TEST Departement {TEST_DEPT}")
    print("=" * 60)

    start_time = time.time()

    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    mut_count = conn.execute(f"""
        SELECT COUNT(*) FROM mutations_aggregated
        WHERE code_commune LIKE '{TEST_DEPT}%'
    """).fetchone()[0]
    print(f"Mutations in dept {TEST_DEPT}: {mut_count:,}")

    # Count only leaf parcels (the ones we'll actually use)
    parc_count = conn.execute(f"""
        SELECT COUNT(*) FROM parcelles
        WHERE code_commune LIKE '{TEST_DEPT}%'
          AND section IS NOT NULL AND numero IS NOT NULL
    """).fetchone()[0]
    parc_total = conn.execute(f"""
        SELECT COUNT(*) FROM parcelles
        WHERE code_commune LIKE '{TEST_DEPT}%'
    """).fetchone()[0]
    print(f"Parcels in dept {TEST_DEPT}: {parc_count:,} leaf / {parc_total:,} total")

    has_bdnb = BDNB_STATS_PATH.exists()
    if has_bdnb:
        conn.execute(f"""
            CREATE TEMP TABLE bdnb_stats AS
            SELECT * FROM read_parquet('{BDNB_STATS_PATH}')
            WHERE parcelle_id LIKE '{TEST_DEPT}%'
        """)
        bdnb_count = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
        print(f"BDNB stats for dept {TEST_DEPT}: {bdnb_count:,}")

    conn.execute("DROP TABLE IF EXISTS france_foncier_test")

    print(f"\n--- Creating Golden Join for Dept {TEST_DEPT} ---")
    print("Strategy: leaf parcels only + ROW_NUMBER(smallest area)")

    if has_bdnb:
        bdnb_cols = (
            "b.dpe_energie,\n"
            "        b.annee_construction,\n"
            "        b.hauteur_moyenne,\n"
            "        b.nb_niveau,\n"
            "        b.type_usage,\n"
            "        b.nb_log"
        )
        bdnb_join = "LEFT JOIN bdnb_stats b ON mp.id_parcelle = b.parcelle_id"
    else:
        bdnb_cols = (
            "NULL AS dpe_energie,\n"
            "        NULL AS annee_construction,\n"
            "        NULL AS hauteur_moyenne,\n"
            "        NULL AS nb_niveau,\n"
            "        NULL AS type_usage,\n"
            "        NULL AS nb_log"
        )
        bdnb_join = ""

    sql = GOLDEN_JOIN_SQL.format(
        dept=TEST_DEPT,
        bdnb_cols=bdnb_cols,
        bdnb_join=bdnb_join,
    )
    conn.execute(sql)

    # Create index for fast lookups
    conn.execute("CREATE INDEX idx_fft_date ON france_foncier_test(date_mutation)")
    conn.execute("CREATE INDEX idx_fft_commune ON france_foncier_test(code_commune)")
    conn.execute("CREATE INDEX idx_fft_parcelle ON france_foncier_test(cadastre_parcelle_id)")

    final_count = conn.execute("SELECT COUNT(*) FROM france_foncier_test").fetchone()[0]
    print(f"\nfrance_foncier_test created: {final_count:,} rows")

    unique_mutations = conn.execute("""
        SELECT COUNT(DISTINCT id_mutation) FROM france_foncier_test
    """).fetchone()[0]
    print(f"Unique mutations: {unique_mutations:,}")
    print(f"Ratio rows/mutations: {final_count/unique_mutations:.2f}" if unique_mutations else "")

    with_parcel = conn.execute("""
        SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NOT NULL
    """).fetchone()[0]
    match_rate = 100 * with_parcel / final_count if final_count > 0 else 0
    print(f"Cadastre match: {with_parcel:,} ({match_rate:.1f}%)")

    if has_bdnb:
        with_bdnb = conn.execute("""
            SELECT COUNT(*) FROM france_foncier_test
            WHERE dpe_energie IS NOT NULL
               OR annee_construction IS NOT NULL
               OR hauteur_moyenne IS NOT NULL
        """).fetchone()[0]
        bdnb_rate = 100 * with_bdnb / final_count if final_count > 0 else 0
        print(f"BDNB match: {with_bdnb:,} ({bdnb_rate:.1f}%)")

        dpe_stats = conn.execute("""
            SELECT dpe_energie, COUNT(*) as cnt
            FROM france_foncier_test
            WHERE dpe_energie IS NOT NULL
            GROUP BY dpe_energie
            ORDER BY cnt DESC
            LIMIT 7
        """).fetchall()
        if dpe_stats:
            print("\nDPE distribution:")
            for dpe, cnt in dpe_stats:
                print(f"  {dpe}: {cnt:,}")

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s")

    conn.close()


if __name__ == "__main__":
    main()
