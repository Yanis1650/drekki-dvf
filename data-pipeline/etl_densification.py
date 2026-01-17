"""ETL Densification - Calcul du Potentiel de Densification (ZAN).

Calcule le Coefficient d'Emprise au Sol (CES) actuel et identifie
les "dents creuses" en croisant:
- Surface de Plancher (BDNB, estimée via hauteur/3 × emprise)
- Surface de la Parcelle (Cadastre)
- CES Potentiel (PLU ou défaut 40%)

Output: Table densification_scores dans DuckDB.
"""

import time
from pathlib import Path

import duckdb
import polars as pl

# Configuration
DB_PATH = Path(__file__).parent.parent / "data" / "foncier.duckdb"
BDNB_PARQUET = Path(__file__).parent.parent / "data" / "bdnb_stats.parquet"

# CES potentiel par défaut (40% pour zones urbaines)
DEFAULT_CES_POTENTIEL = 0.40


def main():
    print("=" * 60)
    print("ETL Densification - Potentiel ZAN")
    print("=" * 60)

    start_time = time.time()

    # Connect to DuckDB
    conn = duckdb.connect(str(DB_PATH))
    conn.execute("INSTALL spatial; LOAD spatial;")

    print("\n--- Phase 1: Vérification des données sources ---")

    # Check parcelles table
    parcelles_count = conn.execute("SELECT COUNT(*) FROM parcelles").fetchone()[0]
    print(f"✓ Parcelles cadastrales: {parcelles_count:,} lignes")

    # Check BDNB parquet
    if not BDNB_PARQUET.exists():
        print(f"❌ ERREUR: {BDNB_PARQUET} introuvable")
        print("   Exécute d'abord: python data-pipeline/etl_france_bdnb.py")
        return

    bdnb_size = BDNB_PARQUET.stat().st_size / 1e6
    print(f"✓ BDNB stats: {bdnb_size:.1f} MB")

    print("\n--- Phase 2: Chargement BDNB avec Polars Lazy ---")

    # Load BDNB with Polars lazy evaluation
    bdnb_lazy = pl.scan_parquet(str(BDNB_PARQUET))

    # Estimate surface_plancher from hauteur_moyenne
    # Assumption: hauteur_moyenne / 3m = nombre d'étages
    # surface_plancher ≈ nombre_étages × emprise_au_sol
    # Pour simplifier: surface_plancher ≈ hauteur_moyenne × 10 (emprise moyenne)
    bdnb_processed = bdnb_lazy.select([
        pl.col("parcelle_id").alias("id_parcelle"),
        pl.col("hauteur_moyenne"),
        # Estimation conservative: hauteur × 10 m² d'emprise par mètre de hauteur
        (pl.col("hauteur_moyenne") * 10.0).alias("surface_plancher_estimee"),
    ]).filter(
        pl.col("hauteur_moyenne").is_not_null()
    ).collect()

    print(f"✓ BDNB traité: {len(bdnb_processed):,} parcelles avec hauteur")

    # Register as DuckDB table
    conn.register("bdnb_temp", bdnb_processed)

    print("\n--- Phase 3: Calcul CES et Potentiel ---")

    # Drop existing table
    conn.execute("DROP TABLE IF EXISTS densification_scores;")

    # Create densification_scores table
    # Join parcelles + BDNB + calculate CES
    query = """
        CREATE TABLE densification_scores AS
        WITH parcelles_with_surface AS (
            SELECT 
                p.id_parcelle,
                p.code_commune,
                ST_Area(p.geometry) as surface_parcelle_m2
            FROM parcelles p
            WHERE p.code_commune LIKE '35%'  -- Dept 35 only
              AND p.geometry IS NOT NULL
        ),
        parcelles_bdnb AS (
            SELECT 
                p.id_parcelle,
                p.code_commune,
                p.surface_parcelle_m2,
                COALESCE(b.surface_plancher_estimee, 0.0) as surface_plancher_m2
            FROM parcelles_with_surface p
            LEFT JOIN bdnb_temp b ON p.id_parcelle = b.id_parcelle
        ),
        with_ces AS (
            SELECT 
                id_parcelle,
                code_commune,
                surface_parcelle_m2,
                surface_plancher_m2,
                -- CES actuel = surface_plancher / surface_parcelle
                -- Cap at 9.9999 to prevent DECIMAL(5,4) overflow for multi-story buildings
                CASE 
                    WHEN surface_parcelle_m2 > 0 THEN 
                        CASE 
                            WHEN (surface_plancher_m2 / surface_parcelle_m2) > 9.9999 THEN 9.9999
                            ELSE (surface_plancher_m2 / surface_parcelle_m2)
                        END
                    ELSE 0.0
                END as ces_actuel,
                -- CES potentiel (défaut 40%)
                0.40 as ces_potentiel
            FROM parcelles_bdnb
            WHERE surface_parcelle_m2 > 0
        )
        SELECT 
            id_parcelle,
            code_commune,
            surface_parcelle_m2,
            surface_plancher_m2,
            ces_actuel,
            ces_potentiel,
            -- Potentiel de densification
            GREATEST(0.0, ces_potentiel - ces_actuel) as potentiel_densification,
            -- Surface constructible restante
            GREATEST(0.0, ces_potentiel - ces_actuel) * surface_parcelle_m2 as surface_constructible_restante,
            -- Catégorie
            CASE 
                WHEN (ces_potentiel - ces_actuel) >= 0.20 THEN 'FORT'
                WHEN (ces_potentiel - ces_actuel) >= 0.10 THEN 'MOYEN'
                WHEN (ces_potentiel - ces_actuel) > 0.0 THEN 'FAIBLE'
                ELSE 'SATURE'
            END as categorie
        FROM with_ces
    """

    conn.execute(query)

    print("\n--- Phase 4: Création des index ---")

    # Create indexes for performance
    conn.execute("""
        CREATE INDEX idx_densification_id 
        ON densification_scores(id_parcelle);
    """)

    conn.execute("""
        CREATE INDEX idx_densification_commune 
        ON densification_scores(code_commune);
    """)

    conn.execute("""
        CREATE INDEX idx_densification_categorie 
        ON densification_scores(categorie);
    """)

    print("✓ Index créés: id_parcelle, code_commune, categorie")

    print("\n--- Phase 5: Statistiques ---")

    # Total count
    total = conn.execute("SELECT COUNT(*) FROM densification_scores").fetchone()[0]
    print(f"✓ Total parcelles analysées: {total:,}")

    # Distribution par catégorie
    distribution = conn.execute("""
        SELECT categorie, COUNT(*) as count, 
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
        FROM densification_scores
        GROUP BY categorie
        ORDER BY 
            CASE categorie
                WHEN 'FORT' THEN 1
                WHEN 'MOYEN' THEN 2
                WHEN 'FAIBLE' THEN 3
                WHEN 'SATURE' THEN 4
            END
    """).fetchall()

    print("\n📊 Distribution par catégorie:")
    for cat, count, pct in distribution:
        bar = "█" * int(pct / 2)
        print(f"  {cat:8} : {count:6,} ({pct:5.2f}%) {bar}")

    # Top 5 opportunités
    print("\n🏆 Top 5 opportunités de densification:")
    top5 = conn.execute("""
        SELECT id_parcelle, code_commune, 
               ROUND(surface_parcelle_m2, 0) as surface_m2,
               ROUND(ces_actuel * 100, 1) as ces_pct,
               ROUND(surface_constructible_restante, 0) as constructible_m2
        FROM densification_scores
        WHERE categorie = 'FORT'
        ORDER BY surface_constructible_restante DESC
        LIMIT 5
    """).fetchall()

    for i, (id_p, commune, surf, ces, constr) in enumerate(top5, 1):
        print(f"  {i}. {id_p} ({commune}): {surf:,.0f} m², CES {ces}%, +{constr:,.0f} m² constructibles")

    # Statistics
    stats = conn.execute("""
        SELECT 
            ROUND(AVG(ces_actuel) * 100, 2) as avg_ces_pct,
            ROUND(MEDIAN(ces_actuel) * 100, 2) as median_ces_pct,
            ROUND(AVG(surface_constructible_restante), 0) as avg_constructible_m2
        FROM densification_scores
    """).fetchone()

    print("\n📈 Statistiques globales:")
    print(f"  CES moyen: {stats[0]}%")
    print(f"  CES médian: {stats[1]}%")
    print(f"  Surface constructible moyenne: {stats[2]:,.0f} m²")

    # Cleanup
    conn.execute("DROP TABLE bdnb_temp;")
    conn.close()

    elapsed = time.time() - start_time
    print(f"\n✅ ETL Densification terminé en {elapsed:.1f}s")
    print(f"   Table: densification_scores ({total:,} lignes)")


if __name__ == "__main__":
    main()
