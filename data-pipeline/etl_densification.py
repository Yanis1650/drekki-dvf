"""ETL Densification v2 - Potentiel de Densification (ZAN).

Calcule le CES réel à partir de l'emprise au sol BDNB (s_geom_cstr)
et le potentiel de densification en comparant au CES potentiel
différencié par type d'usage.

Sources:
  - parcelles (cadastre, filtré leaf-level)
  - bdnb_stats.parquet (emprise_sol_m2, nb_niveau, type_usage, hauteur)

Output: Table densification_scores dans DuckDB.
"""

import time
from pathlib import Path

import duckdb
import polars as pl

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
BDNB_PARQUET = Path(__file__).parent.parent / "data" / "bdnb_stats.parquet"

TEST_DEPT = "35"


def main():
    print("=" * 60)
    print("ETL Densification v2 - Potentiel ZAN")
    print("=" * 60)

    start_time = time.time()

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    # ── Phase 1: Verification ────────────────────────────────────────
    print("\n--- Phase 1: Verification des sources ---")

    leaf_count = conn.execute(f"""
        SELECT COUNT(*) FROM parcelles
        WHERE code_commune LIKE '{TEST_DEPT}%'
          AND section IS NOT NULL AND numero IS NOT NULL
    """).fetchone()[0]
    print(f"  Parcelles leaf dept {TEST_DEPT}: {leaf_count:,}")

    if not BDNB_PARQUET.exists():
        print(f"  ERREUR: {BDNB_PARQUET} introuvable")
        return

    print(f"  BDNB: {BDNB_PARQUET.stat().st_size / 1e6:.0f} MB")

    # ── Phase 2: Load BDNB ───────────────────────────────────────────
    print("\n--- Phase 2: Chargement BDNB ---")

    bdnb = (
        pl.scan_parquet(str(BDNB_PARQUET))
        .filter(pl.col("parcelle_id").str.starts_with(TEST_DEPT))
        .select([
            pl.col("parcelle_id").alias("id_parcelle"),
            pl.col("emprise_sol_m2"),
            pl.col("hauteur_moyenne"),
            pl.col("nb_niveau"),
            pl.col("type_usage"),
        ])
        .collect()
    )
    conn.register("bdnb_temp", bdnb)
    print(f"  BDNB dept {TEST_DEPT}: {len(bdnb):,} parcelles")

    emprise_ok = bdnb.filter(pl.col("emprise_sol_m2").is_not_null() & (pl.col("emprise_sol_m2") > 0)).height
    print(f"  Avec emprise_sol > 0: {emprise_ok:,} ({100*emprise_ok/len(bdnb):.1f}%)")

    # ── Phase 3: Calcul CES + Potentiel ──────────────────────────────
    print("\n--- Phase 3: Calcul CES et potentiel ---")

    conn.execute("DROP TABLE IF EXISTS densification_scores")

    conn.execute(f"""
        CREATE TABLE densification_scores AS

        WITH parcelles_leaf AS (
            SELECT
                p.id_parcelle,
                p.code_commune,
                ST_Area(p.geometry) AS surface_parcelle_m2
            FROM parcelles p
            WHERE p.code_commune LIKE '{TEST_DEPT}%'
              AND p.section IS NOT NULL
              AND p.numero IS NOT NULL
              AND p.geometry IS NOT NULL
        ),

        enriched AS (
            SELECT
                p.id_parcelle,
                p.code_commune,
                p.surface_parcelle_m2,
                b.emprise_sol_m2,
                b.hauteur_moyenne,
                b.nb_niveau,
                b.type_usage,

                -- CES actuel = emprise / surface parcelle
                CASE
                    WHEN b.emprise_sol_m2 IS NOT NULL
                     AND b.emprise_sol_m2 > 0
                     AND p.surface_parcelle_m2 > 0
                    THEN LEAST(b.emprise_sol_m2 / p.surface_parcelle_m2, 1.0)
                    ELSE NULL
                END AS ces_actuel,

                -- Surface de plancher estimee
                CASE
                    WHEN b.emprise_sol_m2 IS NOT NULL AND b.nb_niveau IS NOT NULL
                        THEN b.emprise_sol_m2 * b.nb_niveau
                    WHEN b.emprise_sol_m2 IS NOT NULL AND b.hauteur_moyenne IS NOT NULL
                        THEN b.emprise_sol_m2 * GREATEST(1, ROUND(b.hauteur_moyenne / 3.0))
                    WHEN b.emprise_sol_m2 IS NOT NULL
                        THEN b.emprise_sol_m2
                    ELSE NULL
                END AS surface_plancher_m2,

                -- CES potentiel differencie par usage
                CASE
                    WHEN b.type_usage = 'Résidentiel collectif'  THEN 0.60
                    WHEN b.type_usage = 'Résidentiel individuel' THEN 0.40
                    WHEN b.type_usage = 'Tertiaire & Autres'     THEN 0.60
                    WHEN b.type_usage = 'Dépendance'             THEN 0.25
                    WHEN b.type_usage = 'Secondaire'             THEN 0.35
                    ELSE 0.40
                END AS ces_potentiel,

                -- Source du CES pour le score de confiance
                CASE
                    WHEN b.emprise_sol_m2 IS NOT NULL AND b.emprise_sol_m2 > 0
                        THEN 'bdnb_emprise'
                    WHEN b.type_usage IS NOT NULL
                        THEN 'bdnb_usage_only'
                    ELSE 'inconnu'
                END AS source_ces

            FROM parcelles_leaf p
            LEFT JOIN bdnb_temp b ON p.id_parcelle = b.id_parcelle
            WHERE p.surface_parcelle_m2 > 1
        ),

        scored AS (
            SELECT
                *,
                -- Potentiel de densification
                CASE
                    WHEN ces_actuel IS NOT NULL
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel)
                    WHEN source_ces = 'bdnb_usage_only'
                        THEN ces_potentiel * 0.5
                    ELSE NULL
                END AS potentiel_densification,

                -- Surface constructible
                CASE
                    WHEN ces_actuel IS NOT NULL AND surface_parcelle_m2 > 0
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel) * surface_parcelle_m2
                    ELSE NULL
                END AS surface_constructible_restante

            FROM enriched
        )

        SELECT
            id_parcelle,
            code_commune,
            surface_parcelle_m2,
            COALESCE(surface_plancher_m2, 0) AS surface_plancher_m2,
            emprise_sol_m2,
            ces_actuel,
            ces_potentiel,
            potentiel_densification,
            surface_constructible_restante,
            source_ces,
            type_usage,
            nb_niveau,
            CASE
                WHEN potentiel_densification IS NULL       THEN 'INCONNU'
                WHEN potentiel_densification >= 0.25       THEN 'FORT'
                WHEN potentiel_densification >= 0.10       THEN 'MOYEN'
                WHEN potentiel_densification > 0.02        THEN 'FAIBLE'
                ELSE                                            'SATURE'
            END AS categorie
        FROM scored
    """)

    # ── Phase 4: Index ───────────────────────────────────────────────
    print("\n--- Phase 4: Index ---")
    conn.execute("CREATE INDEX idx_densif_id ON densification_scores(id_parcelle)")
    conn.execute("CREATE INDEX idx_densif_commune ON densification_scores(code_commune)")
    conn.execute("CREATE INDEX idx_densif_cat ON densification_scores(categorie)")
    print("  Index: id_parcelle, code_commune, categorie")

    # ── Phase 5: Stats ───────────────────────────────────────────────
    print("\n--- Phase 5: Statistiques ---")

    total = conn.execute("SELECT COUNT(*) FROM densification_scores").fetchone()[0]
    print(f"  Total parcelles: {total:,}")

    distribution = conn.execute("""
        SELECT categorie, COUNT(*) as n,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
        FROM densification_scores
        GROUP BY categorie
        ORDER BY
            CASE categorie
                WHEN 'FORT' THEN 1 WHEN 'MOYEN' THEN 2
                WHEN 'FAIBLE' THEN 3 WHEN 'SATURE' THEN 4
                WHEN 'INCONNU' THEN 5
            END
    """).fetchall()

    print("\n  Distribution:")
    for cat, n, pct in distribution:
        bar = "#" * int(pct / 2)
        print(f"    {cat:10s} {n:>10,} ({pct:5.1f}%) {bar}")

    source_dist = conn.execute("""
        SELECT source_ces, COUNT(*) as n,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct
        FROM densification_scores
        GROUP BY source_ces
        ORDER BY n DESC
    """).fetchall()

    print("\n  Source CES:")
    for src, n, pct in source_dist:
        print(f"    {src:20s} {n:>10,} ({pct:5.1f}%)")

    stats = conn.execute("""
        SELECT
            ROUND(AVG(ces_actuel) * 100, 2) as ces_moy_pct,
            ROUND(MEDIAN(ces_actuel) * 100, 2) as ces_med_pct,
            ROUND(AVG(potentiel_densification) * 100, 2) as pot_moy_pct,
            ROUND(AVG(surface_constructible_restante), 0) as constr_moy_m2
        FROM densification_scores
        WHERE ces_actuel IS NOT NULL
    """).fetchone()

    print(f"\n  CES moyen:     {stats[0]}%")
    print(f"  CES median:    {stats[1]}%")
    print(f"  Potentiel moy: {stats[2]}%")
    print(f"  Surface constructible moy: {stats[3]:,.0f} m2")

    print("\n  Top 5 opportunites:")
    top5 = conn.execute("""
        SELECT id_parcelle, code_commune, type_usage,
               ROUND(surface_parcelle_m2) as surf,
               ROUND(ces_actuel * 100, 1) as ces_pct,
               ROUND(surface_constructible_restante) as constr
        FROM densification_scores
        WHERE categorie = 'FORT' AND surface_constructible_restante IS NOT NULL
        ORDER BY surface_constructible_restante DESC
        LIMIT 5
    """).fetchall()
    for i, (pid, com, usage, surf, ces, constr) in enumerate(top5, 1):
        print(f"    {i}. {pid} ({com}) {usage or '?'}: {surf:,.0f}m2, CES={ces}%, +{constr:,.0f}m2")

    conn.execute("DROP VIEW IF EXISTS bdnb_temp")
    conn.close()

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s — {total:,} parcelles")


if __name__ == "__main__":
    main()
