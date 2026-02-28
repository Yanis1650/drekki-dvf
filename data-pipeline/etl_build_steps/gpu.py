"""Step 3: GPU (PLU zones)."""
import json

import duckdb

from .config import DATA_DIR, GPU_WFS_URL
from .utils import print_distribution, step_banner


def _download_gpu(dept, output):
    try:
        import requests
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
