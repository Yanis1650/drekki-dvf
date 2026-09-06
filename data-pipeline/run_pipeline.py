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
import sys
import time
from pathlib import Path

from pipeline_steps import (
    DATA_DIR,
    step_download_plu,
    step_etl,
    step_migrations,
    step_preflight,
    step_tests,
    step_validate_plu,
)
from pipeline_steps.console import _banner, _hline


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
