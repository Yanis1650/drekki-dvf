"""Audit de Qualité des Données — Foncier Express.

Évalue la qualité des croisements DVF ↔ Cadastre ↔ BDNB ↔ Densification
sur le département 35 (Ille-et-Vilaine).

Résultats nécessaires avant toute extension nationale.
"""

import duckdb
from pathlib import Path

DB_PATH = Path("data/foncier.duckdb")
TEST_DEPT = "35"


def main():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    conn.execute("INSTALL spatial; LOAD spatial;")

    print("=" * 70)
    print("  AUDIT QUALITÉ — Foncier Express (Dept 35)")
    print("=" * 70)

    # ─── Inventaire des tables ───────────────────────────────────────────
    print("\n📋 INVENTAIRE DES TABLES")
    print("-" * 50)
    tables = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()
    for (t,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:40s} → {count:>12,} lignes")

    # ─── Schéma de france_foncier_test ───────────────────────────────────
    print("\n📐 SCHÉMA: france_foncier_test")
    print("-" * 50)
    cols = conn.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'france_foncier_test'
        ORDER BY ordinal_position
    """).fetchall()
    for name, dtype in cols:
        print(f"  {name:35s} {dtype}")

    # ─── Schéma de densification_scores ──────────────────────────────────
    print("\n📐 SCHÉMA: densification_scores")
    print("-" * 50)
    try:
        cols_d = conn.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'densification_scores'
            ORDER BY ordinal_position
        """).fetchall()
        for name, dtype in cols_d:
            print(f"  {name:35s} {dtype}")
    except Exception as e:
        print(f"  ⚠️ Table non trouvée: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 1 : Taux de join DVF ↔ Cadastre ↔ BDNB
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  AUDIT 1 — Taux de join DVF ↔ Cadastre ↔ BDNB")
    print("=" * 70)

    r1 = conn.execute(f"""
        SELECT
            COUNT(*)                                                AS total_mutations,
            
            -- Join Cadastre (mutation → parcelle)
            COUNT(cadastre_parcelle_id)                             AS avec_parcelle_cadastre,
            ROUND(COUNT(cadastre_parcelle_id) * 100.0 / COUNT(*), 1) AS taux_join_cadastre_pct,
            
            -- Join BDNB (via dpe_energie ou hauteur_moyenne non null)
            COUNT(CASE WHEN dpe_energie IS NOT NULL 
                         OR annee_construction IS NOT NULL 
                         OR hauteur_moyenne IS NOT NULL THEN 1 END) AS avec_bdnb,
            ROUND(
                COUNT(CASE WHEN dpe_energie IS NOT NULL 
                             OR annee_construction IS NOT NULL 
                             OR hauteur_moyenne IS NOT NULL THEN 1 END) 
                * 100.0 / COUNT(*), 1
            )                                                       AS taux_join_bdnb_pct,
            
            -- DPE spécifiquement
            COUNT(dpe_energie)                                      AS avec_dpe,
            ROUND(COUNT(dpe_energie) * 100.0 / COUNT(*), 1)        AS taux_dpe_pct,
            
            -- Hauteur BDNB
            COUNT(hauteur_moyenne)                                  AS avec_hauteur,
            ROUND(COUNT(hauteur_moyenne) * 100.0 / COUNT(*), 1)    AS taux_hauteur_pct,
            
            -- Année construction
            COUNT(annee_construction)                               AS avec_annee,
            ROUND(COUNT(annee_construction) * 100.0 / COUNT(*), 1) AS taux_annee_pct

        FROM france_foncier_test
    """).fetchone()

    labels_1 = [
        "total_mutations", "avec_parcelle_cadastre", "taux_join_cadastre_pct",
        "avec_bdnb", "taux_join_bdnb_pct",
        "avec_dpe", "taux_dpe_pct",
        "avec_hauteur", "taux_hauteur_pct",
        "avec_annee", "taux_annee_pct",
    ]
    for label, val in zip(labels_1, r1):
        unit = " %" if "pct" in label else ""
        formatted = f"{val:,.1f}" if isinstance(val, float) else f"{val:,}"
        print(f"  {label:35s} → {formatted}{unit}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 2 : Couverture Densification (ZAN)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  AUDIT 2 — Couverture Densification / ZAN")
    print("=" * 70)

    try:
        r2 = conn.execute(f"""
            SELECT
                COUNT(DISTINCT f.cadastre_parcelle_id)                  AS parcelles_dans_fft,
                COUNT(DISTINCT d.id_parcelle)                           AS parcelles_avec_densif,
                
                -- Taux de couverture : combien de parcelles FFT ont un score
                COUNT(DISTINCT CASE WHEN d.id_parcelle IS NOT NULL 
                                    THEN f.cadastre_parcelle_id END)    AS parcelles_matchees,
                ROUND(
                    COUNT(DISTINCT CASE WHEN d.id_parcelle IS NOT NULL 
                                        THEN f.cadastre_parcelle_id END) 
                    * 100.0 
                    / NULLIF(COUNT(DISTINCT f.cadastre_parcelle_id), 0), 1
                )                                                       AS couverture_pct,
                
                -- Stats sur les scores
                ROUND(AVG(d.potentiel_densification), 4)                AS potentiel_moyen,
                ROUND(MEDIAN(d.potentiel_densification), 4)             AS potentiel_median,
                
                -- Distribution par catégorie
                COUNT(CASE WHEN d.categorie = 'FORT' THEN 1 END)       AS cat_fort,
                COUNT(CASE WHEN d.categorie = 'MOYEN' THEN 1 END)      AS cat_moyen,
                COUNT(CASE WHEN d.categorie = 'FAIBLE' THEN 1 END)     AS cat_faible,
                COUNT(CASE WHEN d.categorie = 'SATURE' THEN 1 END)     AS cat_sature

            FROM france_foncier_test f
            LEFT JOIN densification_scores d 
                ON f.cadastre_parcelle_id = d.id_parcelle
            WHERE f.cadastre_parcelle_id IS NOT NULL
        """).fetchone()

        labels_2 = [
            "parcelles_dans_fft", "parcelles_avec_densif",
            "parcelles_matchees", "couverture_pct",
            "potentiel_moyen", "potentiel_median",
            "cat_fort", "cat_moyen", "cat_faible", "cat_sature",
        ]
        for label, val in zip(labels_2, r2):
            unit = " %" if "pct" in label else ""
            if val is None:
                formatted = "NULL"
            elif isinstance(val, float):
                formatted = f"{val:,.4f}" if "potentiel" in label else f"{val:,.1f}"
            else:
                formatted = f"{val:,}"
            print(f"  {label:35s} → {formatted}{unit}")

    except Exception as e:
        print(f"  ⚠️ Impossible de requêter densification_scores: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 2b : Stats densification_scores seule
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "-" * 50)
    print("  AUDIT 2b — Densification_scores (table isolée)")
    print("-" * 50)

    try:
        r2b = conn.execute("""
            SELECT
                COUNT(*)                                                    AS total_parcelles,
                ROUND(AVG(ces_actuel), 4)                                   AS ces_actuel_moyen,
                ROUND(MEDIAN(ces_actuel), 4)                                AS ces_actuel_median,
                ROUND(AVG(surface_constructible_restante), 0)               AS surface_constr_moy,
                COUNT(CASE WHEN categorie = 'FORT' THEN 1 END)             AS fort,
                COUNT(CASE WHEN categorie = 'MOYEN' THEN 1 END)            AS moyen,
                COUNT(CASE WHEN categorie = 'FAIBLE' THEN 1 END)           AS faible,
                COUNT(CASE WHEN categorie = 'SATURE' THEN 1 END)           AS sature,
                COUNT(CASE WHEN surface_plancher_m2 > 0 THEN 1 END)        AS avec_plancher_bdnb,
                ROUND(COUNT(CASE WHEN surface_plancher_m2 > 0 THEN 1 END) 
                      * 100.0 / COUNT(*), 1)                               AS pct_avec_plancher
            FROM densification_scores
        """).fetchone()

        labels_2b = [
            "total_parcelles", "ces_actuel_moyen", "ces_actuel_median",
            "surface_constr_moy", "fort", "moyen", "faible", "sature",
            "avec_plancher_bdnb", "pct_avec_plancher",
        ]
        for label, val in zip(labels_2b, r2b):
            unit = " %" if "pct" in label else ""
            if val is None:
                formatted = "NULL"
            elif isinstance(val, float):
                formatted = f"{val:,.4f}" if "ces" in label else f"{val:,.1f}"
            else:
                formatted = f"{val:,}"
            print(f"  {label:35s} → {formatted}{unit}")

    except Exception as e:
        print(f"  ⚠️ Table densification_scores non disponible: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 3 : Cas problématiques (données manquantes / aberrantes)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  AUDIT 3 — Données manquantes et aberrantes")
    print("=" * 70)

    r3 = conn.execute(f"""
        SELECT
            COUNT(*)                                                        AS total,
            
            -- Parcelle cadastre manquante
            ROUND(COUNT(CASE WHEN cadastre_parcelle_id IS NULL THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_sans_parcelle,
            
            -- Surface habitable manquante
            ROUND(COUNT(CASE WHEN surface_habitable_totale IS NULL 
                              OR surface_habitable_totale = 0 THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_sans_surface_hab,
            
            -- Valeur foncière manquante
            ROUND(COUNT(CASE WHEN valeur_fonciere IS NULL THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_sans_valeur,
            
            -- Prix m2 aberrant (> 50 000 €/m²)
            ROUND(COUNT(CASE WHEN prix_m2 > 50000 THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_prix_m2_aberrant,
            
            -- Prix m2 très bas (< 100 €/m²) → possible terrain nu
            ROUND(COUNT(CASE WHEN prix_m2 < 100 AND prix_m2 > 0 THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_prix_m2_tres_bas,
            
            -- Transactions sans coordonnées (ne devraient pas exister, filtrées à l'ETL)
            ROUND(COUNT(CASE WHEN longitude IS NULL OR latitude IS NULL THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_sans_coord,
            
            -- Date mutation manquante
            ROUND(COUNT(CASE WHEN date_mutation IS NULL THEN 1 END) 
                  * 100.0 / COUNT(*), 1)                                    AS pct_sans_date

        FROM france_foncier_test
    """).fetchone()

    labels_3 = [
        "total", "pct_sans_parcelle", "pct_sans_surface_hab",
        "pct_sans_valeur", "pct_prix_m2_aberrant", "pct_prix_m2_tres_bas",
        "pct_sans_coord", "pct_sans_date",
    ]
    for label, val in zip(labels_3, r3):
        unit = " %" if "pct" in label else ""
        formatted = f"{val:,.1f}" if isinstance(val, float) else f"{val:,}"
        print(f"  {label:35s} → {formatted}{unit}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 4 : Fraîcheur des données (distribution temporelle)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  AUDIT 4 — Distribution temporelle des mutations")
    print("=" * 70)

    r4 = conn.execute("""
        SELECT 
            YEAR(TRY_CAST(date_mutation AS DATE)) as annee,
            COUNT(*) as nb_mutations,
            ROUND(AVG(valeur_fonciere), 0) as valeur_moy,
            ROUND(AVG(prix_m2), 0) as prix_m2_moy
        FROM france_foncier_test
        WHERE date_mutation IS NOT NULL
        GROUP BY YEAR(TRY_CAST(date_mutation AS DATE))
        ORDER BY annee
    """).fetchall()

    print(f"  {'Année':>6s}  {'Mutations':>10s}  {'Valeur moy':>12s}  {'Prix/m² moy':>12s}")
    print(f"  {'─'*6}  {'─'*10}  {'─'*12}  {'─'*12}")
    for annee, nb, val_moy, pm2 in r4:
        val_str = f"{val_moy:,.0f} €" if val_moy else "N/A"
        pm2_str = f"{pm2:,.0f} €" if pm2 else "N/A"
        print(f"  {annee:>6}  {nb:>10,}  {val_str:>12s}  {pm2_str:>12s}")

    # ═══════════════════════════════════════════════════════════════════════
    # AUDIT 5 : Qualité du match spatial (doublons)
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  AUDIT 5 — Qualité du match spatial (doublons)")
    print("=" * 70)

    r5 = conn.execute("""
        WITH mutation_counts AS (
            SELECT 
                id_mutation,
                COUNT(*) as nb_parcelles_matchees
            FROM france_foncier_test
            GROUP BY id_mutation
        )
        SELECT
            COUNT(*)                                                        AS total_mutations_uniques,
            COUNT(CASE WHEN nb_parcelles_matchees = 1 THEN 1 END)          AS match_1_pour_1,
            COUNT(CASE WHEN nb_parcelles_matchees > 1 THEN 1 END)          AS match_multiple,
            MAX(nb_parcelles_matchees)                                      AS max_parcelles_par_mutation,
            ROUND(AVG(nb_parcelles_matchees), 2)                            AS moy_parcelles_par_mutation,
            ROUND(
                COUNT(CASE WHEN nb_parcelles_matchees = 1 THEN 1 END) 
                * 100.0 / COUNT(*), 1
            )                                                               AS pct_match_exact
        FROM mutation_counts
    """).fetchone()

    labels_5 = [
        "total_mutations_uniques", "match_1_pour_1", "match_multiple",
        "max_parcelles_par_mutation", "moy_parcelles_par_mutation", "pct_match_exact",
    ]
    for label, val in zip(labels_5, r5):
        unit = " %" if "pct" in label else ""
        formatted = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
        print(f"  {label:35s} → {formatted}{unit}")

    # ═══════════════════════════════════════════════════════════════════════
    # RÉSUMÉ
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  RÉSUMÉ — Indicateurs clés")
    print("=" * 70)
    print(f"""
  🏠 Join DVF → Cadastre :  {r1[2]}%
  🏢 Join DVF → BDNB :      {r1[4]}%
  🌡️  Couverture DPE :       {r1[6]}%
  📏 Couverture hauteur :   {r1[8]}%
  ⚠️  Sans parcelle :        {r3[1]}%
  ⚠️  Prix/m² aberrant :     {r3[4]}%
  🎯 Match spatial exact :  {r5[5]}%
""")

    conn.close()
    print("✅ Audit terminé.")


if __name__ == "__main__":
    main()
