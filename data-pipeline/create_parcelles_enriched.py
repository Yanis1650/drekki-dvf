"""Create parcelles_enriched table for Modaal methodology.

This table is the single geographic reference combining:
- Cadastre: geometry (parcels)
- BDNB: DPE, construction year, building height

NO DVF data (no prices, no dates, no transactions).
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"


def create_parcelles_enriched():
    """Create parcelles_enriched table with Cadastre + BDNB only."""

    conn = duckdb.connect(str(DB_PATH))

    # Install and load spatial extension
    conn.execute("INSTALL spatial;")
    conn.execute("LOAD spatial;")

    print("🔍 Checking existing tables...")
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"Found tables: {[t[0] for t in tables]}")

    # Drop existing table if exists
    conn.execute("DROP TABLE IF EXISTS parcelles_enriched;")

    print("\n🏗️ Creating parcelles_enriched table...")

    # Create the enriched parcels table
    # Join parcelles (geometry) with bdnb_stats (DPE, year)
    # NO DVF data included
    conn.execute("""
        CREATE TABLE parcelles_enriched AS
        SELECT 
            p.id_parcelle,
            p.code_commune,
            p.code_departement,
            p.geometry,  -- Lambert-93 (EPSG:2154)
            COALESCE(b.dpe_classe, 'N/A') as dpe_classe,
            b.annee_construction,
            b.hauteur_batiment,
            b.surface_plancher
        FROM parcelles p
        LEFT JOIN bdnb_stats b ON p.id_parcelle = b.id_parcelle
        WHERE p.code_departement = '35'  -- Dept 35 only (real geometry available)
          AND p.geometry IS NOT NULL;
    """)

    # Create spatial index for performance
    print("📍 Creating spatial index...")
    conn.execute("""
        CREATE INDEX idx_parcelles_enriched_spatial 
        ON parcelles_enriched USING RTREE(geometry);
    """)

    # Create regular indexes
    conn.execute("""
        CREATE INDEX idx_parcelles_enriched_commune 
        ON parcelles_enriched(code_commune);
    """)

    # Verify the table
    count = conn.execute("SELECT COUNT(*) FROM parcelles_enriched").fetchone()[0]
    print(f"\n✅ Created parcelles_enriched table with {count:,} parcels")

    # Sample data
    print("\n📊 Sample data:")
    sample = conn.execute("""
        SELECT 
            id_parcelle, 
            code_commune, 
            dpe_classe, 
            annee_construction,
            ST_GeometryType(geometry) as geom_type
        FROM parcelles_enriched 
        LIMIT 5
    """).fetchall()

    for row in sample:
        print(f"  {row}")

    # Verify NO DVF data
    print("\n🔒 Verifying data separation (should have NO DVF columns)...")
    schema = conn.execute("DESCRIBE parcelles_enriched").fetchall()
    dvf_columns = ['prix_m2', 'valeur_fonciere', 'date_mutation', 'nature_mutation']
    has_dvf = any(col[0] in dvf_columns for col in schema)

    if has_dvf:
        print("❌ ERROR: DVF data found in parcelles_enriched!")
    else:
        print("✅ Confirmed: NO DVF data in parcelles_enriched")

    conn.close()
    print("\n✨ Done!")


if __name__ == "__main__":
    create_parcelles_enriched()
