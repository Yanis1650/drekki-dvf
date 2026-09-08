-- Migration : corriger le CES potentiel des usages accentués
--
-- À appliquer sur les bases DuckDB existantes (déjà buildées).
-- Lors d'un rebuild complet (ETL), la correction est portée par
-- etl_build_steps/densification.py — voir le commit
-- « fix(densification): comparer type_usage avec ses accents ».
--
-- Usage (DuckDB CLI) :
--   duckdb data/dept35.duckdb < migrations/fix_ces_potentiel_accents.sql
--
--
-- Le problème
-- -----------
-- L'étape densification comparait `type_usage` à 'Residentiel collectif' et
-- 'Dependance', sans accent. Or `bdnb_stats` est un `SELECT *` du Parquet
-- BDNB, dont la colonne `usage_niveau_1_txt` s'écrit « Résidentiel collectif »
-- et « Dépendance ». Ces deux tests ne pouvaient jamais aboutir : les parcelles
-- concernées tombaient dans le défaut `ELSE 0.40` au lieu de 0,60 et 0,25.
--
-- Deux autres usages ne correspondaient pas non plus, sans conséquence :
-- « Résidentiel individuel » vaut 0,40, soit le défaut lui-même, et
-- « Tertiaire & Autres » comme « Secondaire » n'ont pas d'accent.
--
--
-- Pourquoi une correction ciblée suffit
-- -------------------------------------
-- `ces_potentiel` est ensuite écrasé par les étapes GPU puis RNU, mais
-- seulement `WHERE categorie = 'INCONNU'`. Or la catégorie ne vaut INCONNU que
-- si `potentiel_densification` est NULL, ce qui dépend de `ces_actuel` et de
-- `source_ces` — que l'accent ne touche pas. L'ensemble des lignes reprises par
-- GPU et RNU est donc identique avec ou sans le bug : les lignes corrigées ici
-- sont exactement celles qu'un rebuild aurait calculées autrement.
--
-- Restreindre à `source_ces IN ('bdnb_emprise', 'bdnb_usage_only')` garantit de
-- ne pas écraser une valeur posée après coup par GPU ('plu_gpu'), BD TOPO
-- ('bdtopo') ou RNU ('rnu_proximite').
--
-- `confidence_scores` n'est pas concernée : son `score_densification` ne lit que
-- `source_ces`, et sa pondération que `zone_non_mutable`. Ni l'un ni l'autre ne
-- changent ici.
--
-- Idempotente : relancée, elle ne trouve plus de ligne à corriger.

UPDATE densification_scores AS d
SET ces_potentiel                  = v.ces_potentiel,
    potentiel_densification        = v.potentiel,
    surface_constructible_restante = v.surface,
    categorie                      = v.categorie
FROM (
    SELECT
        id_parcelle,
        ces_potentiel,
        potentiel,
        CASE
            WHEN ces_actuel IS NOT NULL THEN potentiel * surface_parcelle_m2
            ELSE NULL
        END AS surface,
        -- Mêmes seuils que l'étape : FORT à 0,25, MOYEN à 0,10, FAIBLE au-delà
        -- de 0,02 strictement, SATURE en deçà.
        CASE
            WHEN potentiel IS NULL  THEN 'INCONNU'
            WHEN potentiel >= 0.25  THEN 'FORT'
            WHEN potentiel >= 0.10  THEN 'MOYEN'
            WHEN potentiel > 0.02   THEN 'FAIBLE'
            ELSE 'SATURE'
        END AS categorie
    FROM (
        SELECT
            id_parcelle, ces_actuel, surface_parcelle_m2, ces_potentiel,
            CASE
                WHEN ces_actuel IS NOT NULL
                    THEN GREATEST(0.0, ces_potentiel - ces_actuel)
                WHEN source_ces = 'bdnb_usage_only'
                    THEN ces_potentiel * 0.5
                ELSE NULL
            END AS potentiel
        FROM (
            SELECT
                id_parcelle, ces_actuel, surface_parcelle_m2, source_ces,
                CASE type_usage
                    WHEN 'Résidentiel collectif' THEN 0.60
                    WHEN 'Dépendance'            THEN 0.25
                END AS ces_potentiel
            FROM densification_scores
            WHERE type_usage IN ('Résidentiel collectif', 'Dépendance')
              AND source_ces IN ('bdnb_emprise', 'bdnb_usage_only')
        ) AS usages
    ) AS potentiels
) AS v
WHERE d.id_parcelle = v.id_parcelle
  AND d.ces_potentiel IS DISTINCT FROM v.ces_potentiel;
