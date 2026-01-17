"""Test the corrected spatial query directly"""
import duckdb

conn = duckdb.connect('data/foncier.duckdb', read_only=True)
conn.execute('INSTALL spatial; LOAD spatial;')

# Test bbox for Rennes
min_lon, min_lat, max_lon, max_lat = -1.68, 48.11, -1.67, 48.12

print("Testing CORRECTED spatial query...")
print(f"Bbox: {min_lon}, {min_lat}, {max_lon}, {max_lat}")

try:
    # Corrected query with ST_SetSRID
    query = """
        WITH bbox_lambert93 AS (
            SELECT ST_Transform(
                ST_SetSRID(ST_MakeEnvelope(?, ?, ?, ?), 4326),
                2154
            ) as bbox_geom
        )
        SELECT 
            p.id_parcelle,
            ST_AsGeoJSON(ST_Transform(p.geometry, 2154, 4326)) as geom_json
        FROM parcelles p, bbox_lambert93
        WHERE p.code_commune LIKE '35%'
          AND ST_Intersects(p.geometry, bbox_lambert93.bbox_geom)
        LIMIT 10
    """

    results = conn.execute(query, [min_lon, min_lat, max_lon, max_lat]).fetchall()
    print("✅ Query executed successfully!")
    print(f"Results: {len(results)} parcelles found")

    if len(results) > 0:
        print("\nSample parcels:")
        for i, (id_parcelle, geom_json) in enumerate(results[:3], 1):
            print(f"  {i}. {id_parcelle}")
    else:
        print("\n⚠️  Still 0 results. Checking geometry SRID...")

        # Check actual SRID of parcelles
        srid_check = conn.execute("""
            SELECT ST_SRID(geometry) as srid, COUNT(*) as count
            FROM parcelles
            WHERE code_commune LIKE '35%'
            GROUP BY srid
            LIMIT 5
        """).fetchall()
        print(f"Parcelles SRID distribution: {srid_check}")

except Exception as e:
    print(f"❌ Query failed: {e}")
    import traceback
    traceback.print_exc()

conn.close()
