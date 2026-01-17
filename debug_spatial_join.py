"""Debug spatial join issue - v3 - Fix axis order"""
import duckdb

conn = duckdb.connect("data/foncier.duckdb")
conn.execute("INSTALL spatial; LOAD spatial;")

# The issue: ST_Transform gives (6.3M, 2.6M) but cadastre is in (100k-1.2M, 450k-8.5M)
# This suggests the cadastre might already be in a different CRS or the parquet has SRID info

# Check a known point - Toulouse center should be around (571000, 6276000) in Lambert-93
print("=== Correct Lambert-93 for Toulouse ===")
print("  Expected: ~571000, 6276000")

# Test with swapped lat/lon in ST_Point (common issue)
print("\n=== Try swapped order ===")
test1 = conn.execute("""
    SELECT ST_AsText(ST_Transform(ST_Point(43.6047, 1.4442), 'EPSG:4326', 'EPSG:2154'))
""").fetchone()[0]
print(f"  ST_Point(lat, lon): {test1}")

# Try using explicit PROJ string
print("\n=== Cadastre centroid sample ===")
centroid = conn.execute("""
    SELECT ST_X(ST_Centroid(geometry)) as x, ST_Y(ST_Centroid(geometry)) as y
    FROM parcelles 
    WHERE code_commune LIKE '31%'
    LIMIT 5
""").fetchall()
for c in centroid:
    print(f"  Centroid: ({c[0]:.0f}, {c[1]:.0f})")

# Try finding parcels near Toulouse by checking X/Y ranges
print("\n=== Find Toulouse area parcels (X: 570000-575000, Y: 6270000-6280000) ===")
toulouse = conn.execute("""
    SELECT COUNT(*) FROM parcelles 
    WHERE ST_XMin(geometry) BETWEEN 570000 AND 575000
    AND ST_YMin(geometry) BETWEEN 6270000 AND 6280000
""").fetchone()[0]
print(f"  Parcels in Toulouse area: {toulouse}")

# Actually, let me check what code_commune looks like for Toulouse (31555)
print("\n=== Parcels for Toulouse (code 31555) ===")
toul = conn.execute("""
    SELECT COUNT(*) FROM parcelles WHERE code_commune = '31555'
""").fetchone()[0]
print(f"  Parcels in code 31555: {toul}")

# Check bounds of Toulouse parcels
print("\n=== Toulouse parcel bounds ===")
tbounds = conn.execute("""
    SELECT 
        MIN(ST_XMin(geometry)), MAX(ST_XMax(geometry)),
        MIN(ST_YMin(geometry)), MAX(ST_YMax(geometry))
    FROM parcelles WHERE code_commune = '31555'
""").fetchone()
print(f"  X: {tbounds[0]} to {tbounds[1]}")
print(f"  Y: {tbounds[2]} to {tbounds[3]}")

# Now try matching with a point in that range
print("\n=== Test point in Toulouse parcel range ===")
if tbounds[0]:
    test_x = (tbounds[0] + tbounds[1]) / 2
    test_y = (tbounds[2] + tbounds[3]) / 2
    print(f"  Test point: ({test_x:.0f}, {test_y:.0f})")

    match = conn.execute(f"""
        SELECT COUNT(*) FROM parcelles 
        WHERE ST_Contains(geometry, ST_Point({test_x}, {test_y}))
    """).fetchone()[0]
    print(f"  Parcels containing test point: {match}")
