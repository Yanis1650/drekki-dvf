"""ETL RNU Classification - Parcelles INCONNU en communes sans PLU.

Les communes sans PLU numerise dans le GPU sont sous RNU
(Reglement National d'Urbanisme). Sous le RNU, la construction
n'est autorisee que dans les "parties urbanisees" de la commune.

Ce script utilise une grille spatiale (200m) et les batiments BD TOPO
pour determiner si une parcelle INCONNU est dans une zone batie ou non :
  - Zone batie dense (>= 10 batiments proches) -> MOYEN
  - Zone batie (>= 3 batiments proches)        -> FAIBLE
  - Zone batie isolee (1-2 batiments proches)   -> FAIBLE
  - Aucun batiment proche                       -> NON_MUTABLE

Cible: INCONNU passe de ~39% a < 10%.

Sources:
  - BD TOPO GeoPackage (batiment layer)
  - Table parcelles + densification_scores dans DuckDB
"""

import time
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
BDTOPO_GPKG = Path(__file__).parent.parent / "data" / "bdtopo_35.gpkg"
TEST_DEPT = "35"

GRID_SIZE = 200  # metres


def print_distribution(conn, label):
    """Affiche la distribution des categories."""
    rows = conn.execute("""
        SELECT categorie, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM densification_scores
        GROUP BY categorie
        ORDER BY CASE categorie
            WHEN 'FORT' THEN 1 WHEN 'MOYEN' THEN 2
            WHEN 'FAIBLE' THEN 3 WHEN 'SATURE' THEN 4
            WHEN 'NON_MUTABLE' THEN 5 WHEN 'INCONNU' THEN 6
        END
    """).fetchall()
    print(f"\n  {label}:")
    for cat, n, pct in rows:
        bar = "#" * int(pct / 2)
        print(f"    {cat:15s} {n:>10,} ({pct:5.1f}%) {bar}")
    return rows


def main():
    print("=" * 60)
    print(f"ETL RNU Classification - Communes sans PLU dept {TEST_DEPT}")
    print("=" * 60)

    start = time.time()

    if not BDTOPO_GPKG.exists():
        print(f"\n  ERREUR: {BDTOPO_GPKG} introuvable.")
        return

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # -- Baseline ---------------------------------------------------
    baseline = print_distribution(conn, "Baseline avant RNU")
    inconnu_before = sum(n for cat, n, _ in baseline if cat == "INCONNU")
    total = sum(n for _, n, _ in baseline)
    print(f"\n  INCONNU: {inconnu_before:,} / {total:,} "
          f"({100 * inconnu_before / total:.1f}%)")

    if inconnu_before == 0:
        print("\n  Aucune parcelle INCONNU. Rien a faire.")
        conn.close()
        return

    # -- Phase 1: Grille de densite batiment BD TOPO ----------------
    print("\n--- Phase 1: Grille de densite batiment (200m) ---")

    gpkg_path = BDTOPO_GPKG.as_posix()

    conn.execute("DROP TABLE IF EXISTS _rnu_grid_density")
    conn.execute(f"""
        CREATE TEMP TABLE _rnu_grid_density AS

        WITH building_centroids AS (
            SELECT
                ST_X(ST_Centroid(geometrie)) AS bx,
                ST_Y(ST_Centroid(geometrie)) AS by_
            FROM ST_Read('{gpkg_path}', layer='batiment')
            WHERE geometrie IS NOT NULL
              AND (construction_legere IS NULL OR construction_legere = false)
        ),

        building_cells AS (
            SELECT
                (FLOOR(bx / {GRID_SIZE})::BIGINT + dx) AS gx,
                (FLOOR(by_ / {GRID_SIZE})::BIGINT + dy) AS gy
            FROM building_centroids
            CROSS JOIN (SELECT UNNEST([-1, 0, 1]) AS dx) AS offx
            CROSS JOIN (SELECT UNNEST([-1, 0, 1]) AS dy) AS offy
        )

        SELECT gx, gy, COUNT(*) AS nb_buildings
        FROM building_cells
        GROUP BY gx, gy
    """)

    grid_stats = conn.execute("""
        SELECT COUNT(*) as cells,
               SUM(nb_buildings) as total_refs,
               ROUND(AVG(nb_buildings), 1) as avg_buildings
        FROM _rnu_grid_density
    """).fetchone()
    print(f"  Cellules avec batiments: {grid_stats[0]:,}")
    print(f"  Densite moyenne: {grid_stats[2]} batiments/cellule")

    # -- Phase 2: Classifier les parcelles INCONNU ------------------
    print("\n--- Phase 2: Classification des parcelles INCONNU ---")

    conn.execute("DROP TABLE IF EXISTS _rnu_classification")
    conn.execute(f"""
        CREATE TEMP TABLE _rnu_classification AS

        WITH parcel_grid AS (
            SELECT
                d.id_parcelle,
                d.surface_parcelle_m2,
                FLOOR(ST_X(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gx,
                FLOOR(ST_Y(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gy
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU'
              AND p.geometry IS NOT NULL
              AND p.code_commune LIKE '{TEST_DEPT}%'
        )

        SELECT
            pg.id_parcelle,
            pg.surface_parcelle_m2,
            COALESCE(g.nb_buildings, 0) AS nb_nearby,
            CASE
                WHEN COALESCE(g.nb_buildings, 0) >= 10 THEN 'MOYEN'
                WHEN COALESCE(g.nb_buildings, 0) >= 3  THEN 'FAIBLE'
                WHEN COALESCE(g.nb_buildings, 0) >= 1  THEN 'FAIBLE'
                ELSE 'NON_MUTABLE'
            END AS rnu_categorie,
            CASE
                WHEN COALESCE(g.nb_buildings, 0) >= 10 THEN 0.15
                WHEN COALESCE(g.nb_buildings, 0) >= 3  THEN 0.08
                WHEN COALESCE(g.nb_buildings, 0) >= 1  THEN 0.05
                ELSE 0.01
            END AS rnu_potentiel
        FROM parcel_grid pg
        LEFT JOIN _rnu_grid_density g ON pg.gx = g.gx AND pg.gy = g.gy
    """)

    classified = conn.execute("""
        SELECT rnu_categorie, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM _rnu_classification
        GROUP BY rnu_categorie ORDER BY 2 DESC
    """).fetchall()
    print("\n  Classification RNU:")
    for cat, n, pct in classified:
        print(f"    {cat:15s} {n:>10,} ({pct:5.1f}%)")

    rnu_total = conn.execute(
        "SELECT COUNT(*) FROM _rnu_classification"
    ).fetchone()[0]
    print(f"\n  Total classifie: {rnu_total:,} / {inconnu_before:,}")

    # -- Phase 3: Mise a jour densification_scores ------------------
    print("\n--- Phase 3: Mise a jour densification_scores ---")

    conn.execute("""
        UPDATE densification_scores d
        SET
            source_ces                     = 'rnu_proximite',
            potentiel_densification        = r.rnu_potentiel,
            surface_constructible_restante = r.rnu_potentiel * d.surface_parcelle_m2,
            categorie                      = r.rnu_categorie
        FROM _rnu_classification r
        WHERE d.id_parcelle = r.id_parcelle
          AND d.categorie = 'INCONNU'
    """)

    changed = conn.execute("""
        SELECT COUNT(*) FROM densification_scores WHERE source_ces = 'rnu_proximite'
    """).fetchone()[0]
    print(f"  Parcelles mises a jour: {changed:,}")

    # -- Phase 4: Nettoyage et resultats ----------------------------
    conn.execute("DROP TABLE IF EXISTS _rnu_grid_density")
    conn.execute("DROP TABLE IF EXISTS _rnu_classification")

    after = print_distribution(conn, "Distribution apres RNU")
    inconnu_after = sum(n for cat, n, _ in after if cat == "INCONNU")
    print(f"\n  INCONNU: {inconnu_before:,} -> {inconnu_after:,} "
          f"({100 * inconnu_after / total:.1f}%)")
    print(f"  Reduction: {inconnu_before - inconnu_after:,} parcelles reclassees")

    src = conn.execute("""
        SELECT source_ces, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM densification_scores GROUP BY 1 ORDER BY 2 DESC
    """).fetchall()
    print("\n  Sources CES:")
    for s, n, pct in src:
        print(f"    {s:20s} {n:>10,} ({pct:5.1f}%)")

    conn.close()

    elapsed = time.time() - start
    print(f"\nTermine en {elapsed:.1f}s -- {changed:,} parcelles RNU classifiees")


if __name__ == "__main__":
    main()
