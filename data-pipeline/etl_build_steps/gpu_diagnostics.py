"""Journal de controle de l'etape GPU : ce que l'appariement a produit."""

import datetime
import logging

import duckdb

logger = logging.getLogger(__name__)


def _log_diagnostics(conn: duckdb.DuckDBPyConnection, dept: str) -> None:
    """Construit plu_coverage_issues et logge tous les problèmes PLU détectés.

    Motifs possibles :
      'no_plu_gpu'            : commune absente de plu_commune_partition
      'partition_without_zones': partition mappée mais aucune zone spatiale trouvée
      'plu_recently_revised'  : PLU approuvé < 180j → re-run ETL recommandé
    """
    cutoff = datetime.date.today() - datetime.timedelta(days=180)
    conn.execute("DROP TABLE IF EXISTS plu_coverage_issues")
    conn.execute(f"""
        CREATE TABLE plu_coverage_issues AS
        SELECT
            d.code_commune,
            COUNT(*) AS parcelles_inconnu,
            CASE WHEN cp.code_commune IS NULL THEN 'no_plu_gpu'
                 ELSE 'partition_without_zones'
            END AS motif
        FROM densification_scores d
        LEFT JOIN plu_commune_partition cp ON d.code_commune = cp.code_commune
        WHERE d.categorie = 'INCONNU' AND d.code_commune LIKE '{dept}%'
        GROUP BY d.code_commune, cp.code_commune
        UNION ALL
        SELECT DISTINCT code_commune, 0, 'plu_recently_revised'
        FROM densification_scores
        WHERE plu_datappro IS NOT NULL AND plu_datappro > DATE '{cutoff}'
          AND code_commune LIKE '{dept}%'
    """)
    issues = conn.execute(
        "SELECT code_commune, parcelles_inconnu, motif FROM plu_coverage_issues ORDER BY motif, parcelles_inconnu DESC"
    ).fetchall()
    for code, n, motif in issues[:20]:
        if motif == 'plu_recently_revised':
            msg = f"commune {code}: PLU recemment revise (datappro <180j) — re-run ETL recommande"
        elif motif == 'partition_without_zones':
            msg = f"commune {code}: partition mappee mais aucune zone PLU trouvee ({n} parcelles INCONNU)"
        else:
            msg = f"commune {code}: aucun PLU GPU, fallback RNU ({n} parcelles)"
        logger.warning(msg)
        print(f"    WARN: {msg}")
    if len(issues) > 20:
        print(f"  ... et {len(issues) - 20} autres entrees (voir plu_coverage_issues)")
