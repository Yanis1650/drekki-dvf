"""ETL France Cadastre - Ingest GeoParquet into DuckDB.

Streams cadastre.parquet directly into DuckDB parcelles table
with spatial indexing for fast queries.
"""

import time
from pathlib import Path

import duckdb

# Configuration
DUCKDB_PATH = Path("data/foncier.duckdb")
CADASTRE_PATH = Path("data/cadastre.parquet")


def main():
    print("=" * 60)
    print("ETL France Cadastre - GeoParquet Ingestion")
    print("=" * 60)

    start_time = time.time()

    # Connect to DuckDB (read-write mode)
    conn = duckdb.connect(str(DUCKDB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # Check existing tables
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
    print(f"Existing tables: {tables}")

    # Drop old synthetic parcelles if exists
    if 'parcelles' in tables:
        print("Dropping existing 'parcelles' table (synthetic data)...")
        conn.execute("DROP TABLE parcelles")

    # Verify parquet file exists
    if not CADASTRE_PATH.exists():
        print(f"ERROR: Cadastre file not found at {CADASTRE_PATH}")
        return

    # Inspect parquet schema first
    print(f"\nInspecting {CADASTRE_PATH}...")
    schema = conn.execute(f"""
        DESCRIBE SELECT * FROM read_parquet('{CADASTRE_PATH}') LIMIT 1
    """).fetchall()
    print("Parquet Schema:")
    for col in schema:
        print(f"  - {col[0]}: {col[1]}")

    # Get row count estimate
    count = conn.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{CADASTRE_PATH}')
    """).fetchone()[0]
    print(f"\nTotal parcels in cadastre: {count:,}")

    # Create parcelles table from parquet
    # Assuming columns: id (parcelle ID), geometry (WKB/WKT)
    # We need to adapt based on actual schema
    print("\nCreating parcelles table from parquet (streaming)...")

    # First, let's see actual column names
    sample = conn.execute(f"""
        SELECT * FROM read_parquet('{CADASTRE_PATH}') LIMIT 1
    """).fetchone()
    col_names = [col[0] for col in schema]
    print(f"Columns: {col_names}")

    # Verified schema from inspection:
    # - id: parcelle ID (15 char)
    # - geometry: WKB geometry
    # - commune, section, prefixe, numero

    print("\nCreating parcelles table from parquet (streaming)...")
    print("Using: id_parcelle=id, geometry=geometry")

    # Create table with geometry conversion
    # The geometry in parquet appears to be in EPSG:2154 already (Lambert-93)
    conn.execute("""
        CREATE TABLE parcelles AS
        SELECT 
            id AS id_parcelle,
            commune AS code_commune,
            section,
            prefixe,
            numero,
            geometry
        FROM read_parquet('data/cadastre.parquet')
    """)

    # Verify creation
    new_count = conn.execute("SELECT COUNT(*) FROM parcelles").fetchone()[0]
    print(f"\nParcelles table created: {new_count:,} rows")

    # Create spatial index
    print("Creating spatial index (RTREE)...")
    conn.execute("CREATE INDEX idx_parcelles_geom ON parcelles USING RTREE (geometry)")

    # Create code_commune index if available
    print("Checking for code_commune column...")
    if 'code_commune' in col_names or 'ccodep' in col_names:
        print("Recreating with code_commune...")
        # Would need to add code_commune to the table

    elapsed = time.time() - start_time
    print(f"\n✅ Cadastre ingestion complete in {elapsed:.1f}s")
    print(f"   Table: parcelles ({new_count:,} rows)")

    conn.close()


if __name__ == "__main__":
    main()
