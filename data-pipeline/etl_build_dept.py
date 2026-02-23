"""ETL Build Department - Pipeline complet pour un departement.

Orchestre toutes les etapes ETL pour construire une base DuckDB autonome
par departement, prete a etre servie par l'API FastAPI.

Usage:
    python etl_build_dept.py 35
    python etl_build_dept.py 29 --skip-gpu
    python etl_build_dept.py 56 --bdtopo data/bdtopo_56.gpkg

Etapes:
    1. Golden Join    : mutations_aggregated x parcelles x BDNB
    2. Densification  : CES actuel + potentiel (source BDNB)
    3. GPU            : Zones PLU (INCONNU -> PLU categories)
    4. BD TOPO        : Emprise batie pour INCONNU residuels
    5. RNU            : Classification proximite pour restants
    6. Confidence     : Score de confiance global
    7. Optimize       : VACUUM + CHECKPOINT
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb

MAIN_DB = Path(__file__).parent.parent / "data" / "foncier.duckdb"
BDNB_PARQUET = Path(__file__).parent.parent / "data" / "bdnb_stats.parquet"
DATA_DIR = Path(__file__).parent.parent / "data"

GPU_WFS_URL = "https://data.geopf.fr/wfs/ows"

W_BDNB = 0.30
W_DVF = 0.25
W_DENSIF = 0.25
W_FRAICHEUR = 0.20

GRID_SIZE = 200


def parse_args():
    parser = argparse.ArgumentParser(description="Build per-department DuckDB")
    parser.add_argument("dept", help="Code departement (ex: 35, 29, 2A)")
    parser.add_argument("--skip-gpu", action="store_true",
                        help="Sauter le telechargement/integration GPU")
    parser.add_argument("--skip-bdtopo", action="store_true",
                        help="Sauter l'integration BD TOPO")
    parser.add_argument("--bdtopo", type=Path, default=None,
                        help="Chemin vers le GeoPackage BD TOPO")
    parser.add_argument("--output", type=Path, default=None,
                        help="Chemin de sortie (defaut: data/dept{DEPT}.duckdb)")
    return parser.parse_args()


def step_banner(step_num, title):
    print(f"\n{'='*60}")
    print(f"  Etape {step_num}/7 : {title}")
    print(f"{'='*60}")


def print_distribution(conn, label):
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


# =====================================================================
# STEP 1: Golden Join
# =====================================================================
def step_golden_join(conn, dept):
    step_banner(1, "Golden Join (mutations x parcelles x BDNB)")

    main_conn = duckdb.connect(str(MAIN_DB), read_only=True)
    main_conn.execute("LOAD spatial;")

    mut_count = main_conn.execute(
        f"SELECT COUNT(*) FROM mutations_aggregated WHERE code_commune LIKE '{dept}%'"
    ).fetchone()[0]
    print(f"  Mutations dept {dept}: {mut_count:,}")

    if mut_count == 0:
        print(f"  ERREUR: Aucune mutation pour le dept {dept}")
        main_conn.close()
        return False

    parc_count = main_conn.execute(f"""
        SELECT COUNT(*) FROM parcelles
        WHERE code_commune LIKE '{dept}%' AND section IS NOT NULL AND numero IS NOT NULL
    """).fetchone()[0]
    print(f"  Parcelles leaf dept {dept}: {parc_count:,}")

    print("  Export mutations...")
    conn.execute(f"""
        CREATE TABLE mutations_aggregated AS
        SELECT * FROM main_db.mutations_aggregated
        WHERE code_commune LIKE '{dept}%'
    """)

    print("  Export parcelles...")
    conn.execute(f"""
        CREATE TABLE parcelles AS
        SELECT * FROM main_db.parcelles
        WHERE code_commune LIKE '{dept}%'
    """)

    has_bdnb = BDNB_PARQUET.exists()
    if has_bdnb:
        print("  Export BDNB...")
        conn.execute(f"""
            CREATE TABLE bdnb_stats AS
            SELECT * FROM read_parquet('{BDNB_PARQUET.as_posix()}')
            WHERE parcelle_id LIKE '{dept}%'
        """)
        bdnb_count = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
        print(f"  BDNB: {bdnb_count:,}")

    main_conn.close()

    print("  Spatial join...")
    bdnb_cols = (
        "b.dpe_energie, b.annee_construction, b.hauteur_moyenne, "
        "b.nb_niveau, b.type_usage, b.nb_log"
    ) if has_bdnb else (
        "NULL AS dpe_energie, NULL AS annee_construction, "
        "NULL AS hauteur_moyenne, NULL AS nb_niveau, "
        "NULL AS type_usage, NULL AS nb_log"
    )
    bdnb_join = "LEFT JOIN bdnb_stats b ON mp.id_parcelle = b.parcelle_id" if has_bdnb else ""

    conn.execute(f"""
        CREATE TABLE france_foncier_test AS
        WITH mutations_dept AS (
            SELECT m.*,
                   ST_Transform(ST_Point(m.latitude, m.longitude),
                                'EPSG:4326', 'EPSG:2154') AS point_geom
            FROM mutations_aggregated m
            WHERE m.longitude IS NOT NULL AND m.latitude IS NOT NULL
        ),
        parcelles_dept AS (
            SELECT * FROM parcelles
            WHERE section IS NOT NULL AND numero IS NOT NULL
        ),
        mutation_parcelle_ranked AS (
            SELECT md.*, pd.id_parcelle, pd.geometry AS parcelle_geometry,
                   ROW_NUMBER() OVER (PARTITION BY md.id_mutation
                                      ORDER BY ST_Area(pd.geometry) ASC) AS rn
            FROM mutations_dept md
            LEFT JOIN parcelles_dept pd
                ON md.code_commune = pd.code_commune
                AND ST_Contains(pd.geometry, md.point_geom)
        ),
        mutation_parcelle AS (
            SELECT * FROM mutation_parcelle_ranked WHERE rn = 1
        )
        SELECT
            mp.id_mutation, mp.date_mutation, mp.nature_mutation,
            mp.valeur_fonciere, mp.code_commune,
            mp.parcelles AS dvf_parcelles,
            mp.surface_habitable_totale, mp.nombre_locaux, mp.prix_m2,
            mp.longitude, mp.latitude,
            mp.id_parcelle AS cadastre_parcelle_id,
            mp.parcelle_geometry AS geometry,
            {bdnb_cols}
        FROM mutation_parcelle mp
        {bdnb_join}
    """)

    count = conn.execute("SELECT COUNT(*) FROM france_foncier_test").fetchone()[0]
    print(f"  france_foncier_test: {count:,} rows")

    conn.execute("CREATE INDEX idx_fft_date ON france_foncier_test(date_mutation)")
    conn.execute("CREATE INDEX idx_fft_commune ON france_foncier_test(code_commune)")
    conn.execute("CREATE INDEX idx_fft_parcelle ON france_foncier_test(cadastre_parcelle_id)")

    return True


# =====================================================================
# STEP 2: Densification
# =====================================================================
def step_densification(conn, dept):
    step_banner(2, "Densification (CES actuel + potentiel)")

    has_bdnb = "bdnb_stats" in [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    conn.execute("DROP TABLE IF EXISTS densification_scores")
    conn.execute(f"""
        CREATE TABLE densification_scores AS
        WITH parcelles_leaf AS (
            SELECT p.id_parcelle, p.code_commune,
                   ST_Area(p.geometry) AS surface_parcelle_m2
            FROM parcelles p
            WHERE p.section IS NOT NULL AND p.numero IS NOT NULL
              AND p.geometry IS NOT NULL AND p.code_commune LIKE '{dept}%'
        ),
        enriched AS (
            SELECT
                p.id_parcelle, p.code_commune, p.surface_parcelle_m2,
                {'b.emprise_sol_m2' if has_bdnb else 'NULL AS emprise_sol_m2'},
                {'b.hauteur_moyenne' if has_bdnb else 'NULL AS hauteur_moyenne'},
                {'b.nb_niveau' if has_bdnb else 'NULL AS nb_niveau'},
                {'b.type_usage' if has_bdnb else "NULL AS type_usage"},
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.emprise_sol_m2' if has_bdnb else '0'} > 0
                     AND p.surface_parcelle_m2 > 0
                    THEN LEAST({'b.emprise_sol_m2' if has_bdnb else '0'} / p.surface_parcelle_m2, 1.0)
                    ELSE NULL
                END AS ces_actuel,
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.nb_niveau' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'} * {'b.nb_niveau' if has_bdnb else '1'}
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.hauteur_moyenne' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'} * GREATEST(1, ROUND({'b.hauteur_moyenne' if has_bdnb else '3'} / 3.0))
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'}
                    ELSE NULL
                END AS surface_plancher_m2,
                CASE
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Residentiel collectif'  THEN 0.60
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Residentiel individuel' THEN 0.40
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Tertiaire & Autres'     THEN 0.60
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Dependance'             THEN 0.25
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Secondaire'             THEN 0.35
                    ELSE 0.40
                END AS ces_potentiel,
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.emprise_sol_m2' if has_bdnb else '0'} > 0
                        THEN 'bdnb_emprise'
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN 'bdnb_usage_only'
                    ELSE 'inconnu'
                END AS source_ces
            FROM parcelles_leaf p
            {'LEFT JOIN bdnb_stats b ON p.id_parcelle = b.parcelle_id' if has_bdnb else ''}
            WHERE p.surface_parcelle_m2 > 1
        ),
        scored AS (
            SELECT *,
                CASE
                    WHEN ces_actuel IS NOT NULL
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel)
                    WHEN source_ces = 'bdnb_usage_only'
                        THEN ces_potentiel * 0.5
                    ELSE NULL
                END AS potentiel_densification,
                CASE
                    WHEN ces_actuel IS NOT NULL AND surface_parcelle_m2 > 0
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel) * surface_parcelle_m2
                    ELSE NULL
                END AS surface_constructible_restante
            FROM enriched
        )
        SELECT
            id_parcelle, code_commune, surface_parcelle_m2,
            COALESCE(surface_plancher_m2, 0) AS surface_plancher_m2,
            emprise_sol_m2, ces_actuel, ces_potentiel,
            potentiel_densification, surface_constructible_restante,
            source_ces, type_usage, nb_niveau,
            CASE
                WHEN potentiel_densification IS NULL  THEN 'INCONNU'
                WHEN potentiel_densification >= 0.25  THEN 'FORT'
                WHEN potentiel_densification >= 0.10  THEN 'MOYEN'
                WHEN potentiel_densification > 0.02   THEN 'FAIBLE'
                ELSE 'SATURE'
            END AS categorie
        FROM scored
    """)

    conn.execute("CREATE INDEX idx_densif_id ON densification_scores(id_parcelle)")
    conn.execute("CREATE INDEX idx_densif_commune ON densification_scores(code_commune)")
    conn.execute("CREATE INDEX idx_densif_cat ON densification_scores(categorie)")

    total = conn.execute("SELECT COUNT(*) FROM densification_scores").fetchone()[0]
    print(f"  densification_scores: {total:,} parcelles")
    print_distribution(conn, "Apres densification")


# =====================================================================
# STEP 3: GPU (PLU zones)
# =====================================================================
def step_gpu(conn, dept):
    step_banner(3, "GPU - Zones PLU")

    gpu_path = DATA_DIR / f"gpu_dept{dept}.geojson"

    if not gpu_path.exists():
        print(f"  Telechargement GPU dept {dept}...")
        ok = _download_gpu(dept, gpu_path)
        if not ok:
            print(f"  GPU non disponible -- skip")
            return
    else:
        size = gpu_path.stat().st_size / 1e6
        print(f"  Cache: {gpu_path.name} ({size:.1f} MB)")

    try:
        conn.execute("ALTER TABLE densification_scores ADD COLUMN libelle_zone VARCHAR")
    except duckdb.CatalogException:
        pass

    conn.execute("DROP TABLE IF EXISTS gpu_zones_raw")
    conn.execute(f"""
        CREATE TABLE gpu_zones_raw AS
        SELECT COALESCE(LIBELLE, TYPEZONE) AS libelle_zone,
               TYPEZONE AS typezone, geom AS geometry
        FROM ST_Read('{gpu_path.as_posix()}')
        WHERE TYPEZONE IS NOT NULL
    """)

    gpu_count = conn.execute("SELECT COUNT(*) FROM gpu_zones_raw").fetchone()[0]
    print(f"  Zones PLU: {gpu_count:,}")

    conn.execute("DROP TABLE IF EXISTS gpu_parcelles")
    conn.execute(f"""
        CREATE TABLE gpu_parcelles AS
        WITH parcelles_inconnu AS (
            SELECT d.id_parcelle, p.geometry, p.code_commune
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU' AND p.geometry IS NOT NULL
        ),
        matched AS (
            SELECT pi.id_parcelle, pi.code_commune,
                   g.typezone, g.libelle_zone,
                   ROW_NUMBER() OVER (PARTITION BY pi.id_parcelle
                       ORDER BY ST_Area(ST_Intersection(pi.geometry, g.geometry)) DESC
                   ) AS rn
            FROM parcelles_inconnu pi
            JOIN gpu_zones_raw g ON ST_Intersects(ST_Centroid(pi.geometry), g.geometry)
        )
        SELECT id_parcelle, code_commune, typezone, libelle_zone,
            CASE
                WHEN typezone = 'U'      THEN 'urbanise'
                WHEN typezone = 'AUc'    THEN 'a_urbaniser'
                WHEN typezone = 'AUs'    THEN 'a_urbaniser_strict'
                WHEN typezone LIKE 'AU%' THEN 'a_urbaniser'
                WHEN typezone = 'A'      THEN 'agricole'
                WHEN typezone = 'N'      THEN 'naturel'
                ELSE 'autre'
            END AS type_zone
        FROM matched WHERE rn = 1
    """)

    matched = conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]
    print(f"  Parcelles matchees: {matched:,}")

    conn.execute("""
        UPDATE densification_scores d SET
            source_ces = 'plu_gpu',
            libelle_zone = g.libelle_zone,
            potentiel_densification = CASE
                WHEN g.type_zone = 'urbanise'           THEN 0.40
                WHEN g.type_zone = 'a_urbaniser'        THEN 0.75
                WHEN g.type_zone = 'a_urbaniser_strict' THEN 0.50
                WHEN g.type_zone = 'agricole'           THEN 0.05
                WHEN g.type_zone = 'naturel'            THEN 0.02
                ELSE 0.10
            END,
            surface_constructible_restante = CASE
                WHEN g.type_zone IN ('agricole', 'naturel') THEN 0
                ELSE d.surface_parcelle_m2 * CASE
                    WHEN g.type_zone = 'urbanise'           THEN 0.40
                    WHEN g.type_zone = 'a_urbaniser'        THEN 0.75
                    WHEN g.type_zone = 'a_urbaniser_strict' THEN 0.50
                    ELSE 0.10
                END
            END,
            categorie = CASE
                WHEN g.type_zone IN ('agricole', 'naturel') THEN 'NON_MUTABLE'
                WHEN g.type_zone = 'a_urbaniser'            THEN 'FORT'
                WHEN g.type_zone = 'urbanise'               THEN 'MOYEN'
                WHEN g.type_zone = 'a_urbaniser_strict'     THEN 'MOYEN'
                ELSE 'FAIBLE'
            END
        FROM gpu_parcelles g
        WHERE d.id_parcelle = g.id_parcelle AND d.categorie = 'INCONNU'
    """)

    conn.execute("DROP TABLE IF EXISTS gpu_zones_raw")
    print_distribution(conn, "Apres GPU")


def _download_gpu(dept, output):
    try:
        import requests
        import json
    except ImportError:
        print("  pip install requests")
        return False

    print(f"  Recuperation partitions GPU dept {dept}...")
    params_list = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "wfs_du:zone_urba", "outputFormat": "application/json",
        "srsName": "EPSG:2154",
        "CQL_FILTER": f"partition LIKE 'DU_{dept}%'",
        "count": 1, "propertyName": "partition",
    }
    try:
        resp = requests.get(GPU_WFS_URL, params=params_list, timeout=120)
        resp.raise_for_status()
        sample = resp.json()
        partitions = sorted({
            f["properties"]["partition"]
            for f in sample.get("features", [])
        })
    except Exception:
        partitions = []

    if not partitions:
        print("  Telechargement bloc unique...")
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": "wfs_du:zone_urba", "outputFormat": "application/json",
            "srsName": "EPSG:2154",
            "CQL_FILTER": f"partition LIKE 'DU_{dept}%'",
            "count": 100000,
        }
        try:
            resp = requests.get(GPU_WFS_URL, params=params, timeout=600)
            resp.raise_for_status()
            output.write_text(resp.text, encoding="utf-8")
            nb = len(json.loads(resp.text).get("features", []))
            print(f"  {nb:,} zones -> {output.name}")
            return nb > 0
        except Exception as e:
            print(f"  Echec: {e}")
            return False

    all_features, crs_info, errors = [], None, 0
    for i, part in enumerate(partitions):
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": "wfs_du:zone_urba", "outputFormat": "application/json",
            "srsName": "EPSG:2154", "CQL_FILTER": f"partition = '{part}'",
            "count": 10000,
        }
        try:
            r = requests.get(GPU_WFS_URL, params=params, timeout=120)
            r.raise_for_status()
            d = r.json()
            all_features.extend(d.get("features", []))
            if crs_info is None:
                crs_info = d.get("crs")
        except Exception:
            errors += 1
        if (i + 1) % 50 == 0 or (i + 1) == len(partitions):
            print(f"    {i+1}/{len(partitions)} ({len(all_features):,} zones)")

    combined = {"type": "FeatureCollection", "crs": crs_info, "features": all_features}
    output.write_text(json.dumps(combined), encoding="utf-8")
    print(f"  {len(all_features):,} zones -> {output.name}")
    return len(all_features) > 0


# =====================================================================
# STEP 4: BD TOPO
# =====================================================================
def step_bdtopo(conn, dept, gpkg_path):
    step_banner(4, "BD TOPO (emprise batie)")

    if gpkg_path is None:
        gpkg_path = DATA_DIR / f"bdtopo_{dept}.gpkg"

    if not gpkg_path.exists():
        print(f"  BD TOPO non trouvee: {gpkg_path}")
        print(f"  -> Telecharger depuis https://geoservices.ign.fr/bdtopo")
        print(f"  -> Theme BATI, Dept {dept}, format GeoPackage")
        return

    print(f"  BD TOPO: {gpkg_path.name} ({gpkg_path.stat().st_size / 1e9:.1f} GB)")

    inconnu_before = conn.execute(
        "SELECT COUNT(*) FROM densification_scores WHERE categorie = 'INCONNU'"
    ).fetchone()[0]
    print(f"  INCONNU avant: {inconnu_before:,}")

    if inconnu_before == 0:
        print("  Aucun INCONNU restant -- skip")
        return

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    conn.execute(f"""
        CREATE TABLE bdtopo_bati AS
        SELECT
            cleabs AS id_bdtopo, nature, usage_1,
            CAST(hauteur AS DOUBLE) AS hauteur_m,
            CAST(nombre_d_etages AS INTEGER) AS nb_etages,
            ST_Area(geometrie) AS emprise_m2,
            geometrie AS geometry
        FROM ST_Read('{gpkg_path.as_posix()}', layer='batiment')
        WHERE (construction_legere IS NULL OR construction_legere = false)
          AND (etat_de_l_objet IS NULL OR etat_de_l_objet != 'Detruit')
          AND geometrie IS NOT NULL
    """)

    bati_count = conn.execute("SELECT COUNT(*) FROM bdtopo_bati").fetchone()[0]
    print(f"  Batiments charges: {bati_count:,}")

    conn.execute("DROP TABLE IF EXISTS _bdtopo_parcelle")
    conn.execute("""
        CREATE TEMP TABLE _bdtopo_parcelle AS
        SELECT
            p.id_parcelle,
            SUM(b.emprise_m2) AS emprise_bdtopo_m2,
            MAX(b.hauteur_m) AS hauteur_max_m,
            MAX(b.nb_etages) AS nb_etages_max,
            COUNT(*) AS nb_batiments,
            MAX(b.usage_1) AS usage_dominant
        FROM parcelles p
        JOIN bdtopo_bati b ON ST_Intersects(p.geometry, b.geometry)
        WHERE p.id_parcelle IN (
            SELECT id_parcelle FROM densification_scores WHERE categorie = 'INCONNU'
        )
        GROUP BY p.id_parcelle
    """)

    matched = conn.execute("SELECT COUNT(*) FROM _bdtopo_parcelle").fetchone()[0]
    print(f"  Parcelles INCONNU avec bati BD TOPO: {matched:,}")

    conn.execute("""
        CREATE TEMP TABLE _bdtopo_update AS
        SELECT
            bp.id_parcelle,
            bp.emprise_bdtopo_m2,
            CASE
                WHEN bp.nb_etages_max IS NOT NULL
                    THEN bp.emprise_bdtopo_m2 * bp.nb_etages_max
                WHEN bp.hauteur_max_m IS NOT NULL
                    THEN bp.emprise_bdtopo_m2 * GREATEST(1, ROUND(bp.hauteur_max_m / 3.0))
                ELSE bp.emprise_bdtopo_m2
            END AS surface_plancher_est,
            LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0) AS ces_actuel,
            0.40 AS ces_potentiel,
            GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) AS potentiel,
            GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0))
                * d.surface_parcelle_m2 AS surface_constr,
            CASE
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) >= 0.25 THEN 'FORT'
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) >= 0.10 THEN 'MOYEN'
                WHEN GREATEST(0.0, 0.40 - LEAST(bp.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0), 1.0)) > 0.02  THEN 'FAIBLE'
                ELSE 'SATURE'
            END AS new_categorie
        FROM _bdtopo_parcelle bp
        JOIN densification_scores d ON bp.id_parcelle = d.id_parcelle
    """)

    conn.execute("""
        UPDATE densification_scores d SET
            source_ces = 'bdtopo',
            emprise_sol_m2 = u.emprise_bdtopo_m2,
            surface_plancher_m2 = u.surface_plancher_est,
            ces_actuel = u.ces_actuel,
            ces_potentiel = u.ces_potentiel,
            potentiel_densification = u.potentiel,
            surface_constructible_restante = u.surface_constr,
            categorie = u.new_categorie
        FROM _bdtopo_update u
        WHERE d.id_parcelle = u.id_parcelle AND d.categorie = 'INCONNU'
    """)

    conn.execute("DROP TABLE IF EXISTS bdtopo_bati")
    print_distribution(conn, "Apres BD TOPO")


# =====================================================================
# STEP 5: RNU Classification
# =====================================================================
def step_rnu(conn, dept, gpkg_path):
    step_banner(5, "RNU (classification proximite)")

    inconnu = conn.execute(
        "SELECT COUNT(*) FROM densification_scores WHERE categorie = 'INCONNU'"
    ).fetchone()[0]
    print(f"  INCONNU restants: {inconnu:,}")

    if inconnu == 0:
        print("  Aucun INCONNU -- skip")
        return

    if gpkg_path is None:
        gpkg_path = DATA_DIR / f"bdtopo_{dept}.gpkg"

    has_bdtopo_table = "bdtopo_bati" in [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    if not has_bdtopo_table and gpkg_path.exists():
        print("  Chargement batiments BD TOPO pour grille RNU...")
        conn.execute(f"""
            CREATE TEMP TABLE _rnu_bati AS
            SELECT ST_Centroid(geometrie) AS pt
            FROM ST_Read('{gpkg_path.as_posix()}', layer='batiment')
            WHERE geometrie IS NOT NULL
              AND (construction_legere IS NULL OR construction_legere = false)
        """)
    elif has_bdtopo_table:
        conn.execute("""
            CREATE TEMP TABLE _rnu_bati AS
            SELECT ST_Centroid(geometry) AS pt FROM bdtopo_bati
        """)
    else:
        print("  Pas de BD TOPO -- skip RNU")
        return

    bati_count = conn.execute("SELECT COUNT(*) FROM _rnu_bati").fetchone()[0]
    print(f"  Batiments pour grille: {bati_count:,}")

    conn.execute(f"""
        CREATE TEMP TABLE _rnu_grid AS
        SELECT
            FLOOR(ST_X(pt) / {GRID_SIZE})::BIGINT AS gx,
            FLOOR(ST_Y(pt) / {GRID_SIZE})::BIGINT AS gy,
            COUNT(*) AS nb_buildings
        FROM _rnu_bati
        GROUP BY 1, 2
    """)

    conn.execute(f"""
        CREATE TEMP TABLE _rnu_grid_density AS
        SELECT
            g.gx, g.gy,
            g.nb_buildings + COALESCE(
                (SELECT SUM(g2.nb_buildings) FROM _rnu_grid g2
                 WHERE ABS(g2.gx - g.gx) <= 1 AND ABS(g2.gy - g.gy) <= 1
                   AND NOT (g2.gx = g.gx AND g2.gy = g.gy)),
                0
            ) AS nb_buildings
        FROM _rnu_grid g
    """)

    conn.execute(f"""
        CREATE TEMP TABLE _rnu_classification AS
        WITH parcel_grid AS (
            SELECT d.id_parcelle, d.surface_parcelle_m2,
                   FLOOR(ST_X(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gx,
                   FLOOR(ST_Y(ST_Centroid(p.geometry)) / {GRID_SIZE})::BIGINT AS gy
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU' AND p.geometry IS NOT NULL
        )
        SELECT pg.id_parcelle, pg.surface_parcelle_m2,
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

    conn.execute("""
        UPDATE densification_scores d SET
            source_ces = 'rnu_proximite',
            potentiel_densification = r.rnu_potentiel,
            surface_constructible_restante = r.rnu_potentiel * r.surface_parcelle_m2,
            categorie = r.rnu_categorie
        FROM _rnu_classification r
        WHERE d.id_parcelle = r.id_parcelle AND d.categorie = 'INCONNU'
    """)

    print_distribution(conn, "Apres RNU")


# =====================================================================
# STEP 6: Confidence Score
# =====================================================================
def step_confidence(conn, dept):
    step_banner(6, "Confidence Score")

    conn.execute("DROP TABLE IF EXISTS confidence_scores")
    conn.execute(f"""
        CREATE TABLE confidence_scores AS
        WITH raw_scores AS (
            SELECT
                d.id_parcelle,
                ROUND(CASE
                    WHEN f.dpe_energie IS NOT NULL AND f.annee_construction IS NOT NULL
                         AND f.hauteur_moyenne IS NOT NULL THEN 1.0
                    WHEN f.dpe_energie IS NOT NULL OR f.annee_construction IS NOT NULL THEN 0.6
                    WHEN f.cadastre_parcelle_id IS NOT NULL THEN 0.3
                    ELSE 0.0
                END, 2) AS score_bdnb,

                ROUND(CASE
                    WHEN tx_count >= 5  THEN 1.0
                    WHEN tx_count >= 3  THEN 0.8
                    WHEN tx_count >= 1  THEN 0.5
                    ELSE 0.0
                END, 2) AS score_dvf,

                ROUND(CASE
                    WHEN d.source_ces = 'bdnb_emprise'    THEN 1.0
                    WHEN d.source_ces = 'bdtopo'          THEN 0.85
                    WHEN d.source_ces = 'plu_gpu'         THEN 0.70
                    WHEN d.source_ces = 'rnu_proximite'   THEN 0.45
                    WHEN d.source_ces = 'bdnb_usage_only' THEN 0.4
                    WHEN d.categorie  = 'INCONNU'         THEN 0.1
                    ELSE 0.1
                END, 2) AS score_densification,

                ROUND(CASE
                    WHEN last_sale >= 2023 THEN 1.0
                    WHEN last_sale >= 2020 THEN 0.8
                    WHEN last_sale >= 2017 THEN 0.5
                    WHEN last_sale >= 2014 THEN 0.3
                    ELSE 0.0
                END, 2) AS score_fraicheur

            FROM densification_scores d
            LEFT JOIN (
                SELECT cadastre_parcelle_id,
                       COUNT(*) AS tx_count,
                       MAX(YEAR(date_mutation)) AS last_sale,
                       MAX(dpe_energie) AS dpe_energie,
                       MAX(annee_construction) AS annee_construction,
                       MAX(hauteur_moyenne) AS hauteur_moyenne
                FROM france_foncier_test
                GROUP BY cadastre_parcelle_id
            ) f ON d.id_parcelle = f.cadastre_parcelle_id
            WHERE d.code_commune LIKE '{dept}%'
        )
        SELECT
            id_parcelle,
            score_bdnb, score_dvf, score_densification, score_fraicheur,
            ROUND(
                score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR},
            2) AS confidence_global,
            CASE
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.75
                    THEN 'Elevee'
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.55
                    THEN 'Moyenne'
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.35
                    THEN 'Faible'
                ELSE 'Insuffisante'
            END AS confidence_label
        FROM raw_scores
    """)

    conn.execute("CREATE INDEX idx_conf_id ON confidence_scores(id_parcelle)")

    total = conn.execute("SELECT COUNT(*) FROM confidence_scores").fetchone()[0]
    dist = conn.execute("""
        SELECT confidence_label, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM confidence_scores GROUP BY 1
        ORDER BY CASE confidence_label
            WHEN 'Elevee' THEN 1 WHEN 'Moyenne' THEN 2
            WHEN 'Faible' THEN 3 ELSE 4
        END
    """).fetchall()

    print(f"  confidence_scores: {total:,}")
    for label, n, pct in dist:
        print(f"    {label:15s} {n:>10,} ({pct:5.1f}%)")


# =====================================================================
# STEP 7: Optimize
# =====================================================================
def step_optimize(conn, dept):
    step_banner(7, "Optimize (VACUUM + CHECKPOINT)")
    conn.execute("VACUUM")
    conn.execute("CHECKPOINT")

    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"  Tables: {', '.join(t[0] for t in tables)}")

    for t in tables:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"    {t[0]:30s} {cnt:>12,}")


# =====================================================================
# MAIN
# =====================================================================
def main():
    args = parse_args()
    dept = args.dept
    output_path = args.output or DATA_DIR / f"dept{dept}.duckdb"

    print("=" * 60)
    print(f"  FONCIER EXPRESS - Build dept {dept}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    global_start = time.time()

    if output_path.exists():
        output_path.unlink()
        print(f"  Ancien fichier supprime: {output_path.name}")

    conn = duckdb.connect(str(output_path))
    conn.execute("INSTALL spatial; LOAD spatial;")

    main_conn = duckdb.connect(str(MAIN_DB), read_only=True)
    conn.execute(f"ATTACH '{MAIN_DB.as_posix()}' AS main_db (READ_ONLY)")

    ok = step_golden_join(conn, dept)
    if not ok:
        print("\nAbandon: pas de donnees pour ce departement")
        conn.close()
        output_path.unlink(missing_ok=True)
        return

    try:
        conn.execute("DETACH main_db")
    except Exception:
        pass

    step_densification(conn, dept)

    if not args.skip_gpu:
        step_gpu(conn, dept)

    bdtopo = args.bdtopo
    if not args.skip_bdtopo:
        step_bdtopo(conn, dept, bdtopo)
        step_rnu(conn, dept, bdtopo)

    step_confidence(conn, dept)
    step_optimize(conn, dept)

    conn.close()

    size_mb = output_path.stat().st_size / 1e6
    elapsed = time.time() - global_start
    print(f"\n{'='*60}")
    print(f"  dept{dept}.duckdb genere: {size_mb:.0f} MB en {elapsed:.0f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
