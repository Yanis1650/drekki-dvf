"""Debug spatial query for parcelles"""
import duckdb

conn = duckdb.connect('data/foncier.duckdb', read_only=True)
conn.execute('INSTALL spatial; LOAD spatial;')

# Test bbox for Rennes
min_lon, min_lat, max_lon, max_lat = -1.68, 48.11, -1.67, 48.12

print("=" * 60)
print("Debugging Spatial Query for Parcelles")
print("=" * 60)

# Test 1: Check if geometry column exists and is valid
print("\n1. Checking parcelles schema...")
schema = conn.execute("DESCRIBE parcelles").fetchall()
for col in schema:
    print(f"   {col[0]}: {col[1]}")

# Test 2: Sample a parcel to see its geometry
print("\n2. Sampling a parcel from dept 35...")
sample = conn.execute("""
    SELECT id_parcelle, code_commune, geometry
    FROM parcelles 
    WHERE code_commune LIKE '35%'
    LIMIT 1
""").fetchone()
print(f"   ID: {sample[0]}")
print(f"   Commune: {sample[1]}")
print(f"   Geometry type: {type(sample[2])}")

# Test 3: Try the exact query from the repository
print("\n3. Testing the spatial query from repository...")
print(f"   Bbox WGS84: {min_lon}, {min_lat}, {max_lon}, {max_lat}")

try:
    # This is the exact query from get_parcelles_geojson
    query = """
        WITH bbox_lambert93 AS (
            SELECT ST_Transform(
                ST_MakeEnvelope(?, ?, ?, ?, 'EPSG:4326'),
                'EPSG:2154'
            ) as bbox_geom
        )
        SELECT 
            p.id_parcelle,
            ST_AsGeoJSON(ST_Transform(p.geometry, 'EPSG:2154', 'EPSG:4326')) as geom_json
        FROM parcelles p, bbox_lambert93
        WHERE p.code_commune LIKE '35%'
          AND ST_Intersects(p.geometry, bbox_lambert93.bbox_geom)
        LIMIT 10
    """

    results = conn.execute(query, [min_lon, min_lat, max_lon, max_lat]).fetchall()
    print("   ✅ Query executed successfully")
    print(f"   Results: {len(results)} parcelles found")

    if len(results) > 0:
        print(f"\n   Sample parcel: {results[0][0]}")
    else:
        print("\n   ⚠️  Query returned 0 results")
        print("\n4. Debugging why no results...")

        # Check if bbox transformation works
        bbox_check = conn.execute("""
            SELECT ST_AsText(ST_Transform(
                ST_MakeEnvelope(?, ?, ?, ?, 'EPSG:4326'),
                'EPSG:2154'
            )) as bbox_lambert93
        """, [min_lon, min_lat, max_lon, max_lat]).fetchone()
        print(f"   Transformed bbox: {bbox_check[0][:100]}...")

        # Check if any parcelles intersect a larger bbox
        larger_bbox = conn.execute("""
            WITH bbox_lambert93 AS (
                SELECT ST_Transform(
                    ST_MakeEnvelope(-2.0, 47.5, -1.0, 48.5, 'EPSG:4326'),
                    'EPSG:2154'
                ) as bbox_geom
            )
            SELECT COUNT(*)
            FROM parcelles p, bbox_lambert93
            WHERE p.code_commune LIKE '35%'
              AND ST_Intersects(p.geometry, bbox_lambert93.bbox_geom)
        """).fetchone()
        print(f"   Larger bbox (all Rennes area): {larger_bbox[0]} parcelles")

except Exception as e:
    print(f"   ❌ Query failed: {e}")
    import traceback
    traceback.print_exc()

conn.close()
