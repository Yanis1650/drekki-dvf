# Architecture Foncier-Express

## Vue d'ensemble

Foncier-Express suit une **Clean Architecture** avec séparation stricte des responsabilités.
L'application est libre, sans compte ni authentification : l'API est en **lecture seule**
au-dessus d'un unique fichier DuckDB. Il n'y a pas de base transactionnelle.

## Stack technique

| Composant | Technologie | Rôle |
|-----------|------------|------|
| API | FastAPI (Python 3.11) | Endpoints REST, validation Pydantic |
| OLAP | DuckDB + Spatial | Querying massif (DVF, cadastre, BDNB) |
| ETL | Polars | Nettoyage et agrégation des données DVF |
| Frontend | Vue.js 3 (Composition API) | Interface cartographique |
| Cartographie | MapLibre GL JS | Rendu WebGL des parcelles et transactions |
| UI | Tailwind CSS | Charte stricte, vérifiée en CI — voir [CHARTE_GRAPHIQUE.md](CHARTE_GRAPHIQUE.md) |
| PDF | Jinja2 + Playwright | Génération de rapports HTML → PDF |

## Architecture backend

```
app/
├── api/v1/endpoints/    # Couche HTTP (routes FastAPI, thin layer)
├── domain/              # Modèles purs — AUCUNE dépendance externe
├── schemas/             # Schémas Pydantic (validation entrée/sortie API)
├── services/            # Logique métier (orchestration)
├── repositories/        # Accès aux données (DuckDB)
├── infrastructure/      # Connexions DB, pool DuckDB, config
├── templates/           # Templates HTML pour rapports PDF
└── scripts/             # Utilitaires CLI
```

### Flux de données

```
HTTP Request → Endpoint → Service → Repository → DuckDB
                                                        ↓
HTTP Response ← Endpoint ← Service ← Pydantic Schema ←─┘
```

### Principes SOLID appliqués

- **Single Responsibility** : chaque fichier a une seule responsabilité, max 200 lignes
- **Dependency Inversion** : les services dépendent d'interfaces abstraites (ABC), pas d'implémentations
- **Interface Segregation** : les repositories sont découpés en mixins (parcelles, transactions, enrichissement)
- **No Circular Dependencies** : flux unidirectionnel strict `endpoints → services → repositories`

## Architecture base de données

### DuckDB (OLAP) — Moteur d'analyse

Base embarquée optimisée pour les requêtes analytiques. Une base par
département — voir [ADR-0001](adr/0001-duckdb-lecture-seule.md) et
[ADR-0003](adr/0003-une-base-par-departement.md).

- Extension `spatial` pour les requêtes géospatiales, chargée au plus une fois
  par connexion et jamais bloquante (`app/infrastructure/duckdb_spatial.py`)
- Tables principales : `mutations_aggregated` (mutations DVF agrégées),
  `france_foncier_test` (jointure mutations × parcelles × BDNB), `parcelles`,
  `densification_scores`, `confidence_scores`, `dfi_filiations`, `bdnb_stats`,
  `plu_zones`. Les volumes réels de la base servie sont dans
  [PIPELINE.md](PIPELINE.md).
- Connexions partagées pour tout le processus : `DuckDBPool` par département en
  mode multi-départements, registre par fichier en mode base unique. Les
  repositories sont construits à chaque requête, pas les connexions.

### Disponibilité des données

Le pipeline ETL est modulaire : selon les étapes réellement exécutées pour un
département, certaines tables peuvent être absentes (`dfi_filiations` sans ETL
DFI, `points_interet` sans ETL POI).

L'API distingue explicitement **« donnée non chargée »** de **« pas de résultat »** :

| Situation | Réponse |
|-----------|---------|
| Table absente | `503` avec `error: "data_unavailable"` et le nom du jeu de données |
| Extension spatiale indisponible | `503` avec `error: "spatial_unavailable"` |
| Requête valide, aucun résultat | `200` avec une liste vide |

C'est délibéré : un `except` qui renvoie une liste vide transforme « je n'ai pas
la donnée » en « il n'y a pas de donnée », et l'API se met à affirmer du faux.
Voir `app/infrastructure/data_availability.py`.

Les deux exceptions dérivent de `ResourceUnavailableError`
(`app/infrastructure/unavailable.py`). Chaque endpoint la ré-émet **avant** son
`except Exception` générique :

```python
    except ResourceUnavailableError:
        raise                      # -> 503 explicite
    except Exception:
        raise HTTPException(500, "...")
```

Sans cette reprise, le filet générique convertissait une indisponibilité
légitime en « erreur serveur » — la carte a ainsi renvoyé un 500 à son premier
chargement, le temps que l'extension spatiale se charge.

### Extension spatiale

`ensure_spatial()` ne tente le chargement qu'une fois par connexion, sous
verrou. FastAPI sert les endpoints synchrones depuis un pool de threads qui
partagent la connexion : sans ce verrou, deux requêtes simultanées lançaient
chacune `INSTALL spatial` et l'une des deux échouait — un défaut intermittent,
invisible en test séquentiel.

## Pipeline ETL

```
data-pipeline/
├── etl_build_dept.py          # Point d'entrée : construction par département
├── etl_build_steps/           # Étapes modulaires
│   ├── golden_join.py         # Jointure DVF ↔ cadastre
│   ├── bdtopo.py              # Enrichissement BDNB (DPE, hauteur, année)
│   ├── densification.py       # Potentiel de densification
│   ├── confidence.py          # Calcul de l'indice de confiance
│   ├── rnu.py                 # Classification RNU
│   └── optimize.py            # Optimisation des tables finales
├── etl_dvf.py                 # Import DVF brut
├── etl_dfi.py                 # Import filiation cadastrale (DFI)
└── etl_osm_enrichment.py      # Scoring proximité OSM
```

### Méthodologie de nettoyage DVF

Basée sur les travaux de Boris Mericskay (Université Rennes 2) :

- Filtrage : `nature_mutation = 'Vente'`, exclusion ≤ 1 000 EUR, surface > 9m²
- Agrégation par `id_mutation` pour lier bâtis et parcelles
- Enrichissement qualitatif via OSM (proximité transports, éducation, commerces)

## Frontend

```
frontend/src/
├── components/          # Composants Vue (carte, panels, timeline)
│   └── parcel/          # Sous-composants parcelle (header, badge, filiation)
├── composables/         # Hooks réutilisables (useMapContainer, mapColorSchemes)
├── api/                 # Client Axios centralisé
└── App.vue              # Point d'entrée
```

### Patterns

- **Composition API** avec `<script setup>`
- **Composables** pour la logique partagée (pas de store global sauf nécessité)
- **Client API centralisé** : toutes les requêtes passent par `api/client.js`

## Indice de confiance

Scoring multi-source pour qualifier la fiabilité des données par parcelle :

| Source | Poids | Critères |
|--------|-------|----------|
| BDNB | 30% | DPE, année construction, hauteur bâti |
| DVF | 25% | Nombre et récence des transactions |
| Densification | 25% | Potentiel constructible |
| Fraîcheur | 20% | Ancienneté de la dernière donnée |

Niveaux : **Elevée** (>=70), **Moyenne** (40-69), **Faible** (<40)

## Conventions

- **Fichiers** : max 200 lignes, refactoring obligatoire au-delà
- **Tests** : TDD (Red → Green → Refactor), couverture obligatoire sur services/repositories
- **Linting** : `ruff check .` (Python), `npm run build` (Frontend)
- **Typage** : Pydantic strict côté API, props typées côté Vue
