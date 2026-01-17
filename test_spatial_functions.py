"""Find working spatial functions in DuckDB"""
import duckdb

conn = duckdb.connect('data/foncier.duckdb', read_only=True)
conn.execute('INSTALL spatial; LOAD spatial;')

print("Testing different approaches for bbox creation...")

# Test 1: Simple ST_MakeEnvelope without SRID
print("\n1. ST_MakeEnvelope (4 params, no SRID):")
try:
    bbox = conn.execute("SELECT ST_AsText(ST_MakeEnvelope(-1.68, 48.11, -1.67, 48.12))").fetchone()[0]
    print(f"   ✅ Works: {bbox[:80]}...")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 2: ST_GeomFromText with SRID
print("\n2. ST_GeomFromText with SRID:")
try:
    bbox = conn.execute("SELECT ST_AsText(ST_GeomFromText('POLYGON((-1.68 48.11, -1.67 48.11, -1.67 48.12, -1.68 48.12, -1.68 48.11))', 4326))").fetchone()[0]
    print(f"   ✅ Works: {bbox[:80]}...")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 3: Check if geometries in parcelles have SRID
print("\n3. Checking parcelles geometry SRID:")
try:
    sample = conn.execute("""
        SELECT id_parcelle, ST_AsText(geometry) as geom_text
        FROM parcelles
        WHERE code_commune LIKE '35%'
        LIMIT 1
    """).fetchone()
    print(f"   Parcel: {sample[0]}")
    print(f"   Geometry: {sample[1][:100]}...")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# Test 4: Try direct coordinate-based query (no transformation)
print("\n4. Testing simple bbox intersection (no transform):")
try:
    # Get bounding box of a sample parcel
    bbox_sample = conn.execute("""
        SELECT 
            ST_XMin(geometry) as min_x,
            ST_YMin(geometry) as min_y,
            ST_XMax(geometry) as max_x,
            ST_YMax(geometry) as max_y
        FROM parcelles
        WHERE code_commune LIKE '35%'
        LIMIT 1
    """).fetchone()
    print(f"   Sample parcel bbox (Lambert-93): {bbox_sample}")

    # Now try to find parcels in that area
    count = conn.execute("""
        SELECT COUNT(*)
        FROM parcelles
        WHERE code_commune LIKE '35%'
          AND ST_Intersects(
              geometry,
              ST_MakeEnvelope(?, ?, ?, ?)
          )
    """, [bbox_sample[0] - 100, bbox_sample[1] - 100, bbox_sample[2] + 100, bbox_sample[3] + 100]).fetchone()[0]
    print(f"   ✅ Found {count} parcels in Lambert-93 coordinates")

except Exception as e:
    print(f"   ❌ Failed: {e}")

conn.close()
