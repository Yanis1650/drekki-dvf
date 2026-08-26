"""Script d'orchestration du pipeline Foncier-Express pour un département.

Exécute toutes les étapes dans le bon ordre et s'arrête sur les erreurs critiques.

Ordre d'exécution
-----------------
1.  Téléchargement PLU/PLUi (WFS GPU)  — si data/plu_<DEPT>.gpkg absent
2.  Construction DB DuckDB              — etl_build_dept.py
    2a. Golden Join (mutations × parcelles × BDNB)
    2b. Densification (CES actuel + potentiel)
    2c. Import PLU (auto, depuis plu_<DEPT>.gpkg)
    2d. GPU — Zones PLU (parcelles INCONNU → catégories)
    2e. BD TOPO (emprise bâtie)
    2f. RNU (classification proximité)
    2g. Confidence Score
    2h. Optimize (VACUUM + CHECKPOINT)
3.  Migrations SQL                      — add_plu_datappro.sql, add_outlier_flag.sql
4.  Vérification post-migration         — preflight_check.py
5.  Validation PLU commune test         — validate_plu.py --commune <INSEE>
6.  Tests unitaires                     — pytest tests/ (option --no-tests pour sauter)

Usage
-----
    cd foncier-express
    python data-pipeline/run_pipeline.py 35
    python data-pipeline/run_pipeline.py 35 --commune 35238
    python data-pipeline/run_pipeline.py 35 --skip-download --no-tests
    python data-pipeline/run_pipeline.py 35 --gpkg data/plu_35.gpkg --skip-etl

Flags
-----
    --commune       Code INSEE pour la validation PLU (defaut: <DEPT>238 si existe)
    --skip-download Ne pas télécharger le PLU depuis WFS GPU si le .gpkg existe déjà
    --skip-etl      Sauter l'ETL (seulement migrations + vérifs)
    --skip-gpu      Passer l'étape GPU dans l'ETL
    --no-tests      Sauter les tests pytest
    --gpkg          Chemin GeoPackage PLU (defaut: data/plu_<DEPT>.gpkg)
    --db            Chemin DuckDB (defaut: data/dept<DEPT>.duckdb)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MIGRATIONS_DIR = ROOT / "migrations"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _hline(char: str = "=", width: int = 62) -> str:
    return char * width


def _banner(step: str, title: str) -> None:
    print(f"\n{_hline()}")
    print(f"  {step} : {title}")
    print(_hline())


def _run(cmd: list[str], cwd: Path = ROOT, critical: bool = True) -> int:
    """Lance une commande et retourne le code de retour."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(cwd))
    elapsed = time.time() - t0
    status = "OK" if result.returncode == 0 else f"ERREUR (code {result.returncode})"
    print(f"  [{status}] {elapsed:.0f}s")
    if result.returncode != 0 and critical:
        print(f"\nETAPE BLOQUANTE ECHOUEE — arrêt du pipeline.", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode


def _section_result(ok: bool, label: str) -> None:
    icon = "✓" if ok else "✗"
    print(f"  {icon}  {label}")


# ── Étapes ────────────────────────────────────────────────────────────────────

def step_download_plu(dept: str, gpkg: Path, force: bool = False) -> bool:
    """Télécharge le GeoPackage PLU depuis le WFS GPU si absent."""
    _banner("1/6", f"Téléchargement PLU/PLUi dept {dept}")
    if gpkg.exists() and not force:
        size_mb = gpkg.stat().st_size / 1e6
        print(f"  {gpkg.name} déjà présent ({size_mb:.0f} MB) — téléchargement ignoré")
        print(f"  (--skip-download pour ne jamais redemander, supprimer le fichier pour forcer)")
        return True

    rc = _run(
        [sys.executable, str(ROOT / "data-pipeline" / "download_plu_wfs.py"), dept,
         "--out", str(gpkg)],
        critical=False,
    )
    if rc != 0:
        print("  WARN: téléchargement PLU échoué — l'étape GPU sera sautée", file=sys.stderr)
        return False

    # Intégrer le ZIP PLUi s'il est présent à la racine
    zip_pattern = list(ROOT.glob(f"*PLUi*.zip")) + list(ROOT.glob(f"*plui*.zip"))
    if zip_pattern:
        print(f"\n  ZIP PLUi détecté : {zip_pattern[0].name}")
        _run_merge_plui(zip_pattern[0], gpkg, dept)
    return True


def _run_merge_plui(zip_path: Path, gpkg: Path, dept: str) -> None:
    """Intègre un ZIP PLUi CNIG dans le GeoPackage existant."""
    import zipfile, tempfile, shutil
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import shape

    # Trouver le SIREN dans le nom du ZIP (ex: 243500139_PLUi_20251218.zip)
    stem = zip_path.stem
    parts = stem.split("_")
    siren = parts[0] if parts[0].isdigit() and len(parts[0]) == 9 else None
    datappro = parts[-1] if len(parts[-1]) == 8 and parts[-1].isdigit() else "00000000"
    partition = f"DU_{siren}" if siren else f"DU_PLUI_{dept}"

    print(f"  Intégration PLUi {partition} (datappro={datappro})...")
    tmpdir = Path(tempfile.mkdtemp())
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmpdir)
        shp_candidates = list(tmpdir.rglob("*zone_urba*.shp"))
        if not shp_candidates:
            print("  WARN: aucun *zone_urba*.shp dans le ZIP — skip")
            return

        gdf_new = gpd.read_file(shp_candidates[0])
        gdf_new.columns = [c.lower() for c in gdf_new.columns]
        gdf_new["partition"] = partition
        if "idurba" not in gdf_new.columns:
            gdf_new["idurba"] = stem
        if "datappro" not in gdf_new.columns:
            gdf_new["datappro"] = datappro

        if gdf_new.crs and gdf_new.crs.to_epsg() != 2154:
            gdf_new = gdf_new.to_crs("EPSG:2154")

        # Charger zones existantes et fusionner
        gdf_existing = gpd.read_file(gpkg, layer="zone_urba")
        gdf_existing = gdf_existing[gdf_existing["partition"] != partition]
        common = (set(gdf_existing.columns) & set(gdf_new.columns)) | {"geometry"}
        gdf_merged = gpd.GeoDataFrame(
            pd.concat([
                gdf_existing[[c for c in gdf_existing.columns if c in common]],
                gdf_new[[c for c in gdf_new.columns if c in common]],
            ], ignore_index=True),
            geometry="geometry", crs="EPSG:2154",
        )
        gdf_merged.to_file(gpkg, layer="zone_urba", driver="GPKG")
        print(f"  zone_urba : {len(gdf_merged):,} zones après fusion")

        # Récupérer les communes du PLUi via WFS GPU doc_urba_com
        _add_plui_communes(gpkg, partition, datappro, siren)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    shutil.copy2(gpkg, gpkg.parent / f"plui_{dept}.gpkg")


def _add_plui_communes(gpkg: Path, partition: str, datappro: str, siren: str | None) -> None:
    import requests
    import geopandas as gpd
    import pandas as pd

    WFS = "https://data.geopf.fr/wfs/ows"
    commune_list: list[str] = []
    if siren:
        try:
            r = requests.get(WFS, params={
                "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                "TYPENAMES": "wfs_du:doc_urba_com", "outputFormat": "application/json",
                "count": 300, "CQL_FILTER": f"partition = '{partition}'",
            }, timeout=30)
            if r.status_code == 200:
                commune_list = [
                    str(f["properties"].get("insee") or f["properties"].get("commune", ""))
                    for f in r.json().get("features", [])
                    if f.get("properties")
                ]
                commune_list = [c for c in commune_list if len(c) in (4, 5)]
        except Exception as e:
            print(f"  WARN: WFS doc_urba_com : {e}")

    gdf_doc = gpd.read_file(gpkg, layer="doc_urba")
    gdf_doc = gdf_doc[gdf_doc["partition"] != partition]
    if commune_list:
        rows = []
        for code in commune_list:
            row = {col: None for col in gdf_doc.columns}
            row.update({"partition": partition, "code_commune": code,
                        "typedoc": "PLUi", "etat": "Opposable",
                        "datappro": datappro})
            if "siren" in row and siren:
                row["siren"] = siren
            rows.append(row)
        gdf_doc = pd.concat(
            [gdf_doc, gpd.GeoDataFrame(rows, geometry="geometry", crs=gdf_doc.crs)],
            ignore_index=True,
        )
        print(f"  doc_urba : {len(commune_list)} communes PLUi ajoutées")
    gdf_doc_final = gpd.GeoDataFrame(gdf_doc, geometry="geometry", crs=gdf_doc.crs)
    gdf_doc_final.to_file(gpkg, layer="doc_urba", driver="GPKG")


def step_etl(dept: str, db: Path, gpkg: Path, skip_gpu: bool = False) -> bool:
    """Lance l'ETL complet (reconstruit la base DuckDB)."""
    _banner("2/6", f"ETL complet dept {dept}")
    cmd = [sys.executable, str(ROOT / "data-pipeline" / "etl_build_dept.py"), dept,
           "--output", str(db)]
    if skip_gpu:
        cmd.append("--skip-gpu")
    if gpkg.exists():
        cmd += ["--gpkg", str(gpkg)]
    return _run(cmd, critical=True) == 0


def step_migrations(db: Path) -> bool:
    """Applique les migrations SQL idempotentes sur la base."""
    _banner("3/6", "Migrations SQL")
    import duckdb
    migrations = [
        MIGRATIONS_DIR / "add_plu_datappro.sql",
        MIGRATIONS_DIR / "add_outlier_flag.sql",
    ]
    if not db.exists():
        print(f"  ERREUR: base introuvable : {db}", file=sys.stderr)
        return False
    conn = duckdb.connect(str(db))
    ok = True
    for mig in migrations:
        if not mig.exists():
            print(f"  WARN: migration manquante : {mig.name}")
            continue
        try:
            conn.execute(mig.read_text(encoding="utf-8"))
            print(f"  {mig.name} : OK")
        except Exception as e:
            print(f"  {mig.name} : {e}")
            ok = False
    conn.close()
    return ok


def step_preflight(db: Path) -> bool:
    """Vérifie la cohérence du schéma post-migration."""
    _banner("4/6", "Vérification schéma (preflight)")
    rc = _run(
        [sys.executable, str(ROOT / "data-pipeline" / "preflight_check.py"), str(db)],
        critical=False,
    )
    return rc == 0


def step_validate_plu(db: Path, commune: str) -> bool:
    """Valide le mapping PLUi pour une commune test."""
    _banner("5/6", f"Validation PLU — commune {commune}")
    if not db.exists():
        print(f"  SKIP: base introuvable")
        return False
    rc = _run(
        [sys.executable, str(ROOT / "data-pipeline" / "validate_plu.py"),
         str(db), "--commune", commune],
        critical=False,
    )
    return rc == 0


def step_tests(dept: str) -> bool:
    """Lance la suite de tests pytest."""
    _banner("6/6", "Tests unitaires")
    rc = _run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
        critical=False,
    )
    return rc == 0


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline Foncier-Express — orchestration complète pour un département"
    )
    parser.add_argument("dept", help="Code département (ex: 35, 29, 2A)")
    parser.add_argument("--commune", default=None,
                        help="Code INSEE pour validation PLU (defaut: <DEPT>238)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Ne pas télécharger le PLU si le .gpkg existe déjà")
    parser.add_argument("--skip-etl", action="store_true",
                        help="Sauter l'ETL (migrations + vérifs uniquement)")
    parser.add_argument("--skip-gpu", action="store_true",
                        help="Sauter l'étape GPU dans l'ETL")
    parser.add_argument("--no-tests", action="store_true",
                        help="Sauter les tests pytest")
    parser.add_argument("--gpkg", type=Path, default=None,
                        help="GeoPackage PLU (defaut: data/plu_<DEPT>.gpkg)")
    parser.add_argument("--db", type=Path, default=None,
                        help="Base DuckDB cible (defaut: data/dept<DEPT>.duckdb)")
    args = parser.parse_args()

    dept     = args.dept
    db       = args.db   or (DATA_DIR / f"dept{dept}.duckdb")
    gpkg     = args.gpkg or (DATA_DIR / f"plu_{dept}.gpkg")
    commune  = args.commune or f"{dept}238"

    t_start = time.time()
    results: dict[str, bool | None] = {}

    print(_hline())
    print(f"  FONCIER EXPRESS — Pipeline dept {dept}")
    print(f"  DB   : {db}")
    print(f"  PLU  : {gpkg}")
    print(_hline())

    # ── 1. PLU download ───────────────────────────────────────────────────────
    if not args.skip_download or not gpkg.exists():
        results["plu_download"] = step_download_plu(dept, gpkg,
                                                    force=not args.skip_download)
    else:
        results["plu_download"] = True
        _banner("1/6", f"Téléchargement PLU/PLUi dept {dept}")
        print(f"  SKIP (--skip-download) — {gpkg.name} déjà présent")

    # ── 2. ETL ────────────────────────────────────────────────────────────────
    if not args.skip_etl:
        results["etl"] = step_etl(dept, db, gpkg, skip_gpu=args.skip_gpu)
    else:
        results["etl"] = None
        _banner("2/6", f"ETL complet dept {dept}")
        print("  SKIP (--skip-etl)")

    # ── 3. Migrations ─────────────────────────────────────────────────────────
    results["migrations"] = step_migrations(db)

    # ── 4. Preflight ──────────────────────────────────────────────────────────
    results["preflight"] = step_preflight(db)

    # ── 5. Validate PLU ───────────────────────────────────────────────────────
    results["validate_plu"] = step_validate_plu(db, commune)

    # ── 6. Tests ──────────────────────────────────────────────────────────────
    if not args.no_tests:
        results["tests"] = step_tests(dept)
    else:
        results["tests"] = None
        _banner("6/6", "Tests unitaires")
        print("  SKIP (--no-tests)")

    # ── Résumé ────────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{_hline()}")
    print(f"  RESUME — dept {dept} — {elapsed/60:.1f} min")
    print(_hline())

    label_map = {
        "plu_download": "1. Téléchargement PLU/PLUi",
        "etl":          "2. ETL complet",
        "migrations":   "3. Migrations SQL",
        "preflight":    "4. Vérification schéma",
        "validate_plu": "5. Validation PLU",
        "tests":        "6. Tests unitaires",
    }
    all_ok = True
    for key, label in label_map.items():
        v = results.get(key)
        if v is None:
            icon, note = "-", "SKIP"
        elif v:
            icon, note = "OK", "OK"
        else:
            icon, note = "KO", "ECHEC"
            all_ok = False
        print(f"  [{icon:2s}]  {label:35s} {note}")

    if db.exists():
        print(f"\n  Base DuckDB : {db.stat().st_size / 1e6:.0f} MB")

    print(_hline())
    if all_ok:
        print("  STATUT : PRET AU DEPLOIEMENT")
    else:
        print("  STATUT : ECHECS A CORRIGER")
        sys.exit(1)
    print(_hline())


if __name__ == "__main__":
    main()
