"""Step 2: Densification (CES actuel + potentiel)."""

from .utils import print_distribution, step_banner


def step_densification(conn, dept):
    step_banner(2, "Densification (CES actuel + potentiel)")

    has_bdnb = "bdnb_stats" in [r[0] for r in conn.execute("SHOW TABLES").fetchall()]

    conn.execute("DROP TABLE IF EXISTS densification_scores")
    conn.execute(f"""
        CREATE TABLE densification_scores AS
        WITH parcelles_leaf AS (
            SELECT p.id_parcelle, p.code_commune,
                   ST_Area(p.geometry) AS surface_parcelle_m2
            FROM parcelles p
            WHERE p.section IS NOT NULL AND p.numero IS NOT NULL
              AND p.geometry IS NOT NULL AND p.code_commune LIKE '{dept}%'
        ),
        enriched AS (
            SELECT
                p.id_parcelle, p.code_commune, p.surface_parcelle_m2,
                {'b.emprise_sol_m2' if has_bdnb else 'NULL AS emprise_sol_m2'},
                {'b.hauteur_moyenne' if has_bdnb else 'NULL AS hauteur_moyenne'},
                {'b.nb_niveau' if has_bdnb else 'NULL AS nb_niveau'},
                {'b.type_usage' if has_bdnb else "NULL AS type_usage"},
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.emprise_sol_m2' if has_bdnb else '0'} > 0
                     AND p.surface_parcelle_m2 > 0
                    THEN LEAST({'b.emprise_sol_m2' if has_bdnb else '0'} / p.surface_parcelle_m2, 1.0)
                    ELSE NULL
                END AS ces_actuel,
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.nb_niveau' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'} * {'b.nb_niveau' if has_bdnb else '1'}
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.hauteur_moyenne' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'}
                             * GREATEST(1, ROUND(
                                 {'b.hauteur_moyenne' if has_bdnb else '3'} / 3.0
                               ))
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN {'b.emprise_sol_m2' if has_bdnb else '0'}
                    ELSE NULL
                END AS surface_plancher_m2,
                CASE
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Residentiel collectif'  THEN 0.60
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Residentiel individuel' THEN 0.40
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Tertiaire & Autres'     THEN 0.60
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Dependance'             THEN 0.25
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} = 'Secondaire'             THEN 0.35
                    ELSE 0.40
                END AS ces_potentiel,
                CASE
                    WHEN {'b.emprise_sol_m2' if has_bdnb else 'NULL'} IS NOT NULL
                     AND {'b.emprise_sol_m2' if has_bdnb else '0'} > 0
                        THEN 'bdnb_emprise'
                    WHEN {'b.type_usage' if has_bdnb else 'NULL'} IS NOT NULL
                        THEN 'bdnb_usage_only'
                    ELSE 'inconnu'
                END AS source_ces
            FROM parcelles_leaf p
            {'LEFT JOIN bdnb_stats b ON p.id_parcelle = b.parcelle_id' if has_bdnb else ''}
            WHERE p.surface_parcelle_m2 > 1
        ),
        scored AS (
            SELECT *,
                CASE
                    WHEN ces_actuel IS NOT NULL
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel)
                    WHEN source_ces = 'bdnb_usage_only'
                        THEN ces_potentiel * 0.5
                    ELSE NULL
                END AS potentiel_densification,
                CASE
                    WHEN ces_actuel IS NOT NULL AND surface_parcelle_m2 > 0
                        THEN GREATEST(0.0, ces_potentiel - ces_actuel) * surface_parcelle_m2
                    ELSE NULL
                END AS surface_constructible_restante
            FROM enriched
        )
        SELECT
            id_parcelle, code_commune, surface_parcelle_m2,
            COALESCE(surface_plancher_m2, 0) AS surface_plancher_m2,
            emprise_sol_m2, ces_actuel, ces_potentiel,
            potentiel_densification, surface_constructible_restante,
            source_ces, type_usage, nb_niveau,
            CASE
                WHEN potentiel_densification IS NULL  THEN 'INCONNU'
                WHEN potentiel_densification >= 0.25  THEN 'FORT'
                WHEN potentiel_densification >= 0.10  THEN 'MOYEN'
                WHEN potentiel_densification > 0.02   THEN 'FAIBLE'
                ELSE 'SATURE'
            END AS categorie
        FROM scored
    """)

    conn.execute("CREATE INDEX idx_densif_id ON densification_scores(id_parcelle)")
    conn.execute("CREATE INDEX idx_densif_commune ON densification_scores(code_commune)")
    conn.execute("CREATE INDEX idx_densif_cat ON densification_scores(categorie)")

    total = conn.execute("SELECT COUNT(*) FROM densification_scores").fetchone()[0]
    print(f"  densification_scores: {total:,} parcelles")
    print_distribution(conn, "Apres densification")
