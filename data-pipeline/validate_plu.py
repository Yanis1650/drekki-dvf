"""Validation du mapping PLUi sur données réelles.

Vérifie que le taux de rnu_proximite sur les parcelles bâties
(emprise_sol_m2 > 0) d'une commune avec partition PLU connue
reste sous MAX_RNU_FALLBACK_RATE = 0.15.
N'échoue pas si la commune est absente de plu_commune_partition
(commune sans PLU GPU, fallback RNU est alors attendu).

Usage :
    python validate_plu.py data/dept35.duckdb
    python validate_plu.py data/dept35.duckdb --commune 35238
"""

import argparse
import sys
from pathlib import Path

import duckdb

# Seuil empirique : si > 15 % des parcelles bâties (emprise_sol_m2 > 0)
# d'une commune avec partition PLU connue restent en rnu_proximite, le
# mapping est probablement cassé (GeoPackage mal importé ou non exécuté).
MAX_RNU_FALLBACK_RATE = 0.15


def validate_plui_mapping(
    db_path: Path,
    code_commune: str = "35238",
) -> dict:
    """Vérifie que les parcelles bâties d'une commune PLUi ont bien source_ces = 'plu_gpu'.

    Returns:
        dict avec keys: commune, total_parcelles, distribution, partition_resolue,
                        has_plu_tables, built_total, rnu_rate_built, ok (bool)
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        conn.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass

    # Vérifie que les tables PLU sont présentes
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    has_plu = {"plu_zones", "plu_commune_partition"}.issubset(tables)

    # Distribution globale source_ces pour la commune
    rows = conn.execute(f"""
        SELECT source_ces, COUNT(*) AS n
        FROM densification_scores
        WHERE code_commune = '{code_commune}'
        GROUP BY source_ces
        ORDER BY n DESC
    """).fetchall()
    dist = {r[0]: r[1] for r in rows}
    total = sum(dist.values())

    # Taux rnu_proximite sur parcelles bâties (emprise_sol_m2 > 0) uniquement.
    # Les parcelles non bâties peuvent légitimement rester en rnu_proximite.
    built_rows = conn.execute(f"""
        SELECT source_ces, COUNT(*) AS n
        FROM densification_scores
        WHERE code_commune = '{code_commune}' AND emprise_sol_m2 > 0
        GROUP BY source_ces
    """).fetchall()
    built_dist = {r[0]: r[1] for r in built_rows}
    built_total = sum(built_dist.values())
    rnu_built = built_dist.get("rnu_proximite", 0)
    rnu_rate_built = rnu_built / max(built_total, 1)

    # Résolution partition PLUi
    partition = None
    if has_plu:
        row = conn.execute(
            f"SELECT partition FROM plu_commune_partition WHERE code_commune = '{code_commune}' LIMIT 1"
        ).fetchone()
        partition = row[0] if row else None

    conn.close()

    # Échec uniquement si la partition est connue et le taux dépasse le seuil.
    # Si partition is None : commune sans PLU GPU → rnu_proximite est normal → ok.
    ok = partition is None or rnu_rate_built <= MAX_RNU_FALLBACK_RATE

    return {
        "commune": code_commune,
        "total_parcelles": total,
        "distribution": dist,
        "partition_resolue": partition,
        "has_plu_tables": has_plu,
        "built_total": built_total,
        "rnu_rate_built": rnu_rate_built,
        "ok": ok,
    }


def _print_result(result: dict) -> None:
    thresh = MAX_RNU_FALLBACK_RATE * 100
    rate = result["rnu_rate_built"] * 100
    print(f"\n{'='*60}")
    print(f"  Validation PLUi — commune {result['commune']}")
    print(f"{'='*60}")
    print(f"  Tables PLU presentes   : {result['has_plu_tables']}")
    print(f"  Partition resolue      : {result['partition_resolue'] or 'NON TROUVEE'}")
    print(f"  Total parcelles        : {result['total_parcelles']:,}")
    print(f"  Parcelles baties (>0)  : {result['built_total']:,}  "
          f"rnu_proximite: {rate:.1f}%  (seuil {thresh:.0f}%)")
    print("\n  Distribution source_ces:")
    for source, n in sorted(result["distribution"].items(), key=lambda x: -x[1]):
        pct = n * 100 / max(result["total_parcelles"], 1)
        is_problem = (source == "rnu_proximite"
                      and result["partition_resolue"]
                      and rate > thresh)
        flag = " <- PROBLEME" if is_problem else ""
        print(f"    {source:<25} {n:>8,} ({pct:5.1f}%){flag}")

    if result["ok"]:
        print("\n  RESULTAT : OK — mapping PLUi fonctionnel")
    else:
        print(f"\n  RESULTAT : ECHEC — {rate:.1f}% parcelles baties en rnu_proximite (seuil {thresh:.0f}%)")
        print("  -> Verifier que import_plu.py a ete execute sur cette base")
        if not result["partition_resolue"]:
            print(f"  -> Commune {result['commune']} absente de plu_commune_partition")
            print("  -> Verifier que le GeoPackage GPU contient bien la commune (doc_urba)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Valide le mapping PLUi sur données réelles")
    parser.add_argument("db", type=Path, help="Chemin vers le fichier DuckDB (ex: data/dept35.duckdb)")
    parser.add_argument("--commune", default="35238", help="Code commune INSEE (défaut: 35238 Rennes)")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERREUR: {args.db} introuvable", file=sys.stderr)
        sys.exit(1)

    result = validate_plui_mapping(args.db, args.commune)
    _print_result(result)
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
