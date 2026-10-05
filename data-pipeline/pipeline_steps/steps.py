"""Les six etapes du pipeline departemental, dans leur ordre d'execution."""

from __future__ import annotations

import sys
from pathlib import Path

from pipeline_steps.console import _banner, _run
from pipeline_steps.paths import MIGRATIONS_DIR, ROOT
from pipeline_steps.plui import _run_merge_plui


def step_download_plu(dept: str, gpkg: Path, force: bool = False) -> bool:
    """Télécharge le GeoPackage PLU depuis le WFS GPU si absent."""
    _banner("1/6", f"Téléchargement PLU/PLUi dept {dept}")
    if gpkg.exists() and not force:
        size_mb = gpkg.stat().st_size / 1e6
        print(f"  {gpkg.name} déjà présent ({size_mb:.0f} MB) — téléchargement ignoré")
        print("  (--skip-download pour ne jamais redemander, supprimer le fichier pour forcer)")
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
    zip_pattern = list(ROOT.glob("*PLUi*.zip")) + list(ROOT.glob("*plui*.zip"))
    if zip_pattern:
        print(f"\n  ZIP PLUi détecté : {zip_pattern[0].name}")
        _run_merge_plui(zip_pattern[0], gpkg, dept)
    return True


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
        print("  SKIP: base introuvable")
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
