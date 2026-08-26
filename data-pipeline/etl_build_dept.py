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
import logging
import time
from pathlib import Path

import duckdb
from etl_build_steps import (
    DATA_DIR,
    MAIN_DB,
    step_bdtopo,
    step_confidence,
    step_densification,
    step_golden_join,
    step_gpu,
    step_optimize,
    step_rnu,
)

logger = logging.getLogger(__name__)

try:
    from validate_plu import validate_plui_mapping as _validate_plu
except ImportError:
    _validate_plu = None

try:
    from import_plu import import_plu_into_duckdb as _import_plu
except ImportError:
    _import_plu = None


def _auto_import_plu(conn, dept: str, gpkg_override=None) -> None:
    """Importe les tables PLU dans la base en cours de construction.

    Appelé automatiquement entre step_densification et step_gpu.
    Sans GeoPackage disponible, l'étape GPU sera sautée (warning déjà géré dans gpu.py).
    """
    if _import_plu is None:
        return
    gpkg = gpkg_override or (DATA_DIR / f"plu_{dept}.gpkg")
    if not gpkg.exists():
        print(f"\n  INFO: {gpkg.name} absent — import PLU saute (GPU step sautera)")
        return
    print(f"\n  Import PLU depuis {gpkg.name}...")
    conn.execute("INSTALL spatial; LOAD spatial;")
    result = _import_plu(conn, gpkg, dept)
    print(f"  PLU OK: {result['communes']} communes, {result['zones']} zones")


def parse_args():
    parser = argparse.ArgumentParser(description="Build per-department DuckDB")
    parser.add_argument("dept", help="Code departement (ex: 35, 29, 2A)")
    parser.add_argument(
        "--skip-gpu",
        action="store_true",
        help="Sauter le telechargement/integration GPU",
    )
    parser.add_argument(
        "--skip-bdtopo",
        action="store_true",
        help="Sauter l'integration BD TOPO",
    )
    parser.add_argument(
        "--bdtopo",
        type=Path,
        default=None,
        help="Chemin vers le GeoPackage BD TOPO",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Chemin de sortie (defaut: data/dept{DEPT}.duckdb)",
    )
    parser.add_argument(
        "--gpkg",
        type=Path,
        default=None,
        help="GeoPackage PLU (defaut: data/plu_<DEPT>.gpkg)",
    )
    return parser.parse_args()


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
    conn.execute(f"ATTACH '{MAIN_DB.as_posix()}' AS main_db (READ_ONLY)")

    ok = step_golden_join(conn, dept)
    if not ok:
        print("\nAbandon: pas de donnees pour ce departement")
        conn.close()
        output_path.unlink(missing_ok=True)
        return

    try:
        conn.execute("DETACH main_db")
    except Exception as e:
        logger.debug("DETACH main_db skipped (may not be attached): %s", e)

    step_densification(conn, dept)

    if not args.skip_gpu:
        _auto_import_plu(conn, dept, getattr(args, "gpkg", None))
        step_gpu(conn, dept)
        # Validation non-bloquante : log si le seuil est dépassé, ne fait jamais échouer l'ETL.
        if _validate_plu is not None:
            try:
                val = _validate_plu(output_path)
                if not val["ok"]:
                    logger.warning(
                        "PLUi mapping degrade — commune %s: %.0f%% parcelles baties en rnu_proximite (seuil 15%%)",
                        val["commune"], val["rnu_rate_built"] * 100,
                    )
                    print(f"  WARN: PLUi mapping potentiellement casse pour commune {val['commune']}"
                          f" — {val['rnu_rate_built']*100:.0f}% rnu_proximite (seuil 15%)")
                else:
                    logger.debug("PLUi validation OK commune %s", val["commune"])
            except Exception as e:
                logger.warning("Validation PLU echouee (non bloquant): %s", e)

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
