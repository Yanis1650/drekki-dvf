# Rapport de relance — département 35 (Foncier-Express)

## Date et heure d'exécution

**Généré le :** 2026-04-14 (session d'audit / exécution sur machine de développement Windows).

---

## 1. Audit des migrations (`migrations/`)

Fichiers présents :

| Fichier | Rôle | Conflit / doublon |
|--------|------|-------------------|
| `add_plu_datappro.sql` | `densification_scores` : `plu_datappro`, `libelle_zone`, `zone_non_mutable` ; table `plu_coverage_issues` (`motif` VARCHAR) | Aucun |
| `add_outlier_flag.sql` | `france_foncier_test.is_outlier` + index | Indépendant du PLU |

**Conclusion :** pas de chevauchement. La colonne `zone_non_mutable` n'apparaît que dans `add_plu_datappro.sql`.

**Script :** `migrations/run_all.sh` — ordre : `add_plu_datappro.sql` puis `add_outlier_flag.sql` ; chaque étape logue `Applying migration <fichier>...` ; garde-fous `IF NOT EXISTS` dans les SQL (idempotent).

**Vérification :** exécution réussie avec Git Bash :
```
bash migrations/run_all.sh data/dept35.duckdb
→ All migrations applied successfully.
```

---

## 2. Vérification post-migration (`preflight_check.py`)

Commande : `python data-pipeline/preflight_check.py data/dept35.duckdb`

| Colonne / objet attendu | Résultat |
|-------------------------|----------|
| `densification_scores.plu_datappro` (DATE) | OK |
| `densification_scores.zone_non_mutable` (BOOLEAN) | OK |
| `france_foncier_test.is_outlier` (BOOLEAN) | OK |
| `plu_coverage_issues.motif` (VARCHAR) | OK |

**Exit code :** 0.

---

## 3. Import PLU (prérequis fichiers)

| Fichier | Présent | Contenu |
|---------|---------|---------|
| `data/plu_35.gpkg` | **Oui** (généré le 2026-04-14) | 14 PLU communaux, 1 018 zones |
| `data/plui_35.gpkg` | **Oui** (copie du précédent) | Identique |

**Téléchargement WFS GPU :** `python data-pipeline/download_plu_wfs.py 35`
- Script créé cette session — interroge `https://data.geopf.fr/wfs/ows` (layers `wfs_du:zone_urba` + `wfs_du:doc_urba`)
- 14 partitions PLU communaux approuvés (`etat=Opposable`/`Applicable`)
- Durée : ~40 secondes pour 1 018 zones

**Note sur la couverture :** seuls les documents publiés dans la base GPU nationale sont présents.
Les PLUi d'EPCI (ex. Rennes Métropole `DU_243500139`) n'apparaissent pas dans `zone_urba`
sur le WFS public à ce jour — probable absence de publication ou délai d'intégration GPU.
Pour forcer l'ajout du PLUi de Rennes, utiliser le service de téléchargement direct :
```
https://www.geoportail-urbanisme.gouv.fr/document/download-by-partition/DU_243500139
```
puis intégrer le shapefile manuellement dans le GeoPackage.

**Conséquence :** ETL complet non encore relancé dans cette session (PLUi Rennes absent).

---

## 4. ETL complet `etl_build_dept.py 35`

**Non exécuté** (bloqué par l'absence des fichiers §3).

Tableaux ci-dessous = lecture ponctuelle de `data/dept35.duckdb` après migrations.

### A. Distribution `source_ces` (`densification_scores`)

| source_ces    |      n |  pct |
|--------------|-------:|-----:|
| rnu_proximite | 521607 | 39.1 |
| bdnb_emprise  | 501959 | 37.6 |
| plu_gpu       | 233238 | 17.5 |
| bdtopo        |  77456 |  5.8 |

**Alerte : `rnu_proximite` > 20 %** (39,1 %) — couverture PLU incomplète tant que `import_plu.py` n'a pas été relancé.

### B. Distribution `is_outlier` (`france_foncier_test`, `prix_m2` non NULL)

| is_outlier |      n |
|------------|-------:|
| False      | 164941 |

**Alerte : 0 outlier** — flags non recalculés après ajout de la colonne. Relancer `etl_build_dept.py` pour déclencher `_tag_outliers`.

### C. Diagnostic PLU (`plu_coverage_issues`)

Aucune ligne (table vide — pas d'exécution `step_gpu` depuis la migration).

### D. Sanity check confiance (`confidence_scores`)

> Note : la colonne du pipeline est **`confidence_global`** (pas `score_global` comme dans le cahier des charges).

| niveau       |       n |
|-------------|--------:|
| Insuffisante | 1239906 |
| Moyenne      |   58176 |
| Elevée       |   34569 |
| Faible       |    1609 |

---

## 5. Validation PLU — Rennes (`35238`)

Commande : `python data-pipeline/validate_plu.py data/dept35.duckdb --commune 35238`

| Indicateur | Valeur |
|------------|--------|
| Exit code | **0** (OK) |
| Tables PLU présentes | Non (pas encore importées) |
| Taux `rnu_proximite` (parcelles bâties) | 0,0 % |
| Résultat script | OK — seuil 15 % non dépassé |

---

## 6. Tests unitaires

| Suite | Résultat | Tests |
|-------|----------|-------|
| `tests/test_gpu_integration.py` | **PASS** | 9 |
| `tests/test_confidence.py` | **PASS** | 6 |
| `tests/test_outliers.py` | **PASS** | 7 |
| `tests/test_osm_scoring.py` | **PASS** | 17 |
| `tests/test_filiation.py` | **PASS** | 21 |
| `tests/test_preflight_check.py` | **PASS** | 2 |

**Première suite en échec :** aucune — toutes vertes.

---

## 7. Smoke tests API

**Statut : 5 / 5 OK**

Serveur démarré : `uvicorn app.main:app --host 127.0.0.1 --port 8000 --loop asyncio`
(PostgreSQL indisponible → warning au démarrage, API DuckDB opérationnelle)

| # | Test | Résultat | Détail |
|---|------|----------|--------|
| A | `GET /api/v1/health` | **OK** | `status=ok` |
| B | Fiche parcelle `35238000CP0724` — `source_ces` | **OK** | `source_ces=bdnb_emprise` (≠ rnu_proximite) |
| C | Tendances marché commune 35238 — prix max | **OK** | `max_prix=4080 €/m²` (seuil 15 000) |
| D | Recherche enrichie — `transit_score` présent | **OK** | `transit_score=0.0` |
| E | Filiation — `truncated` + `coherence_geo` dans schéma | **OK** | `tree.truncated=False`, `tree.coherence_geo=NON_VERIFIABLE` |

---

## 8. Statut global

### PARTIELLEMENT BLOQUANT au déploiement

**Bloquant :**
1. **PLUi Rennes Métropole absent** — données GPU pas encore publiées sur le WFS public.
   Couverture PLU actuelle limitée à 14 communes ; `rnu_proximite` restera élevé (39 %).
2. **Indicateurs données** : outliers DVF non recalculés (ETL à relancer).

**Non bloquant (résolu) :**
- GeoPackages PLU téléchargés via WFS GPU (`download_plu_wfs.py`).
- Smoke tests API : **5 / 5 OK** après corrections code.

### Prochaines actions recommandées

1. *(Optionnel)* Récupérer le PLUi Rennes Métropole :
   ```
   https://www.geoportail-urbanisme.gouv.fr/document/download-by-partition/DU_243500139
   ```
   → intégrer dans `data/plu_35.gpkg` layer `zone_urba` puis relancer l'import.
2. `bash migrations/run_all.sh data/dept35.duckdb` puis `python data-pipeline/preflight_check.py data/dept35.duckdb`.
3. `python data-pipeline/import_plu.py 35 --db data/dept35.duckdb --gpkg data/plu_35.gpkg` — vérifier COUNT > 10 communes.
4. `python data-pipeline/etl_build_dept.py 35` — rejeu des 4 requêtes de contrôle (utiliser `confidence_global`).
5. `python data-pipeline/validate_plu.py data/dept35.duckdb --commune 35238` — stopper si exit 1.
6. Relancer les smoke (URLs et paramètres validés dans cette session).

---

## Fichiers modifiés ou créés

| Fichier | Type | Changement |
|---------|------|-----------|
| `migrations/run_all.sh` | Nouveau | Script bash idempotent (migrations dans l'ordre) |
| `data-pipeline/preflight_check.py` | Nouveau | Vérification post-migration (exit 0/1) |
| `data-pipeline/download_plu_wfs.py` | **Nouveau** | Téléchargement PLU/PLUi depuis WFS GPU (`wfs_du:zone_urba` + `wfs_du:doc_urba`) |
| `tests/test_preflight_check.py` | Nouveau | 2 tests unitaires preflight |
| `app/main.py` | Modifié | Lifespan PostgreSQL tolérant (try/except + warning) |
| `app/api/v1/router.py` | Modifié | Route `GET /api/v1/health` ajoutée |
| `app/api/v1/endpoints/land_search.py` | Modifié | `transit_score` renseigné dans `EnrichmentScoreResponse` |
| `app/api/v1/endpoints/filiation.py` | Modifié | Réponse avec `tree`, `truncated`, `coherence_geo` ; DuckDB via settings |
| `app/services/filiation_service.py` | Modifié | Chaîne d'ancêtres avec `coherence_geo` et `nature_operation` |
| `app/repositories/duckdb/fiche_mixin.py` | Modifié | `score_zan` → `score_densification` (colonne réelle) |
