# Plan de cohérence — Règles vs existant

**Date :** 23 février 2025  
**Règles cibles :** limite 200 lignes, architecture SOLID, pas de dépendances circulaires

---

## 1. Synthèse

| Critère | Statut | Détail |
|---------|--------|--------|
| **Dépendances circulaires** | ✅ Conforme | Aucun cycle détecté dans `app/` |
| **Domain purity** | ✅ Conforme | `app/domain` sans SQLAlchemy/Polars |
| **except Exception: pass** | ❌ Violation | 2 occurrences dans `duckdb_pool.py` |
| **Limite 200 lignes** | ❌ Non respectée | 28 fichiers Python + 13 composants Vue dépassent |

---

## 2. Violations : limite 200 lignes

### Backend / app/ (priorité haute)

| Fichier | Lignes | Action proposée |
|---------|--------|-----------------|
| `app/repositories/duckdb_repository.py` | **1191** | Scinder : `DuckDBLandRepository`, `DuckDBTransactionRepo`, `DuckDBEnrichmentRepo` |
| `app/api/v1/endpoints/land.py` | **558** | Extraire handlers : `land_search.py`, `land_parcel.py`, `land_export.py` |
| `app/repositories/dvf_repository.py` | 364 | Scinder : lecture DVF vs agrégation |
| `app/services/report_generator.py` | 308 | Extraire : `report_templates.py`, `report_sections.py` |
| `app/infrastructure/osm_client.py` | 286 | Extraire : `osm_requests.py`, `osm_cache.py` |
| `app/services/parcel_report_service.py` | 282 | Extraire : `parcel_data_fetcher.py`, `parcel_pdf_builder.py` |
| `app/repositories/duckdb_analytics_repository.py` | 264 | Scinder en 2 modules (~130 lignes chacun) |
| `app/repositories/poi_repository.py` | 231 | Réduire via factorisation des requêtes |
| `app/services/enrichment/quality_scorer.py` | 298 | Scinder : `quality_scorer.py` + `quality_utils.py` |

### Data pipeline (priorité moyenne)

| Fichier | Lignes | Action proposée |
|---------|--------|-----------------|
| `data-pipeline/etl_build_dept.py` | **863** | Extraire steps : `etl_build_steps/` (golden, densif, gpu, bdtopo, rnu, confidence) |
| `data-pipeline/etl_bdtopo_bati.py` | 303 | Scinder : parsing vs spatial join |
| `data-pipeline/etl_gpu_integration.py` | 369 | Extraire : `gpu_client.py`, `gpu_parser.py` |
| `data-pipeline/etl_densification.py` | 272 | Réduire via helpers |
| `data-pipeline/etl_osm_enrichment.py` | 271 | Scinder : OSM fetch vs enrich |
| `data-pipeline/etl_confidence_score.py` | 254 | OK en 2 modules |
| `data-pipeline/etl_poi.py` | 250 | Réduire via factorisation |
| `data-pipeline/etl_df i.py` | 295 | Scinder parsing / écriture |
| `data-pipeline/etl_rnu_classification.py` | 221 | Réduire via helpers |
| `data-pipeline/etl_join_test_dept.py` | 206 | Réduire via factorisation |

### Frontend (priorité haute)

| Composant | Lignes | Action proposée |
|-----------|--------|-----------------|
| `MapContainer.vue` | **654** | Extraire : `MapLayers.vue`, `MapSources.js`, `MapControls.vue` |
| `ParcelPanel.vue` | **489** | Extraire : `ParcelSummary.vue`, `ParcelDetails.vue`, `ParcelActions.vue` |
| `ConfidenceBadge.vue` | 339 | Extraire sous-composants |
| `DensificationGauge.vue` | 324 | Extraire : `GaugeChart.vue`, `GaugeLegend.vue` |
| `ParcelHistory.vue` | 344 | Extraire : `HistoryList.vue`, `HistoryFilters.vue` |
| `FiliationTimeline.vue` | 286 | Extraire : `TimelineItem.vue`, `TimelineConnector.vue` |
| `LayerSwitcher.vue` | 260 | Réduire via `LayerGroup.vue` |
| `AnalysisPanel.vue` | 254 | Extraire : `AnalysisSection.vue` |
| `ParcelHeader.vue` | 245 | OK en extrayant stats dans `ParcelStats.vue` |
| `MarketTrendsChart.vue` | 213 | Extraire config chart |
| `SearchHUD.vue` | 207 | Extraire : `SearchForm.vue`, `SearchResults.vue` |
| `App.vue` | 207 | Extraire : `useMapState.js`, `useUserCredits.js` |

### Scripts utilitaires (priorité basse)

- `audit_data_quality.py` (354), `diagnose_parcelle_dupes.py` (183) — scripts de diagnostic, peuvent rester tels quels ou être déplacés dans `scripts/`.

---

## 3. Violations : error handling

### `except Exception: pass` (interdit)

| Fichier | Ligne | Contexte |
|---------|-------|----------|
| `app/infrastructure/duckdb_pool.py` | 71 | `evict_conn.close()` dans eviction |
| `app/infrastructure/duckdb_pool.py` | 103 | `conn.close()` dans `close_all()` |

**Correction :** Remplacer par `logging.warning()` et laisser l’exception se propager ou ignorer explicitement avec un commentaire justifié.

### `except Exception` sans logging (à améliorer)

Les endpoints (`land.py`, `reports.py`, etc.) lèvent des `HTTPException` mais ne loguent pas avant. La règle exige : *« Chaque erreur doit être loguée avec `logging` »*.

**Correction :** Ajouter `logging.exception()` ou `logging.error()` dans chaque bloc `except` avant `raise HTTPException`.

---

## 4. Écarts mineurs (recommandations)

| Écart | Fichier(s) | Recommandation |
|-------|------------|----------------|
| Endpoint accède à l’infra directement | `land.py` importe `get_pool`, `UserRepository` | Router toute l’accès via `deps.py` |
| Endpoint accède aux models | `reports.py` importe `app.infrastructure.models` | Fournir `User` via `deps` ou schéma |

---

## 5. Ordre des modifications proposé

### Phase 1 — Corrections rapides

1. Corriger `duckdb_pool.py` : remplacer `except Exception: pass` par un logging approprié.
2. Ajouter `logging` dans les blocs `except` des endpoints principaux (`land.py`, `reports.py`, `analytics.py`, `filiation.py`).

### Phase 2 — Fichiers critiques (> 400 lignes)

3. Refactoriser `duckdb_repository.py` (1191 lignes) — priorité la plus haute.
4. Refactoriser `land.py` (558 lignes).
5. Refactoriser `MapContainer.vue` (654 lignes).
6. Refactoriser `etl_build_dept.py` (863 lignes).

### Phase 3 — Fichiers 200–400 lignes

7. Scinder les services et repositories restants.
8. Scinder les composants Vue > 200 lignes.

### Phase 4 — Validation

9. Exécuter `madge --circular app/` pour vérifier l’absence de cycles.
10. Linter : `ruff check app/` et `npm run build` frontend.
