"""Marquage statistique des prix/m2 aberrants, apres le golden join.

Concern distinct de la jointure elle-meme : la jointure assemble les
sources, ceci qualifie ce qu'elle a produit. Couvert par
`tests/test_outliers.py`.
"""

import duckdb


def _tag_outliers(conn: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """Tags outliers prix/m² dans france_foncier_test.

    Algorithme :
      1. P5/P95 par (code_commune, année) — utilisé si n ≥ 10.
      2. Fallback (dept=LEFT(code_commune,2), année) si n < 10.
      is_outlier = TRUE si prix_m2 < P5 ou prix_m2 > P95.
      Les outliers sont conservés (non supprimés).

    Returns: (total, n_outliers)
    """
    conn.execute(
        "ALTER TABLE france_foncier_test ADD COLUMN is_outlier BOOLEAN DEFAULT FALSE"
    )
    conn.execute("DROP TABLE IF EXISTS _outlier_bounds")
    conn.execute("""
        CREATE TABLE _outlier_bounds AS
        WITH cy AS (
            SELECT
                code_commune,
                YEAR(TRY_CAST(date_mutation AS DATE))                     AS yr,
                COUNT(*)                                                   AS n,
                PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY prix_m2) AS p5,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prix_m2) AS p95
            FROM france_foncier_test
            WHERE prix_m2 IS NOT NULL AND prix_m2 > 0
            GROUP BY code_commune, YEAR(TRY_CAST(date_mutation AS DATE))
        ),
        dy AS (
            SELECT
                LEFT(code_commune, 2)                                     AS dept,
                YEAR(TRY_CAST(date_mutation AS DATE))                     AS yr,
                PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY prix_m2) AS p5,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prix_m2) AS p95
            FROM france_foncier_test
            WHERE prix_m2 IS NOT NULL AND prix_m2 > 0
            GROUP BY LEFT(code_commune, 2), YEAR(TRY_CAST(date_mutation AS DATE))
        )
        SELECT
            f.id_mutation,
            CASE
                WHEN f.prix_m2 IS NULL OR f.prix_m2 <= 0 THEN FALSE
                WHEN cy.n >= 10
                    THEN f.prix_m2 < cy.p5 OR f.prix_m2 > cy.p95
                WHEN dy.p5 IS NOT NULL
                    THEN f.prix_m2 < dy.p5 OR f.prix_m2 > dy.p95
                ELSE FALSE
            END AS is_out
        FROM france_foncier_test f
        JOIN cy  ON f.code_commune = cy.code_commune
                AND YEAR(TRY_CAST(f.date_mutation AS DATE)) = cy.yr
        LEFT JOIN dy ON LEFT(f.code_commune, 2) = dy.dept
                     AND YEAR(TRY_CAST(f.date_mutation AS DATE)) = dy.yr
    """)
    conn.execute("""
        UPDATE france_foncier_test
        SET is_outlier = b.is_out
        FROM _outlier_bounds b
        WHERE france_foncier_test.id_mutation = b.id_mutation
    """)
    conn.execute("DROP TABLE _outlier_bounds")
    n_out = conn.execute(
        "SELECT COUNT(*) FROM france_foncier_test WHERE is_outlier"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM france_foncier_test").fetchone()[0]
    return total, n_out
