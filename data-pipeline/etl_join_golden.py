"""ETL Golden Join - Create france_foncier_indexed table.

Joins:
- mutations_aggregated (DVF cleaned)
- parcelles (Cadastre geometry)
- bdnb_stats (DPE, year, height)

Creates indexed table for sub-second spatial queries.
"""

import time
from pathlib import Path

import duckdb

# Configuration
DUCKDB_PATH = Path("data/foncier.duckdb")
BDNB_STATS_PATH = Path("data/bdnb_stats.parquet")


def main():
    print("=" * 60)
    print("ETL Golden Join - france_foncier_indexed")
    print("=" * 60)

    start_time = time.time()

    # Connect to DuckDB
    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Verify required tables exist
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    print(f"Available tables: {tables}")

    if 'mutations_aggregated' not in tables:
        print("ERROR: mutations_aggregated table not found!")
        return

    if 'parcelles' not in tables:
        print("ERROR: parcelles table not found! Run etl_france_cadastre.py first.")
        return

    # Check BDNB stats
    if not BDNB_STATS_PATH.exists():
        print(f"WARNING: {BDNB_STATS_PATH} not found. Joining without BDNB data.")
        has_bdnb = False
    else:
        has_bdnb = True
        print(f"✓ BDNB stats: {BDNB_STATS_PATH}")

    # Drop existing table
    if 'france_foncier_indexed' in tables:
        print("Dropping existing france_foncier_indexed table...")
        conn.execute("DROP TABLE france_foncier_indexed")

    # Load BDNB stats if available
    if has_bdnb:
        print("\nLoading BDNB stats into temporary table...")
        conn.execute(f"""
            CREATE TEMP TABLE bdnb_stats AS
            SELECT * FROM read_parquet('{BDNB_STATS_PATH}')
        """)
        bdnb_count = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
        print(f"BDNB stats: {bdnb_count:,} parcels with attributes")

    print("\n--- Creating Golden Join ---")
    print("Strategy: Spatial join mutations → parcelles, then attribute join → bdnb")

    # Get mutation count
    mutation_count = conn.execute("SELECT COUNT(*) FROM mutations_aggregated").fetchone()[0]
    print(f"Mutations to process: {mutation_count:,}")

    # Create the joined table
    # Step 1: Join mutations with nearest parcel (spatial point-in-polygon)
    if has_bdnb:
        conn.execute("""
            CREATE TABLE france_foncier_indexed AS
            WITH mutation_with_geom AS (
                SELECT 
                    m.*,
                    ST_Transform(ST_Point(m.latitude, m.longitude), 'EPSG:4326', 'EPSG:2154') AS point_geom
                FROM mutations_aggregated m
                WHERE m.longitude IS NOT NULL AND m.latitude IS NOT NULL
            ),
            mutation_parcelle AS (
                SELECT 
                    mwg.*,
                    p.id_parcelle,
                    p.geometry AS parcelle_geometry
                FROM mutation_with_geom mwg
                LEFT JOIN parcelles p ON ST_Contains(p.geometry, mwg.point_geom)
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
        conn.execute("""
            CREATE TABLE france_foncier_indexed AS
            WITH mutation_with_geom AS (
                SELECT 
                    m.*,
                    ST_Transform(ST_Point(m.latitude, m.longitude), 'EPSG:4326', 'EPSG:2154') AS point_geom
                FROM mutations_aggregated m
                WHERE m.longitude IS NOT NULL AND m.latitude IS NOT NULL
            )
            SELECT 
                mwg.*,
                p.id_parcelle AS cadastre_parcelle_id,
                p.geometry
            FROM mutation_with_geom mwg
            LEFT JOIN parcelles p ON ST_Contains(p.geometry, mwg.point_geom)
        """)

    # Verify creation
    final_count = conn.execute("SELECT COUNT(*) FROM france_foncier_indexed").fetchone()[0]
    print(f"\nfrance_foncier_indexed created: {final_count:,} rows")

    # Create indexes
    print("\nCreating indexes...")

    print("  - Spatial index (RTREE on geometry)...")
    try:
        conn.execute("CREATE INDEX idx_foncier_geom ON france_foncier_indexed USING RTREE (geometry)")
        print("    ✓ Spatial index created")
    except Exception as e:
        print(f"    ⚠ Spatial index failed: {e}")

    print("  - Code commune index...")
    conn.execute("CREATE INDEX idx_foncier_commune ON france_foncier_indexed (code_commune)")
    print("    ✓ Commune index created")

    # Stats
    print("\n--- Statistics ---")
    if has_bdnb:
        dpe_stats = conn.execute("""
            SELECT dpe_energie, COUNT(*) as cnt
            FROM france_foncier_indexed
            WHERE dpe_energie IS NOT NULL
            GROUP BY dpe_energie
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
        print("DPE Distribution:")
        for row in dpe_stats:
            print(f"  {row[0]}: {row[1]:,}")

        with_parcel = conn.execute("""
            SELECT COUNT(*) FROM france_foncier_indexed WHERE cadastre_parcelle_id IS NOT NULL
        """).fetchone()[0]
        print(f"\nMutations with cadastre match: {with_parcel:,} ({100*with_parcel/final_count:.1f}%)")

    elapsed = time.time() - start_time
    print(f"\n✅ Golden Join complete in {elapsed:.1f}s")
    print(f"   Table: france_foncier_indexed ({final_count:,} rows)")

    conn.close()


if __name__ == "__main__":
    main()
