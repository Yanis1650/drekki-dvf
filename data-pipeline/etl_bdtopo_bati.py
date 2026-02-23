"""ETL BD TOPO Bati - Emprise batie pour les INCONNU residuels.

Apres le GPU, certaines parcelles restent INCONNU car :
  1. Le GPU ne couvre pas toutes les communes (PLU en cours d'elaboration)
  2. La parcelle a un batiment mais aucune source ne l'a reference

Ce script utilise le GeoPackage BD TOPO IGN (batiments) pour effectuer
une jointure spatiale directe avec les parcelles cadastrales.

Telechargement BD TOPO :
  https://geoservices.ign.fr/bdtopo
  -> Theme BATI, Dept 35, format GeoPackage (~800 MB decompresse)

Cible: INCONNU passe de ~35% a < 10% (apres GPU).

Output: Met a jour densification_scores pour les INCONNU restants.
"""

import sys
import time
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
BDTOPO_GPKG = Path(__file__).parent.parent / "data" / "bdtopo_35.gpkg"
TEST_DEPT = "35"

BDTOPO_DOWNLOAD_URL = (
    "https://data.geopf.fr/telechargement/download/BDTOPO/BDTOPO_3-4_TOUSTHEMES_GPKG_LAMB93_D035_2025-03-15/"
    "BDTOPO_3-4_TOUSTHEMES_GPKG_LAMB93_D035_2025-03-15.7z"
)

CES_POTENTIEL_DEFAULT = 0.40


def print_distribution(conn, label):
    """Affiche la distribution des categories de densification."""
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
    print(f"ETL BD TOPO Bati - Emprise batie dept {TEST_DEPT}")
    print("=" * 60)

    start = time.time()

    if not BDTOPO_GPKG.exists():
        print(f"\n  ERREUR: {BDTOPO_GPKG} introuvable.")
        print(f"  -> Telecharger la BD TOPO IGN dept {TEST_DEPT}:")
        print(f"     {BDTOPO_DOWNLOAD_URL}")
        print(f"  -> Extraire le GeoPackage et le placer dans:")
        print(f"     {BDTOPO_GPKG}")
        print(f"\n  Alternative: copier le .gpkg depuis l'archive:")
        print(f"     BDTOPO_*/1_DONNEES_LIVRAISON_*/BDT_*_D0{TEST_DEPT}/BDT_*_D0{TEST_DEPT}.gpkg")
        return

    size_mb = BDTOPO_GPKG.stat().st_size / 1e6
    print(f"  BD TOPO: {BDTOPO_GPKG.name} ({size_mb:.0f} MB)")

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # -- Baseline ---------------------------------------------------
    baseline = print_distribution(conn, "Baseline avant BD TOPO")
    inconnu_before = sum(n for cat, n, _ in baseline if cat == "INCONNU")
    total = sum(n for _, n, _ in baseline)
    print(f"\n  INCONNU: {inconnu_before:,} / {total:,} "
          f"({100 * inconnu_before / total:.1f}%)")

    if inconnu_before == 0:
        print("\n  Aucune parcelle INCONNU. Rien a faire.")
        conn.close()
        return

    # -- Phase 1: Charger les batiments BD TOPO ---------------------
    print("\n--- Phase 1: Chargement BD TOPO batiments ---")

    gpkg_path = BDTOPO_GPKG.as_posix()

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    conn.execute(f"""
        CREATE TABLE bdtopo_bati AS
        SELECT
            cleabs            AS id_bdtopo,
            nature,
            usage_1,
            CAST(hauteur AS DOUBLE)          AS hauteur_m,
            CAST(nombre_d_etages AS INTEGER) AS nb_etages,
            ST_Area(geometrie)               AS emprise_m2,
            geometrie                        AS geometry
        FROM ST_Read('{gpkg_path}', layer='batiment')
        WHERE (construction_legere IS NULL OR construction_legere = false)
          AND (etat_de_l_objet IS NULL OR etat_de_l_objet != 'Detruit')
          AND geometrie IS NOT NULL
    """)

    bati_count = conn.execute("SELECT COUNT(*) FROM bdtopo_bati").fetchone()[0]
    emprise_avg = conn.execute(
        "SELECT ROUND(AVG(emprise_m2), 1) FROM bdtopo_bati WHERE emprise_m2 > 0"
    ).fetchone()[0]
    print(f"  Batiments charges: {bati_count:,}")
    print(f"  Emprise moyenne: {emprise_avg} m2")

    nature_dist = conn.execute("""
        SELECT nature, COUNT(*) as n FROM bdtopo_bati
        GROUP BY nature ORDER BY n DESC LIMIT 10
    """).fetchall()
    for nat, n in nature_dist:
        print(f"    {nat or '(null)':30s} {n:>8,}")

    # -- Phase 2: Spatial join BD TOPO -> parcelles INCONNU ---------
    print("\n--- Phase 2: Jointure spatiale BD TOPO -> parcelles INCONNU ---")

    conn.execute("DROP TABLE IF EXISTS bdtopo_parcelle")
    conn.execute(f"""
        CREATE TABLE bdtopo_parcelle AS
        SELECT
            p.id_parcelle,
            SUM(b.emprise_m2)   AS emprise_bdtopo_m2,
            MAX(b.hauteur_m)    AS hauteur_max_m,
            AVG(b.hauteur_m)    AS hauteur_moy_m,
            MAX(b.nb_etages)    AS nb_etages_max,
            MODE(b.usage_1)     AS usage_dominant,
            COUNT(*)            AS nb_batiments_bdtopo
        FROM parcelles p
        JOIN bdtopo_bati b ON ST_Intersects(p.geometry, b.geometry)
        WHERE p.code_commune LIKE '{TEST_DEPT}%'
          AND p.id_parcelle IN (
              SELECT id_parcelle FROM densification_scores
              WHERE categorie = 'INCONNU'
          )
        GROUP BY p.id_parcelle
    """)

    matched = conn.execute("SELECT COUNT(*) FROM bdtopo_parcelle").fetchone()[0]
    print(f"  Parcelles INCONNU avec batiment BD TOPO: {matched:,} "
          f"({100 * matched / max(inconnu_before, 1):.1f}%)")

    if matched > 0:
        stats = conn.execute("""
            SELECT
                ROUND(AVG(emprise_bdtopo_m2), 1) as emp_moy,
                ROUND(AVG(hauteur_moy_m), 1) as h_moy,
                ROUND(AVG(nb_batiments_bdtopo), 1) as nb_moy
            FROM bdtopo_parcelle
        """).fetchone()
        print(f"  Emprise moy: {stats[0]} m2, Hauteur moy: {stats[1]} m, "
              f"Nb bati moy: {stats[2]}")

    # -- Phase 3: Pre-calculer les valeurs --------------------------
    print("\n--- Phase 3: Calcul CES et potentiel ---")

    conn.execute("DROP TABLE IF EXISTS _bdtopo_update")
    conn.execute("""
        CREATE TEMP TABLE _bdtopo_update AS
        WITH raw AS (
            SELECT
                bt.id_parcelle,
                bt.emprise_bdtopo_m2,
                bt.hauteur_moy_m,
                bt.hauteur_max_m,
                bt.nb_batiments_bdtopo,
                bt.usage_dominant,
                bt.nb_etages_max,
                d.surface_parcelle_m2,
                LEAST(
                    bt.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0),
                    1.0
                ) AS ces_actuel,
                CASE bt.usage_dominant
                    WHEN 'Résidentiel'               THEN 0.40
                    WHEN 'Commercial et services'     THEN 0.55
                    WHEN 'Industriel'                 THEN 0.50
                    WHEN 'Agricole'                   THEN 0.25
                    WHEN 'Religieux'                  THEN 0.30
                    WHEN 'Sportif'                    THEN 0.35
                    ELSE 0.40
                END AS ces_potentiel
            FROM bdtopo_parcelle bt
            JOIN densification_scores d ON bt.id_parcelle = d.id_parcelle
            WHERE d.categorie = 'INCONNU'
        )
        SELECT
            id_parcelle,
            emprise_bdtopo_m2,
            hauteur_moy_m,
            usage_dominant,
            ces_actuel,
            ces_potentiel,
            GREATEST(0.0, ces_potentiel - ces_actuel) AS potentiel,
            GREATEST(0.0, ces_potentiel - ces_actuel)
                * surface_parcelle_m2 AS surface_constr,
            COALESCE(
                nb_etages_max,
                CASE WHEN hauteur_moy_m IS NOT NULL
                    THEN GREATEST(1, ROUND(hauteur_moy_m / 3.0))::INT
                    ELSE 1
                END
            ) AS nb_niveaux,
            CASE WHEN hauteur_moy_m IS NOT NULL
                THEN emprise_bdtopo_m2 * GREATEST(1,
                    COALESCE(nb_etages_max, ROUND(hauteur_moy_m / 3.0)))
                ELSE emprise_bdtopo_m2
            END AS plancher_m2,
            CASE
                WHEN GREATEST(0.0, ces_potentiel - ces_actuel) >= 0.25 THEN 'FORT'
                WHEN GREATEST(0.0, ces_potentiel - ces_actuel) >= 0.10 THEN 'MOYEN'
                WHEN GREATEST(0.0, ces_potentiel - ces_actuel) > 0.02  THEN 'FAIBLE'
                ELSE 'SATURE'
            END AS categorie
        FROM raw
    """)

    # -- Phase 4: Mise a jour densification_scores ------------------
    print("\n--- Phase 4: Mise a jour densification_scores ---")

    conn.execute("""
        UPDATE densification_scores d
        SET
            source_ces                     = 'bdtopo',
            emprise_sol_m2                 = u.emprise_bdtopo_m2,
            ces_actuel                     = u.ces_actuel,
            ces_potentiel                  = u.ces_potentiel,
            type_usage                     = u.usage_dominant,
            nb_niveau                      = u.nb_niveaux,
            surface_plancher_m2            = u.plancher_m2,
            potentiel_densification        = u.potentiel,
            surface_constructible_restante = u.surface_constr,
            categorie                      = u.categorie
        FROM _bdtopo_update u
        WHERE d.id_parcelle = u.id_parcelle
          AND d.categorie = 'INCONNU'
    """)

    changed = conn.execute("""
        SELECT COUNT(*) FROM densification_scores WHERE source_ces = 'bdtopo'
    """).fetchone()[0]
    print(f"  Parcelles mises a jour: {changed:,}")

    # -- Phase 5: Nettoyage et resultats ----------------------------
    conn.execute("DROP TABLE IF EXISTS _bdtopo_update")
    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    conn.execute("DROP TABLE IF EXISTS bdtopo_parcelle")

    after = print_distribution(conn, "Distribution apres BD TOPO")
    inconnu_after = sum(n for cat, n, _ in after if cat == "INCONNU")
    print(f"\n  INCONNU: {inconnu_before:,} -> {inconnu_after:,} "
          f"({100 * inconnu_after / total:.1f}%)")
    print(f"  Reduction: {inconnu_before - inconnu_after:,} parcelles reclassees")

    # Source CES
    src = conn.execute("""
        SELECT source_ces, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM densification_scores GROUP BY 1 ORDER BY 2 DESC
    """).fetchall()
    print("\n  Sources CES:")
    for s, n, pct in src:
        print(f"    {s:20s} {n:>10,} ({pct:5.1f}%)")

    # Top opportunites BD TOPO
    if changed > 0:
        print("\n  Top 5 opportunites BD TOPO:")
        top5 = conn.execute("""
            SELECT id_parcelle, code_commune,
                   ROUND(surface_parcelle_m2) as surf,
                   ROUND(ces_actuel * 100, 1) as ces_pct,
                   ROUND(surface_constructible_restante) as constr
            FROM densification_scores
            WHERE source_ces = 'bdtopo'
              AND surface_constructible_restante IS NOT NULL
            ORDER BY surface_constructible_restante DESC
            LIMIT 5
        """).fetchall()
        for i, (pid, com, surf, ces, constr) in enumerate(top5, 1):
            print(f"    {i}. {pid} ({com}): "
                  f"{surf:,.0f}m2, CES={ces}%, +{constr:,.0f}m2")

    conn.close()

    elapsed = time.time() - start
    print(f"\nTermine en {elapsed:.1f}s -- {changed:,} parcelles BD TOPO integrees")


if __name__ == "__main__":
    main()
