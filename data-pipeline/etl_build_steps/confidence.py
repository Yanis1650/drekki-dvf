"""Step 6: Confidence Score."""

from .utils import step_banner


def step_confidence(conn, dept):
    step_banner(6, "Confidence Score")

    conn.execute("DROP TABLE IF EXISTS confidence_scores")
    conn.execute(f"""
        CREATE TABLE confidence_scores AS
        WITH bdnb_raw AS (
            SELECT
                d.id_parcelle,
                d.source_ces,
                COALESCE(d.zone_non_mutable, FALSE) AS zone_non_mutable,
                -- BDNB : richesse données bâtiment (DPE, millésime, hauteur)
                ROUND(CASE
                    WHEN f.dpe_energie IS NOT NULL
                         AND f.annee_construction IS NOT NULL
                         AND f.hauteur_moyenne IS NOT NULL THEN 1.0
                    WHEN f.dpe_energie IS NOT NULL
                         OR  f.annee_construction IS NOT NULL THEN 0.6
                    WHEN f.cadastre_parcelle_id IS NOT NULL   THEN 0.3
                    ELSE 0.0
                END, 2) AS score_bdnb,
                COALESCE(f.tx_count, 0) AS tx_count,
                f.last_sale
            FROM densification_scores d
            LEFT JOIN (
                SELECT cadastre_parcelle_id,
                       COUNT(*) AS tx_count,
                       MAX(YEAR(TRY_CAST(date_mutation AS DATE))) AS last_sale,
                       MAX(dpe_energie)        AS dpe_energie,
                       MAX(annee_construction) AS annee_construction,
                       MAX(hauteur_moyenne)    AS hauteur_moyenne
                FROM france_foncier_test
                GROUP BY cadastre_parcelle_id
            ) f ON d.id_parcelle = f.cadastre_parcelle_id
            WHERE d.code_commune LIKE '{dept}%'
        ),
        raw_scores AS (
            SELECT
                id_parcelle, zone_non_mutable, score_bdnb,
                -- DVF fiabilité : binaire — "peut-on calculer un prix/m² ?"
                ROUND(CASE WHEN tx_count >= 1 THEN 1.0 ELSE 0.0 END, 2) AS score_dvf_fiabilite,
                -- DVF précision : granulaire — pour zones transactées U/AU
                ROUND(CASE
                    WHEN tx_count >= 5 THEN 1.0
                    WHEN tx_count >= 3 THEN 0.80
                    WHEN tx_count >= 1 THEN 0.50
                    ELSE 0.0
                END, 2) AS score_dvf_precision,
                -- Qualité de la source de densification : découpée de BDNB,
                -- avec une pénalité unique pour rnu_proximite.
                -- rnu_proximite + score_bdnb = 0 → 0.10  (absence totale de données bâtiment)
                -- rnu_proximite + score_bdnb > 0 → 0.30  (BDNB présent, emprise seule inconnue)
                ROUND(CASE
                    WHEN source_ces = 'bdnb_emprise'                       THEN 1.00
                    WHEN source_ces = 'bdtopo'                             THEN 0.85
                    WHEN source_ces = 'plu_gpu'                            THEN 0.70
                    WHEN source_ces = 'rnu_proximite' AND score_bdnb > 0.0 THEN 0.30
                    WHEN source_ces = 'rnu_proximite'                      THEN 0.10
                    WHEN source_ces = 'bdnb_usage_only'                    THEN 0.40
                    ELSE 0.10
                END, 2) AS score_densification,
                -- Fraîcheur : récence dernière vente (non pertinent pour zones A/N)
                ROUND(CASE
                    WHEN last_sale >= 2023 THEN 1.0
                    WHEN last_sale >= 2020 THEN 0.8
                    WHEN last_sale >= 2017 THEN 0.5
                    WHEN last_sale >= 2014 THEN 0.3
                    ELSE 0.0
                END, 2) AS score_fraicheur
            FROM bdnb_raw
        ),
        weighted AS (
            SELECT *,
                ROUND(CASE WHEN zone_non_mutable
                    -- Zones A/N : fraîcheur ignorée → BDNB 40%, DVF fiabilité 25%, densification 35%
                    THEN score_bdnb * 0.40 + score_dvf_fiabilite * 0.25 + score_densification * 0.35
                    -- Zones U/AU : formule standard → BDNB 30%, DVF précision 25%, densification 25%, Fraîcheur 20%
                    ELSE score_bdnb * 0.30 + score_dvf_precision * 0.25
                         + score_densification * 0.25 + score_fraicheur * 0.20
                END, 2) AS confidence_global
            FROM raw_scores
        )
        SELECT
            id_parcelle,
            score_bdnb,
            score_dvf_fiabilite,
            score_dvf_precision,
            score_densification,
            score_fraicheur,
            CASE WHEN zone_non_mutable
                THEN score_dvf_fiabilite
                ELSE score_dvf_precision
            END AS score_dvf,
            confidence_global,
            CASE
                WHEN confidence_global >= 0.75 THEN 'Elevee'
                WHEN confidence_global >= 0.55 THEN 'Moyenne'
                WHEN confidence_global >= 0.35 THEN 'Faible'
                ELSE 'Insuffisante'
            END AS confidence_label
        FROM weighted
    """)

    conn.execute("CREATE INDEX idx_conf_id ON confidence_scores(id_parcelle)")

    total = conn.execute("SELECT COUNT(*) FROM confidence_scores").fetchone()[0]
    dist = conn.execute("""
        SELECT confidence_label, COUNT(*) AS n,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
        FROM confidence_scores GROUP BY 1
        ORDER BY CASE confidence_label
            WHEN 'Elevee' THEN 1 WHEN 'Moyenne' THEN 2
            WHEN 'Faible' THEN 3 ELSE 4
        END
    """).fetchall()

    print(f"  confidence_scores: {total:,}")
    for label, n, pct in dist:
        print(f"    {label:15s} {n:>10,} ({pct:5.1f}%)")
