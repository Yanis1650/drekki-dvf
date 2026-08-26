-- Migration : ajout du flag is_outlier dans france_foncier_test
--
-- À appliquer sur les bases DuckDB existantes (déjà buildées).
-- Lors d'un rebuild complet (ETL), is_outlier est calculé automatiquement
-- par _tag_outliers() dans golden_join.py.
--
-- Après cette migration, re-exécuter _tag_outliers sur la base existante pour
-- calculer les flags (sinon toutes les lignes restent à FALSE par défaut).
--
-- Usage (DuckDB CLI) :
--   duckdb data/dept35.duckdb < migrations/add_outlier_flag.sql

ALTER TABLE france_foncier_test ADD COLUMN IF NOT EXISTS is_outlier BOOLEAN DEFAULT FALSE;

-- Index pour filtrage rapide dans les requêtes tendances/stats.
CREATE INDEX IF NOT EXISTS idx_fft_outlier ON france_foncier_test(is_outlier);
