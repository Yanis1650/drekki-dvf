# Architecture Foncier-Express

## Vue d'ensemble

Foncier-Express suit une **Clean Architecture** avec séparation stricte des responsabilités. Le système repose sur une architecture hybride OLAP/OLTP pour optimiser les performances d'analyse et la gestion transactionnelle.

## Stack technique

| Composant | Technologie | Rôle |
|-----------|------------|------|
| API | FastAPI (Python 3.11) | Endpoints REST, validation Pydantic |
| OLAP | DuckDB + Spatial | Querying massif (DVF, cadastre, BDNB) |
| OLTP | PostgreSQL / PostGIS | Utilisateurs, crédits, authentification |
| ORM | SQLAlchemy 2.0 (Async) | Accès PostgreSQL |
| ETL | Polars | Nettoyage et agrégation des données DVF |
| Frontend | Vue.js 3 (Composition API) | Interface cartographique |
| Cartographie | MapLibre GL JS | Rendu WebGL des parcelles et transactions |
| UI | Tailwind CSS | Design glassmorphism |
| PDF | Jinja2 + Playwright | Génération de rapports HTML → PDF |

## Architecture backend

```
app/
├── api/v1/endpoints/    # Couche HTTP (routes FastAPI, thin layer)
├── domain/              # Modèles purs — AUCUNE dépendance externe
├── schemas/             # Schémas Pydantic (validation entrée/sortie API)
├── services/            # Logique métier (orchestration)
├── repositories/        # Accès aux données (DuckDB, PostGIS)
├── infrastructure/      # Connexions DB, pool DuckDB, config
├── templates/           # Templates HTML pour rapports PDF
└── scripts/             # Utilitaires CLI
```

### Flux de données

```
HTTP Request → Endpoint → Service → Repository → DuckDB / PostGIS
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

Base embarquée optimisée pour les requêtes analytiques sur 9.7M+ mutations DVF :

- Extension `spatial` pour les requêtes géospatiales
- Tables : `dvf_enriched`, `parcelles_enriched`, `filiation`, `densification`
- Pool de connexions avec thread safety

### PostgreSQL / PostGIS (OLTP) — Gestion utilisateurs

- Gestion des comptes, crédits (pay-per-view) et sessions
- Extension PostGIS pour les opérations géospatiales transactionnelles

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

- Filtrage : `nature_mutation = 'Vente'`, exclusion < 2000 EUR, surface > 9m²
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
