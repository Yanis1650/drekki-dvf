"""Diagnostic spatial join - Dept 35 (Rennes).

Verifie l'inversion lon/lat et mesure l'impact du fix.
"""
import duckdb
from pathlib import Path

DB_PATH = Path("data/foncier.duckdb")

conn = duckdb.connect(str(DB_PATH), read_only=True)
conn.execute("INSTALL spatial; LOAD spatial;")

# ── 1. Valeurs brutes lon/lat dans mutations_aggregated ──────────────
print("=" * 70)
print("  1. Valeurs brutes longitude/latitude (Rennes = 35238)")
print("=" * 70)

sample = conn.execute("""
    SELECT longitude, latitude
    FROM mutations_aggregated
    WHERE code_commune = '35238'
      AND longitude IS NOT NULL
    LIMIT 5
""").fetchall()
for lon, lat in sample:
    print(f"  lon={lon:.6f}, lat={lat:.6f}")

print("\n  (Rennes attendu: lon ~ -1.68, lat ~ 48.11)")

# ── 2. Centroide des parcelles cadastrales Rennes ────────────────────
print("\n" + "=" * 70)
print("  2. Centroides parcelles cadastrales (Lambert-93, EPSG:2154)")
print("=" * 70)

centroids = conn.execute("""
    SELECT 
        id_parcelle,
        ST_X(ST_Centroid(geometry)) as x_l93,
        ST_Y(ST_Centroid(geometry)) as y_l93
    FROM parcelles
    WHERE code_commune = '35238'
    LIMIT 5
""").fetchall()
for pid, x, y in centroids:
    print(f"  {pid}: X={x:.0f}, Y={y:.0f}")

print("\n  (Rennes attendu en L93: X ~ 350000, Y ~ 6790000)")

# ── 3. Test projection avec les deux ordres ──────────────────────────
print("\n" + "=" * 70)
print("  3. Test ST_Point - ordres possibles")
print("=" * 70)

if sample:
    lon, lat = sample[0]

    # Ordre actuel (BUGGE?) : ST_Point(latitude, longitude)
    buggy = conn.execute(f"""
        SELECT ST_X(p) as x, ST_Y(p) as y
        FROM (SELECT ST_Transform(
            ST_Point({lat}, {lon}), 'EPSG:4326', 'EPSG:2154'
        ) as p)
    """).fetchone()
    print(f"  ST_Point(lat, lon) = ({buggy[0]:.0f}, {buggy[1]:.0f})  <-- code actuel")

    # Ordre corrige : ST_Point(longitude, latitude)
    fixed = conn.execute(f"""
        SELECT ST_X(p) as x, ST_Y(p) as y
        FROM (SELECT ST_Transform(
            ST_Point({lon}, {lat}), 'EPSG:4326', 'EPSG:2154'
        ) as p)
    """).fetchone()
    print(f"  ST_Point(lon, lat) = ({fixed[0]:.0f}, {fixed[1]:.0f})  <-- fix propose")

    print(f"\n  Centroide cadastre Rennes:  X ~ {centroids[0][1]:.0f}, Y ~ {centroids[0][2]:.0f}")
    print(f"  --> L'ordre {'ACTUEL (lat,lon)' if abs(buggy[0] - centroids[0][1]) < abs(fixed[0] - centroids[0][1]) else 'CORRIGE (lon,lat)'} est le bon.")

# ── 4. Test de match : combien de parcelles matchent avec chaque ordre ─
print("\n" + "=" * 70)
print("  4. Test de match spatial sur Rennes (35238) - 100 mutations")
print("=" * 70)

for label, point_expr in [
    ("ACTUEL  ST_Point(lat, lon)", "ST_Transform(ST_Point(m.latitude, m.longitude), 'EPSG:4326', 'EPSG:2154')"),
    ("CORRIGE ST_Point(lon, lat)", "ST_Transform(ST_Point(m.longitude, m.latitude), 'EPSG:4326', 'EPSG:2154')"),
]:
    result = conn.execute(f"""
        WITH sample_mutations AS (
            SELECT *
            FROM mutations_aggregated
            WHERE code_commune = '35238'
              AND longitude IS NOT NULL
            LIMIT 100
        ),
        matched AS (
            SELECT
                m.id_mutation,
                COUNT(p.id_parcelle) as nb_parcelles
            FROM sample_mutations m
            LEFT JOIN parcelles p
                ON p.code_commune = '35238'
                AND ST_Contains(p.geometry, {point_expr})
            GROUP BY m.id_mutation
        )
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN nb_parcelles = 1 THEN 1 END) as match_1,
            COUNT(CASE WHEN nb_parcelles = 0 THEN 1 END) as match_0,
            COUNT(CASE WHEN nb_parcelles > 1 THEN 1 END) as match_multi,
            ROUND(AVG(nb_parcelles), 2) as avg_match
        FROM matched
    """).fetchone()

    print(f"\n  {label}:")
    print(f"    Total: {result[0]}, Match=1: {result[1]}, Match=0: {result[2]}, Multi: {result[3]}, Avg: {result[4]}")

# ── 5. Distribution des doublons actuels dans france_foncier_test ────
print("\n" + "=" * 70)
print("  5. Distribution actuelle des doublons (france_foncier_test, Rennes)")
print("=" * 70)

dupes = conn.execute("""
    WITH counts AS (
        SELECT id_mutation, COUNT(*) as n
        FROM france_foncier_test
        WHERE code_commune = '35238'
        GROUP BY id_mutation
    )
    SELECT n as nb_parcelles, COUNT(*) as nb_mutations
    FROM counts
    GROUP BY n
    ORDER BY n
""").fetchall()

for n, cnt in dupes:
    print(f"  {n} parcelle(s)/mutation : {cnt:,} mutations")

conn.close()
print("\n" + "=" * 70)
print("  Diagnostic termine.")
print("=" * 70)
