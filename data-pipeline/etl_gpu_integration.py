"""ETL GPU Integration - Zones PLU dans densification_scores.

Telecharge les zones PLU du Geoportail de l'Urbanisme (GPU) via l'API WFS
de la Geoplateforme IGN, effectue une jointure spatiale avec les parcelles
cadastrales, et met a jour les parcelles INCONNU dans densification_scores.

Cible: INCONNU passe de ~62% a ~35%.

Sources:
  - GPU zone_urba via WFS IGN (ou cache local data/gpu_dept35.geojson)
  - Table parcelles dans DuckDB (geometries cadastrales Lambert-93)

Output: Met a jour densification_scores (source_ces, potentiel, categorie).
        Cree la table gpu_parcelles pour tracabilite.
"""

import time
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
GPU_GEOJSON = Path(__file__).parent.parent / "data" / "gpu_dept35.geojson"
TEST_DEPT = "35"

GPU_WFS_URL = "https://data.geopf.fr/wfs/ows"


def download_gpu_wfs(dept: str, output: Path) -> bool:
    """Telecharge les zones PLU via WFS IGN Geoplateforme (Lambert-93).

    Le WFS GPU limite a 5000 features et ne supporte pas startIndex.
    On telecharge commune par commune (partition = DU_{insee}).
    """
    try:
        import requests
    except ImportError:
        print("  ERREUR: pip install requests")
        return False

    import json

    # D'abord, obtenir la liste des partitions disponibles
    print(f"  Recuperation des partitions GPU dept {dept}...")
    params_list = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "wfs_du:zone_urba",
        "outputFormat": "application/json",
        "srsName": "EPSG:2154",
        "CQL_FILTER": f"partition LIKE 'DU_{dept}%'",
        "count": 5000,
        "propertyName": "partition",
    }

    try:
        resp = requests.get(GPU_WFS_URL, params=params_list, timeout=300)
        resp.raise_for_status()
    except requests.RequestException:
        # Fallback: telecharger d'un bloc avec count eleve
        print("  Fallback: telechargement en un bloc...")
        return _download_gpu_single(dept, output, requests, json)

    data = resp.json()
    partitions = sorted(set(
        f["properties"]["partition"]
        for f in data.get("features", [])
        if f.get("properties", {}).get("partition")
    ))
    print(f"  {len(partitions)} partitions trouvees")

    if not partitions:
        return _download_gpu_single(dept, output, requests, json)

    # Telecharger par partition (chaque commune a < 200 zones)
    all_features = []
    crs_info = None
    errors = 0

    for i, part in enumerate(partitions):
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "wfs_du:zone_urba",
            "outputFormat": "application/json",
            "srsName": "EPSG:2154",
            "CQL_FILTER": f"partition = '{part}'",
            "count": 5000,
        }
        try:
            r = requests.get(GPU_WFS_URL, params=params, timeout=120)
            r.raise_for_status()
            d = r.json()
            feats = d.get("features", [])
            all_features.extend(feats)
            if crs_info is None:
                crs_info = d.get("crs")
        except Exception:
            errors += 1

        if (i + 1) % 50 == 0 or (i + 1) == len(partitions):
            print(f"    {i + 1}/{len(partitions)} partitions "
                  f"({len(all_features):,} zones, {errors} erreurs)")

    combined = {
        "type": "FeatureCollection",
        "crs": crs_info,
        "features": all_features,
    }
    output.write_text(json.dumps(combined), encoding="utf-8")
    size_mb = output.stat().st_size / 1e6
    print(f"  {len(all_features):,} zones PLU -> {output.name} ({size_mb:.1f} MB)")
    return len(all_features) > 0


def _download_gpu_single(dept, output, requests, json):
    """Fallback: telecharger d'un seul bloc."""
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": "wfs_du:zone_urba",
        "outputFormat": "application/json",
        "srsName": "EPSG:2154",
        "CQL_FILTER": f"partition LIKE 'DU_{dept}%'",
        "count": 100000,
    }
    try:
        resp = requests.get(GPU_WFS_URL, params=params, timeout=600)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Echec: {e}")
        return False

    output.write_text(resp.text, encoding="utf-8")
    nb = len(json.loads(resp.text).get("features", []))
    size_mb = output.stat().st_size / 1e6
    print(f"  {nb:,} zones PLU -> {output.name} ({size_mb:.1f} MB)")
    return True


def print_distribution(conn, label: str):
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
    print(f"ETL GPU Integration - Zones PLU dept {TEST_DEPT}")
    print("=" * 60)

    start = time.time()

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # -- Baseline ---------------------------------------------------
    baseline = print_distribution(conn, "Baseline avant GPU")
    inconnu_before = sum(n for cat, n, _ in baseline if cat == "INCONNU")
    total = sum(n for _, n, _ in baseline)
    print(f"\n  INCONNU: {inconnu_before:,} / {total:,} "
          f"({100 * inconnu_before / total:.1f}%)")

    # -- Phase 1: Recuperer les donnees GPU -------------------------
    print("\n--- Phase 1: Donnees GPU ---")

    if not GPU_GEOJSON.exists():
        ok = download_gpu_wfs(TEST_DEPT, GPU_GEOJSON)
        if not ok:
            print("\n  Telechargement automatique echoue.")
            print("  -> Telecharger manuellement les zones PLU :")
            print("    1. https://www.geoportail-urbanisme.gouv.fr/")
            print(f"    2. Chercher PLU departement {TEST_DEPT}")
            print("    3. Exporter en GeoJSON (EPSG:2154)")
            print(f"    4. Sauvegarder : {GPU_GEOJSON}")
            conn.close()
            return
    else:
        size = GPU_GEOJSON.stat().st_size / 1e6
        print(f"  Cache existant: {GPU_GEOJSON.name} ({size:.1f} MB)")

    # -- Phase 2: Charger les zones GPU dans DuckDB -----------------
    print("\n--- Phase 2: Chargement GPU dans DuckDB ---")

    conn.execute("DROP TABLE IF EXISTS gpu_zones_raw")
    gpu_path = GPU_GEOJSON.as_posix()

    conn.execute(f"""
        CREATE TABLE gpu_zones_raw AS
        SELECT
            COALESCE(LIBELLE, TYPEZONE)  AS libelle_zone,
            TYPEZONE                     AS typezone,
            geom                         AS geometry
        FROM ST_Read('{gpu_path}')
        WHERE TYPEZONE IS NOT NULL
    """)

    gpu_count = conn.execute("SELECT COUNT(*) FROM gpu_zones_raw").fetchone()[0]
    print(f"  Zones PLU chargees: {gpu_count:,}")

    zone_dist = conn.execute("""
        SELECT typezone, COUNT(*) as n FROM gpu_zones_raw
        GROUP BY 1 ORDER BY 2 DESC
    """).fetchall()
    for tz, n in zone_dist:
        print(f"    {tz:6s} {n:>6,}")

    # -- Phase 3: Jointure spatiale GPU -> parcelles INCONNU --------
    print("\n--- Phase 3: Jointure spatiale GPU -> parcelles INCONNU ---")

    conn.execute("DROP TABLE IF EXISTS gpu_parcelles")
    conn.execute(f"""
        CREATE TABLE gpu_parcelles AS

        WITH parcelles_inconnu AS (
            SELECT d.id_parcelle, p.geometry, p.code_commune
            FROM densification_scores d
            JOIN parcelles p ON d.id_parcelle = p.id_parcelle
            WHERE d.categorie = 'INCONNU'
              AND p.geometry IS NOT NULL
              AND p.code_commune LIKE '{TEST_DEPT}%'
        ),

        matched AS (
            SELECT
                pi.id_parcelle,
                pi.code_commune,
                g.typezone,
                g.libelle_zone,
                ROW_NUMBER() OVER (
                    PARTITION BY pi.id_parcelle
                    ORDER BY ST_Area(ST_Intersection(pi.geometry, g.geometry)) DESC
                ) AS rn
            FROM parcelles_inconnu pi
            JOIN gpu_zones_raw g
                ON ST_Intersects(ST_Centroid(pi.geometry), g.geometry)
        )

        SELECT
            id_parcelle,
            code_commune,
            typezone,
            libelle_zone,
            CASE
                WHEN typezone = 'U'      THEN 'urbanise'
                WHEN typezone = 'AUc'    THEN 'a_urbaniser'
                WHEN typezone = 'AUs'    THEN 'a_urbaniser_strict'
                WHEN typezone LIKE 'AU%' THEN 'a_urbaniser'
                WHEN typezone = 'A'      THEN 'agricole'
                WHEN typezone = 'N'      THEN 'naturel'
                ELSE 'autre'
            END AS type_zone
        FROM matched
        WHERE rn = 1
    """)

    matched_count = conn.execute("SELECT COUNT(*) FROM gpu_parcelles").fetchone()[0]
    print(f"  Parcelles matchees: {matched_count:,} / {inconnu_before:,} "
          f"({100 * matched_count / max(inconnu_before, 1):.1f}%)")

    match_dist = conn.execute("""
        SELECT type_zone, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM gpu_parcelles GROUP BY 1 ORDER BY 2 DESC
    """).fetchall()
    for tz, n, pct in match_dist:
        print(f"    {tz:25s} {n:>8,} ({pct:5.1f}%)")

    # -- Phase 4: Ajouter la colonne libelle_zone si absente --------
    try:
        conn.execute(
            "ALTER TABLE densification_scores ADD COLUMN libelle_zone VARCHAR"
        )
    except duckdb.CatalogException:
        pass

    # -- Phase 5: Mise a jour densification_scores ------------------
    print("\n--- Phase 5: Mise a jour densification_scores ---")

    conn.execute("""
        UPDATE densification_scores d
        SET
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
        WHERE d.id_parcelle = g.id_parcelle
          AND d.categorie = 'INCONNU'
    """)

    changed = conn.execute("""
        SELECT COUNT(*) FROM densification_scores WHERE source_ces = 'plu_gpu'
    """).fetchone()[0]
    print(f"  Parcelles mises a jour: {changed:,}")

    # -- Phase 6: Index sur la nouvelle colonne ---------------------
    try:
        conn.execute(
            "CREATE INDEX idx_densif_zone ON densification_scores(libelle_zone)"
        )
    except duckdb.CatalogException:
        pass

    # -- Phase 7: Resultats -----------------------------------------
    after = print_distribution(conn, "Distribution apres GPU")
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

    conn.execute("DROP TABLE IF EXISTS gpu_zones_raw")
    conn.close()

    elapsed = time.time() - start
    print(f"\nTermine en {elapsed:.1f}s -- {changed:,} parcelles GPU integrees")


if __name__ == "__main__":
    main()
