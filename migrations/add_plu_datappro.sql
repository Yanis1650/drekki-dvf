-- Migration : colonnes PLU dans densification_scores + table plu_coverage_issues
--
-- À appliquer sur les bases DuckDB existantes (déjà buildées).
-- Lors d'un rebuild complet (ETL), ces colonnes sont créées automatiquement
-- par _ensure_columns() dans gpu.py.
--
-- Usage (DuckDB CLI) :
--   duckdb data/dept35.duckdb < migrations/add_plu_datappro.sql

-- Date d'approbation du PLU source (champ datappro GPU).
-- Permet de détecter les communes dont le PLU a été révisé depuis le dernier ETL.
ALTER TABLE densification_scores ADD COLUMN IF NOT EXISTS plu_datappro DATE;

-- Libellé libre du document PLU (ex: "UA", "Zone UB", "1AU").
-- Informatif uniquement — le calcul du CES utilise typezone (normalisé CNIG).
ALTER TABLE densification_scores ADD COLUMN IF NOT EXISTS libelle_zone VARCHAR;

-- Flag booléen : zone PLU non constructible en pratique (zones A et N).
-- La surface_constructible_restante reste calculée (CES actuel vs CES réglementaire),
-- ce flag permet de l'interpréter correctement sans écraser la valeur.
ALTER TABLE densification_scores ADD COLUMN IF NOT EXISTS zone_non_mutable BOOLEAN;

-- Table de diagnostic des communes avec problème de couverture PLU.
-- Créée ou réinitialisée à chaque exécution de step_gpu().
--
-- motif : 'no_plu_gpu'             → commune absente de plu_commune_partition
--         'partition_without_zones' → partition mappée mais aucune zone spatiale
--         'plu_recently_revised'    → datappro < 180j, re-run ETL recommandé
CREATE TABLE IF NOT EXISTS plu_coverage_issues (
    code_commune      VARCHAR NOT NULL,
    parcelles_inconnu INTEGER NOT NULL,
    motif             VARCHAR NOT NULL
);
