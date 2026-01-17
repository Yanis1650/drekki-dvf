"""ETL Golden Join - TEST on Département 35 only.

Quick test to validate spatial join before running on all France.
"""

import time
from pathlib import Path

import duckdb

# Configuration
DUCKDB_PATH = Path("data/foncier.duckdb")
BDNB_STATS_PATH = Path("data/bdnb_stats.parquet")
TEST_DEPT = "35"  # Ille-et-Vilaine (Rennes)


def main():
    print("=" * 60)
    print(f"ETL Golden Join - TEST Département {TEST_DEPT}")
    print("=" * 60)

    start_time = time.time()

    # Connect to DuckDB
    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Check mutation count for dept 35
    mut_count = conn.execute(f"""
        SELECT COUNT(*) FROM mutations_aggregated 
        WHERE code_commune LIKE '{TEST_DEPT}%'
    """).fetchone()[0]
    print(f"Mutations in dept {TEST_DEPT}: {mut_count:,}")

    # Check parcel count for dept 35
    parc_count = conn.execute(f"""
        SELECT COUNT(*) FROM parcelles 
        WHERE code_commune LIKE '{TEST_DEPT}%'
    """).fetchone()[0]
    print(f"Parcels in dept {TEST_DEPT}: {parc_count:,}")

    # Load BDNB stats
    has_bdnb = BDNB_STATS_PATH.exists()
    if has_bdnb:
        conn.execute(f"""
            CREATE TEMP TABLE bdnb_stats AS
            SELECT * FROM read_parquet('{BDNB_STATS_PATH}')
            WHERE parcelle_id LIKE '{TEST_DEPT}%'
        """)
        bdnb_count = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
        print(f"BDNB stats for dept {TEST_DEPT}: {bdnb_count:,}")

    # Drop test table if exists
    conn.execute("DROP TABLE IF EXISTS france_foncier_test")

    print(f"\n--- Creating Golden Join for Dept {TEST_DEPT} ---")
    print("Strategy: Join on code_commune first, then spatial contains")

    # Optimized join using code_commune pre-filter
    if has_bdnb:
        conn.execute(f"""
            CREATE TABLE france_foncier_test AS
            WITH mutations_dept AS (
                SELECT 
                    m.*,
                    ST_Transform(ST_Point(m.latitude, m.longitude), 'EPSG:4326', 'EPSG:2154') AS point_geom
                FROM mutations_aggregated m
                WHERE m.code_commune LIKE '{TEST_DEPT}%'
                  AND m.longitude IS NOT NULL 
                  AND m.latitude IS NOT NULL
            ),
            parcelles_dept AS (
                SELECT * FROM parcelles WHERE code_commune LIKE '{TEST_DEPT}%'
            ),
            mutation_parcelle AS (
                SELECT 
                    md.*,
                    pd.id_parcelle,
                    pd.geometry AS parcelle_geometry
                FROM mutations_dept md
                LEFT JOIN parcelles_dept pd 
                    ON md.code_commune = pd.code_commune
                    AND ST_Contains(pd.geometry, md.point_geom)
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
                b.dpe_energie,
                b.annee_construction,
                b.hauteur_moyenne
            FROM mutation_parcelle mp
            LEFT JOIN bdnb_stats b ON mp.id_parcelle = b.parcelle_id
        """)
    else:
        conn.execute(f"""
            CREATE TABLE france_foncier_test AS
            WITH mutations_dept AS (
                SELECT 
                    m.*,
                    ST_Transform(ST_Point(m.latitude, m.longitude), 'EPSG:4326', 'EPSG:2154') AS point_geom
                FROM mutations_aggregated m
                WHERE m.code_commune LIKE '{TEST_DEPT}%'
                  AND m.longitude IS NOT NULL 
                  AND m.latitude IS NOT NULL
            ),
            parcelles_dept AS (
                SELECT * FROM parcelles WHERE code_commune LIKE '{TEST_DEPT}%'
            )
            SELECT 
                md.*,
                pd.id_parcelle AS cadastre_parcelle_id,
                pd.geometry
            FROM mutations_dept md
            LEFT JOIN parcelles_dept pd 
                ON md.code_commune = pd.code_commune
                AND ST_Contains(pd.geometry, md.point_geom)
        """)

    # Verify
    final_count = conn.execute("SELECT COUNT(*) FROM france_foncier_test").fetchone()[0]
    print(f"\nfrance_foncier_test created: {final_count:,} rows")

    # Check match rate
    with_parcel = conn.execute("""
        SELECT COUNT(*) FROM france_foncier_test WHERE cadastre_parcelle_id IS NOT NULL
    """).fetchone()[0]
    match_rate = 100 * with_parcel / final_count if final_count > 0 else 0
    print(f"Cadastre match: {with_parcel:,} ({match_rate:.1f}%)")

    # DPE stats if available
    if has_bdnb:
        dpe_stats = conn.execute("""
            SELECT dpe_energie, COUNT(*) as cnt
            FROM france_foncier_test
            WHERE dpe_energie IS NOT NULL
            GROUP BY dpe_energie
            ORDER BY cnt DESC
            LIMIT 5
        """).fetchall()
        if dpe_stats:
            print("\nTop DPE classes:")
            for row in dpe_stats:
                print(f"  {row[0]}: {row[1]:,}")

    elapsed = time.time() - start_time
    print(f"\n✅ Test complete in {elapsed:.1f}s")

    conn.close()


if __name__ == "__main__":
    main()
