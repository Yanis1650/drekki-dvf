"""ETL Confidence Score - Score de confiance par parcelle.

Agrège la qualité de chaque source de données en un score global [0, 1]
qui permet à l'utilisateur de savoir à quel point on peut se fier aux
chiffres affichés sur une parcelle donnée.

Composantes:
  - score_bdnb (30%)        : richesse des données bâtiment BDNB
  - score_dvf (25%)         : profondeur historique des transactions
  - score_densification (25%): qualité du score ZAN/densification
  - score_fraicheur (20%)   : récence de la dernière vente

Output: Table confidence_scores dans DuckDB.
"""

import time
from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
TEST_DEPT = "35"

W_BDNB = 0.30
W_DVF = 0.25
W_DENSIF = 0.25
W_FRAICHEUR = 0.20


def main():
    print("=" * 60)
    print("ETL Confidence Score")
    print("=" * 60)

    start_time = time.time()

    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    conn.execute("DROP TABLE IF EXISTS confidence_scores")

    print("\n--- Creation de confidence_scores ---")

    conn.execute(f"""
        CREATE TABLE confidence_scores AS

        WITH parcelle_dvf AS (
            SELECT
                cadastre_parcelle_id              AS id_parcelle,
                code_commune,
                COUNT(*)                          AS nb_transactions,
                MAX(TRY_CAST(date_mutation AS DATE)) AS derniere_mutation,

                -- BDNB: presences par parcelle (agrege sur toutes les transactions)
                BOOL_OR(dpe_energie IS NOT NULL)           AS has_dpe,
                BOOL_OR(annee_construction IS NOT NULL)    AS has_annee,
                BOOL_OR(hauteur_moyenne IS NOT NULL)       AS has_hauteur,
                BOOL_OR(nb_niveau IS NOT NULL)             AS has_niveaux,
                BOOL_OR(type_usage IS NOT NULL)            AS has_usage

            FROM france_foncier_test
            WHERE cadastre_parcelle_id IS NOT NULL
            GROUP BY cadastre_parcelle_id, code_commune
        ),

        with_scores AS (
            SELECT
                p.id_parcelle,
                p.code_commune,
                p.nb_transactions,
                p.derniere_mutation,

                -- ─── Composante 1 : BDNB (30%) ─────────────────────
                -- Richesse des attributs batiment disponibles
                ROUND((
                    CASE WHEN d.emprise_sol_m2 IS NOT NULL
                          AND d.emprise_sol_m2 > 0         THEN 0.35 ELSE 0.0 END
                  + CASE WHEN p.has_niveaux                THEN 0.25 ELSE 0.0 END
                  + CASE WHEN p.has_annee                  THEN 0.15 ELSE 0.0 END
                  + CASE WHEN p.has_dpe                    THEN 0.15 ELSE 0.0 END
                  + CASE WHEN p.has_usage                  THEN 0.10 ELSE 0.0 END
                ), 2) AS score_bdnb,

                -- ─── Composante 2 : DVF (25%) ──────────────────────
                -- Plus de transactions = meilleure vision du marche
                ROUND(CASE
                    WHEN p.nb_transactions >= 4 THEN 1.0
                    WHEN p.nb_transactions = 3  THEN 0.9
                    WHEN p.nb_transactions = 2  THEN 0.75
                    ELSE                             0.55
                END, 2) AS score_dvf,

                -- ─── Composante 3 : Densification (25%) ─────────────
                -- Qualite du calcul ZAN
                ROUND(CASE
                    WHEN d.source_ces = 'bdnb_emprise'    THEN 1.0
                    WHEN d.source_ces = 'bdtopo'          THEN 0.85
                    WHEN d.source_ces = 'plu_gpu'         THEN 0.70
                    WHEN d.source_ces = 'rnu_proximite'   THEN 0.45
                    WHEN d.source_ces = 'bdnb_usage_only' THEN 0.4
                    WHEN d.categorie  = 'INCONNU'         THEN 0.1
                    WHEN d.id_parcelle IS NULL             THEN 0.0
                    ELSE                                        0.1
                END, 2) AS score_densification,

                -- ─── Composante 4 : Fraicheur (20%) ─────────────────
                -- Recence de la derniere transaction
                ROUND(CASE
                    WHEN YEAR(p.derniere_mutation) >= 2024 THEN 1.0
                    WHEN YEAR(p.derniere_mutation) >= 2022 THEN 0.8
                    WHEN YEAR(p.derniere_mutation) >= 2020 THEN 0.6
                    WHEN YEAR(p.derniere_mutation) >= 2017 THEN 0.4
                    ELSE                                        0.2
                END, 2) AS score_fraicheur,

                -- Metadata densification
                d.source_ces,
                d.categorie AS categorie_densification

            FROM parcelle_dvf p
            LEFT JOIN densification_scores d ON p.id_parcelle = d.id_parcelle
        ),

        final AS (
            SELECT
                *,

                -- Score global pondere
                ROUND(
                    score_bdnb           * {W_BDNB}
                  + score_dvf            * {W_DVF}
                  + score_densification  * {W_DENSIF}
                  + score_fraicheur      * {W_FRAICHEUR}
                , 2) AS confidence_global

            FROM with_scores
        )

        SELECT
            id_parcelle,
            code_commune,
            confidence_global,
            score_bdnb,
            score_dvf,
            score_densification,
            score_fraicheur,
            nb_transactions,
            derniere_mutation,
            source_ces,
            categorie_densification,

            CASE
                WHEN confidence_global >= 0.75 THEN 'Elevee'
                WHEN confidence_global >= 0.55 THEN 'Moyenne'
                WHEN confidence_global >= 0.35 THEN 'Faible'
                ELSE                                'Insuffisante'
            END AS confidence_label

        FROM final
    """)

    # Index
    conn.execute("CREATE INDEX idx_conf_parcelle ON confidence_scores(id_parcelle)")
    conn.execute("CREATE INDEX idx_conf_commune ON confidence_scores(code_commune)")

    # ── Stats ─────────────────────────────────────────────────────────
    print("\n--- Statistiques ---")

    total = conn.execute("SELECT COUNT(*) FROM confidence_scores").fetchone()[0]
    print(f"  Total parcelles: {total:,}")

    # Distribution des labels
    labels = conn.execute("""
        SELECT confidence_label, COUNT(*) as n,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct,
               ROUND(AVG(confidence_global), 3) as score_moy
        FROM confidence_scores
        GROUP BY confidence_label
        ORDER BY score_moy DESC
    """).fetchall()

    print("\n  Distribution confiance:")
    for lab, n, pct, moy in labels:
        bar = "#" * int(pct / 2)
        print(f"    {lab:15s} {n:>8,} ({pct:5.1f}%)  score moy={moy:.3f}  {bar}")

    # Distribution du score global
    print("\n  Percentiles score global:")
    pctiles = conn.execute("""
        SELECT
            ROUND(MIN(confidence_global), 2) as p0,
            ROUND(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY confidence_global), 2) as p10,
            ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY confidence_global), 2) as p25,
            ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY confidence_global), 2) as p50,
            ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY confidence_global), 2) as p75,
            ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY confidence_global), 2) as p90,
            ROUND(MAX(confidence_global), 2) as p100
        FROM confidence_scores
    """).fetchone()
    print(f"    min={pctiles[0]}  p10={pctiles[1]}  p25={pctiles[2]}  "
          f"p50={pctiles[3]}  p75={pctiles[4]}  p90={pctiles[5]}  max={pctiles[6]}")

    # Moyenne par composante
    print("\n  Moyennes par composante:")
    avgs = conn.execute("""
        SELECT
            ROUND(AVG(score_bdnb), 3) as bdnb,
            ROUND(AVG(score_dvf), 3) as dvf,
            ROUND(AVG(score_densification), 3) as densif,
            ROUND(AVG(score_fraicheur), 3) as fraicheur
        FROM confidence_scores
    """).fetchone()
    print(f"    BDNB:           {avgs[0]:.3f}  (poids {W_BDNB})")
    print(f"    DVF:            {avgs[1]:.3f}  (poids {W_DVF})")
    print(f"    Densification:  {avgs[2]:.3f}  (poids {W_DENSIF})")
    print(f"    Fraicheur:      {avgs[3]:.3f}  (poids {W_FRAICHEUR})")

    # Croisement confiance x densification
    print("\n  Croisement confiance x densification:")
    cross = conn.execute("""
        SELECT
            confidence_label,
            categorie_densification,
            COUNT(*) as n
        FROM confidence_scores
        WHERE categorie_densification IS NOT NULL
        GROUP BY confidence_label, categorie_densification
        ORDER BY confidence_label, categorie_densification
    """).fetchall()
    for lab, cat, n in cross:
        print(f"    {lab:15s} x {cat:10s} : {n:>6,}")

    # Exemple parcelles haute confiance
    print("\n  Top 5 parcelles haute confiance:")
    top = conn.execute("""
        SELECT id_parcelle, code_commune, confidence_global,
               score_bdnb, score_dvf, score_densification, score_fraicheur,
               nb_transactions, confidence_label
        FROM confidence_scores
        ORDER BY confidence_global DESC
        LIMIT 5
    """).fetchall()
    for pid, com, g, b, d, z, f, nt, lab in top:
        print(f"    {pid} ({com}): {g:.2f} [{lab}]  "
              f"bdnb={b} dvf={d} zan={z} fraich={f} tx={nt}")

    conn.close()

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.1f}s — {total:,} parcelles")


if __name__ == "__main__":
    main()
