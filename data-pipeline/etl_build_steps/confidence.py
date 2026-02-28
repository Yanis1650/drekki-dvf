"""Step 6: Confidence Score."""

from .config import W_BDNB, W_DENSIF, W_DVF, W_FRAICHEUR
from .utils import step_banner


def step_confidence(conn, dept):
    step_banner(6, "Confidence Score")

    conn.execute("DROP TABLE IF EXISTS confidence_scores")
    conn.execute(f"""
        CREATE TABLE confidence_scores AS
        WITH raw_scores AS (
            SELECT
                d.id_parcelle,
                ROUND(CASE
                    WHEN f.dpe_energie IS NOT NULL AND f.annee_construction IS NOT NULL
                         AND f.hauteur_moyenne IS NOT NULL THEN 1.0
                    WHEN f.dpe_energie IS NOT NULL OR f.annee_construction IS NOT NULL THEN 0.6
                    WHEN f.cadastre_parcelle_id IS NOT NULL THEN 0.3
                    ELSE 0.0
                END, 2) AS score_bdnb,

                ROUND(CASE
                    WHEN tx_count >= 5  THEN 1.0
                    WHEN tx_count >= 3  THEN 0.8
                    WHEN tx_count >= 1  THEN 0.5
                    ELSE 0.0
                END, 2) AS score_dvf,

                ROUND(CASE
                    WHEN d.source_ces = 'bdnb_emprise'    THEN 1.0
                    WHEN d.source_ces = 'bdtopo'          THEN 0.85
                    WHEN d.source_ces = 'plu_gpu'         THEN 0.70
                    WHEN d.source_ces = 'rnu_proximite'   THEN 0.45
                    WHEN d.source_ces = 'bdnb_usage_only' THEN 0.4
                    WHEN d.categorie  = 'INCONNU'         THEN 0.1
                    ELSE 0.1
                END, 2) AS score_densification,

                ROUND(CASE
                    WHEN last_sale >= 2023 THEN 1.0
                    WHEN last_sale >= 2020 THEN 0.8
                    WHEN last_sale >= 2017 THEN 0.5
                    WHEN last_sale >= 2014 THEN 0.3
                    ELSE 0.0
                END, 2) AS score_fraicheur

            FROM densification_scores d
            LEFT JOIN (
                SELECT cadastre_parcelle_id,
                       COUNT(*) AS tx_count,
                       MAX(YEAR(date_mutation)) AS last_sale,
                       MAX(dpe_energie) AS dpe_energie,
                       MAX(annee_construction) AS annee_construction,
                       MAX(hauteur_moyenne) AS hauteur_moyenne
                FROM france_foncier_test
                GROUP BY cadastre_parcelle_id
            ) f ON d.id_parcelle = f.cadastre_parcelle_id
            WHERE d.code_commune LIKE '{dept}%'
        )
        SELECT
            id_parcelle,
            score_bdnb, score_dvf, score_densification, score_fraicheur,
            ROUND(
                score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR},
            2) AS confidence_global,
            CASE
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.75
                    THEN 'Elevee'
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.55
                    THEN 'Moyenne'
                WHEN (score_bdnb * {W_BDNB} + score_dvf * {W_DVF}
                      + score_densification * {W_DENSIF} + score_fraicheur * {W_FRAICHEUR}) >= 0.35
                    THEN 'Faible'
                ELSE 'Insuffisante'
            END AS confidence_label
        FROM raw_scores
    """)

    conn.execute("CREATE INDEX idx_conf_id ON confidence_scores(id_parcelle)")

    total = conn.execute("SELECT COUNT(*) FROM confidence_scores").fetchone()[0]
    dist = conn.execute("""
        SELECT confidence_label, COUNT(*) as n,
               ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(), 1) as pct
        FROM confidence_scores GROUP BY 1
        ORDER BY CASE confidence_label
            WHEN 'Elevee' THEN 1 WHEN 'Moyenne' THEN 2
            WHEN 'Faible' THEN 3 ELSE 4
        END
    """).fetchall()

    print(f"  confidence_scores: {total:,}")
    for label, n, pct in dist:
        print(f"    {label:15s} {n:>10,} ({pct:5.1f}%)")
