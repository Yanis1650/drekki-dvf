"""Rejoue la seule etape densification, sur une base deja construite.

    cd data-pipeline
    python -m etl_build_steps.densification_cli 35
    python -m etl_build_steps.densification_cli 35 --db ../data/dept35.duckdb

C'est ce que faisait `data-pipeline/etl_densification.py`, une seconde
implementation de la meme etape dont la formule avait diverge. La reprise
manuelle passe desormais par `step_densification`, la seule que le pipeline
execute et que `tests/test_densification_step.py` couvre.

Ce module est a part de l'etape parce que `etl_build_steps/__init__.py`
importe `densification` : lancer `python -m etl_build_steps.densification`
executerait le module une seconde fois, sous le nom `__main__`, et Python le
signalerait a chaque appel.
"""

import argparse
from pathlib import Path

import duckdb

from .config import BDNB_PARQUET, MAIN_DB
from .densification import step_densification


def charger_bdnb(conn, dept: str, parquet: Path = BDNB_PARQUET) -> bool:
    """Cree `bdnb_stats` depuis le Parquet BDNB si la table manque.

    Le pipeline complet la cree a l'etape golden join ; relancer la seule
    densification sur une base qui ne l'a pas donnerait des categories
    INCONNU partout. Le filtre et la forme sont ceux de `golden_join.py`.

    Rend True si la table est disponible a la sortie.
    """
    if "bdnb_stats" in [r[0] for r in conn.execute("SHOW TABLES").fetchall()]:
        return True
    if not parquet.exists():
        print(f"  BDNB introuvable ({parquet}) : les categories seront INCONNU")
        return False
    print(f"  Chargement BDNB depuis {parquet.name}...")
    conn.execute(f"""
        CREATE TABLE bdnb_stats AS
        SELECT * FROM read_parquet('{parquet.as_posix()}')
        WHERE parcelle_id LIKE '{dept}%'
    """)
    total = conn.execute("SELECT COUNT(*) FROM bdnb_stats").fetchone()[0]
    print(f"  BDNB dept {dept}: {total:,} parcelles")
    return True


def main(argv=None) -> int:
    """Rejoue la densification seule sur une base existante."""
    parser = argparse.ArgumentParser(
        description="Rejoue l'etape densification sur une base deja construite",
    )
    parser.add_argument("dept", help="Code departement (ex: 35, 29, 2A)")
    parser.add_argument(
        "--db",
        type=Path,
        default=MAIN_DB,
        help=f"Base DuckDB a mettre a jour (defaut : {MAIN_DB})",
    )
    parser.add_argument(
        "--bdnb",
        type=Path,
        default=BDNB_PARQUET,
        help=f"Parquet BDNB, lu si la base n'a pas `bdnb_stats` (defaut : {BDNB_PARQUET})",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"ERREUR: base introuvable : {args.db}")
        return 1

    conn = duckdb.connect(str(args.db))
    try:
        conn.execute("INSTALL spatial; LOAD spatial;")
        charger_bdnb(conn, args.dept, args.bdnb)
        step_densification(conn, args.dept)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
