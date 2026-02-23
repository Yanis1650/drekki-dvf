"""Diagnostic doublons parcelles - Pourquoi 5-6 matches par mutation?"""
import duckdb
from pathlib import Path

conn = duckdb.connect(str(Path("data/foncier.duckdb")), read_only=True)
conn.execute("INSTALL spatial; LOAD spatial;")

COMMUNE = "35238"  # Rennes

print("=" * 70)
print(f"  DIAGNOSTIC DOUBLONS PARCELLES — Commune {COMMUNE}")
print("=" * 70)

# ── 1. Parcelles totales vs distinctes ───────────────────────────────
print("\n--- 1. Comptage parcelles Rennes ---")
r1 = conn.execute(f"""
    SELECT
        COUNT(*)                        AS total_rows,
        COUNT(DISTINCT id_parcelle)     AS parcelles_distinctes
    FROM parcelles
    WHERE code_commune = '{COMMUNE}'
""").fetchone()
print(f"  Total lignes:           {r1[0]:,}")
print(f"  id_parcelle distincts:  {r1[1]:,}")
print(f"  Ratio:                  {r1[0]/r1[1]:.2f}x" if r1[1] > 0 else "  N/A")

# ── 2. Distribution des doublons par id_parcelle ─────────────────────
print("\n--- 2. Distribution doublons par id_parcelle ---")
dupes = conn.execute(f"""
    WITH counts AS (
        SELECT id_parcelle, COUNT(*) as n
        FROM parcelles
        WHERE code_commune = '{COMMUNE}'
        GROUP BY id_parcelle
    )
    SELECT n, COUNT(*) as nb_parcelles
    FROM counts
    GROUP BY n
    ORDER BY n
""").fetchall()
for n, cnt in dupes:
    print(f"  {n} occurrence(s): {cnt:,} parcelles")

# ── 3. Exemple concret : une mutation, ses matches ───────────────────
print("\n--- 3. Exemple : 1 mutation, tous ses matches parcelles ---")
example = conn.execute(f"""
    SELECT id_mutation, cadastre_parcelle_id
    FROM france_foncier_test
    WHERE code_commune = '{COMMUNE}'
    LIMIT 10
""").fetchall()

if example:
    mut_id = example[0][0]
    print(f"  Mutation: {mut_id}")
    matches = conn.execute(f"""
        SELECT cadastre_parcelle_id, dpe_energie, hauteur_moyenne
        FROM france_foncier_test
        WHERE id_mutation = '{mut_id}'
    """).fetchall()
    for pid, dpe, h in matches:
        print(f"    -> parcelle={pid}, dpe={dpe}, hauteur={h}")

# ── 4. Checker si id_parcelle est NULL (et si c'est le NULL qui duplique) ─
print("\n--- 4. Parcelles NULL dans france_foncier_test (Rennes) ---")
r4 = conn.execute(f"""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN cadastre_parcelle_id IS NULL THEN 1 END) as null_parcelle,
        COUNT(CASE WHEN cadastre_parcelle_id IS NOT NULL THEN 1 END) as with_parcelle
    FROM france_foncier_test
    WHERE code_commune = '{COMMUNE}'
""").fetchone()
print(f"  Total lignes: {r4[0]:,}")
print(f"  Parcelle NULL: {r4[1]:,}")
print(f"  Parcelle renseignee: {r4[2]:,}")

# ── 5. Vérifier si les id_parcelle sont identiques ou différents ─────
print("\n--- 5. Matches par mutation : memes ou differentes parcelles ? ---")
r5 = conn.execute(f"""
    WITH mutation_matches AS (
        SELECT 
            id_mutation,
            COUNT(*) as total_matches,
            COUNT(DISTINCT cadastre_parcelle_id) as parcelles_distinctes,
            COUNT(CASE WHEN cadastre_parcelle_id IS NULL THEN 1 END) as null_matches
        FROM france_foncier_test
        WHERE code_commune = '{COMMUNE}'
        GROUP BY id_mutation
    )
    SELECT
        COUNT(*) as mutations,
        ROUND(AVG(total_matches), 2) as avg_total,
        ROUND(AVG(parcelles_distinctes), 2) as avg_distinctes,
        ROUND(AVG(null_matches), 2) as avg_null,
        COUNT(CASE WHEN total_matches = parcelles_distinctes THEN 1 END) as toutes_differentes,
        COUNT(CASE WHEN parcelles_distinctes = 1 AND total_matches > 1 THEN 1 END) as meme_parcelle_dupliquee
    FROM mutation_matches
""").fetchone()
print(f"  Mutations: {r5[0]:,}")
print(f"  Avg matches/mutation: {r5[1]}")
print(f"  Avg parcelles distinctes/mutation: {r5[2]}")
print(f"  Avg NULL matches/mutation: {r5[3]}")
print(f"  Mutations ou toutes les parcelles sont differentes: {r5[4]:,}")
print(f"  Mutations ou c'est la meme parcelle dupliquee: {r5[5]:,}")

# ── 6. Vérifier la table parcelles : colonnes section/prefixe ────────
print("\n--- 6. Schema et echantillon de la table parcelles ---")
cols = conn.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'parcelles'
    ORDER BY ordinal_position
""").fetchall()
for name, dtype in cols:
    print(f"  {name:30s} {dtype}")

print("\n  Echantillon (5 parcelles Rennes):")
sample = conn.execute(f"""
    SELECT * EXCLUDE(geometry), 
           ST_X(ST_Centroid(geometry)) as cx, 
           ST_Y(ST_Centroid(geometry)) as cy
    FROM parcelles
    WHERE code_commune = '{COMMUNE}'
    LIMIT 10
""").fetchall()
col_names = [c[0] for c in conn.execute(f"""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'parcelles'
    ORDER BY ordinal_position
""").fetchall()]
col_names = [c for c in col_names if c != 'geometry'] + ['cx', 'cy']
for row in sample:
    for cname, val in zip(col_names, row):
        print(f"    {cname}: {val}")
    print("    ---")

# ── 7. Test direct : 1 point, combien de parcelles uniques le contiennent ─
print("\n--- 7. Test spatial direct : 1 point dans combien de parcelles ? ---")
point_test = conn.execute(f"""
    SELECT latitude, longitude
    FROM mutations_aggregated
    WHERE code_commune = '{COMMUNE}' AND longitude IS NOT NULL
    LIMIT 1
""").fetchone()

if point_test:
    lat, lon = point_test
    print(f"  Point test: lat={lat}, lon={lon}")
    
    r7 = conn.execute(f"""
        SELECT 
            COUNT(*) as total_matches,
            COUNT(DISTINCT id_parcelle) as parcelles_distinctes
        FROM parcelles
        WHERE code_commune = '{COMMUNE}'
          AND ST_Contains(
                geometry,
                ST_Transform(ST_Point({lat}, {lon}), 'EPSG:4326', 'EPSG:2154')
              )
    """).fetchone()
    print(f"  Total matches: {r7[0]}")
    print(f"  Parcelles distinctes: {r7[1]}")
    
    details = conn.execute(f"""
        SELECT id_parcelle, section, numero,
               ST_Area(geometry) as area_m2
        FROM parcelles
        WHERE code_commune = '{COMMUNE}'
          AND ST_Contains(
                geometry,
                ST_Transform(ST_Point({lat}, {lon}), 'EPSG:4326', 'EPSG:2154')
              )
        ORDER BY area_m2
    """).fetchall()
    for pid, sec, num, area in details:
        print(f"    parcelle={pid}, section={sec}, numero={num}, area={area:.0f} m2")

conn.close()
print("\n" + "=" * 70)
print("  Diagnostic termine.")
print("=" * 70)
