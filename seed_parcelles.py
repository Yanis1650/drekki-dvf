
import duckdb


def seed_parcelles():
    db_path = "data/foncier.duckdb"
    conn = duckdb.connect(db_path)
    conn.execute("INSTALL spatial; LOAD spatial;")

    print("Checking for parcelles table...")
    tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]

    if 'parcelles' in tables:
        print("Table 'parcelles' already exists. Dropping for regeneration (mock mode).")
        conn.execute("DROP TABLE parcelles")

    print("Creating parcelles table...")
    conn.execute("""
        CREATE TABLE parcelles (
            id_parcelle VARCHAR,
            code_commune VARCHAR,
            prefixe VARCHAR,
            section VARCHAR,
            numero VARCHAR,
            surface_m2 DECIMAL,
            geometry GEOMETRY
        )
    """)

    print("Seeding parcelles from mutations (Mocking 20m radius polygons in Lambert-93)...")
    # Buffer 20 meters around mutation point.
    # Note: mutations_aggregated has lon/lat (4326). We transform to 2154 (meters) then buffer.
    count = conn.execute("""
        WITH calculated_geom AS (
            SELECT 
                id_mutation, code_commune, surface_habitable_totale,
                ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:2154') as center_pt,
                15.0 as radius  -- Fixed 15m radius (~900m2 box) as requested ("base coordinates")
            FROM mutations_aggregated
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        )
        INSERT INTO parcelles
        SELECT 
            id_mutation as id_parcelle, 
            code_commune, 
            '000' as prefixe, 
            'A' as section, 
            '1' as numero, 
            TRY_CAST(surface_habitable_totale AS DECIMAL) as surface_m2, 
            ST_MakeEnvelope(
                ST_X(center_pt) - radius, 
                ST_Y(center_pt) - radius,
                ST_X(center_pt) + radius, 
                ST_Y(center_pt) + radius
            ) as geometry
        FROM calculated_geom
    """).fetchall()

    row_count = conn.execute("SELECT count(*) FROM parcelles").fetchone()[0]
    print(f"Seeded {row_count} synthetic parcels.")

    # Create spatial index (RTREE) for performance
    print("Creating spatial index...")
    conn.execute("CREATE INDEX parcelles_geom_idx ON parcelles USING RTREE (geometry)")

    conn.close()

if __name__ == "__main__":
    seed_parcelles()
