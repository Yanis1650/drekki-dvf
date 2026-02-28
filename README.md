<p align="center">
  <h1 align="center">Foncier-Express</h1>
  <p align="center">
    Analyse foncière DVF open data — de la donnée brute au rapport d'expertise en quelques secondes.
  </p>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.109+-009688.svg" alt="FastAPI"></a>
  <a href="https://vuejs.org"><img src="https://img.shields.io/badge/Vue.js-3-4FC08D.svg" alt="Vue.js 3"></a>
  <a href="https://duckdb.org"><img src="https://img.shields.io/badge/DuckDB-OLAP-FFF000.svg" alt="DuckDB"></a>
</p>

---

## Aperçu

Foncier-Express transforme **11 ans de données DVF** (Demande de Valeurs Foncières, 2014-2025) en une application cartographique interactive avec :

- **Carte des transactions** : visualisation géospatiale des ventes immobilières par parcelle
- **Filiation cadastrale** : arbre généalogique des parcelles (arpentage, lotissement, réunion)
- **Indice de confiance** : scoring multi-source (BDNB, DVF, densification, fraîcheur)
- **Rapports PDF** : fiche d'expertise foncière générée en < 5 secondes
- **Enrichissement qualitatif** : proximité transports, éducation, commerces via OSM

Le projet s'appuie sur la méthodologie de Boris Mericskay (Université Rennes 2) pour le nettoyage et l'agrégation des données DVF.

## Tech Stack

| Couche | Technologies |
|--------|-------------|
| **Backend** | FastAPI, Polars, DuckDB (OLAP), PostgreSQL/PostGIS (OLTP) |
| **Frontend** | Vue.js 3 (Composition API), MapLibre GL JS, Tailwind CSS |
| **Data Pipeline** | Polars, DuckDB, OSMnx (enrichissement) |
| **PDF** | Jinja2 + Playwright (HTML → PDF) |

## Prérequis

- **Python 3.11+**
- **Node.js 18+**
- **Docker** (pour PostGIS — optionnel en mode démo)

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/<votre-org>/foncier-express.git
cd foncier-express
```

### 2. Backend

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

### 3. Frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Configuration

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
# Éditer les fichiers .env selon votre environnement
```

### 5. Base de données PostGIS (optionnel)

Pour les fonctionnalités utilisateurs et crédits (rapports PDF) :

```bash
docker compose up -d
```

Puis exécuter les scripts d'initialisation :

```bash
# Les scripts SQL dans init-db/ sont automatiquement exécutés par Docker
```

### 6. Données DVF

Le pipeline ETL traite les données DVF open data. Consultez `data-pipeline/` pour les détails.

```bash
# Exemple : construire la base pour un département
python data-pipeline/etl_build_dept.py --dept 35
```

### 7. Démarrage

```bash
# Backend (port 8000)
uvicorn app.main:app --reload --port 8000

# Frontend (port 5173, dans un autre terminal)
cd frontend && npm run dev
```

Ou avec le script PowerShell (Windows) :

```powershell
.\start.ps1
```

L'application sera accessible sur **http://localhost:5173** et la documentation API sur **http://localhost:8000/docs**.

## Architecture

```
foncier-express/
├── app/                        # Backend FastAPI (Clean Architecture)
│   ├── api/v1/endpoints/       # Routes HTTP
│   ├── domain/                 # Modèles purs (aucune dépendance externe)
│   ├── infrastructure/         # Connexions DB (DuckDB pool, PostGIS)
│   ├── repositories/           # Accès aux données (DuckDB, PostGIS)
│   ├── schemas/                # Schémas Pydantic (validation API)
│   ├── services/               # Logique métier
│   └── templates/              # Templates HTML (rapports PDF)
├── data-pipeline/              # ETL Polars (DVF, cadastre, BDNB, OSM)
│   └── etl_build_steps/        # Étapes modulaires du pipeline
├── frontend/                   # Vue.js 3 + MapLibre GL JS
│   └── src/
│       ├── components/         # Composants Vue (carte, panels, badges)
│       ├── composables/        # Logique réutilisable (hooks)
│       └── api/                # Client Axios
├── init-db/                    # Scripts SQL d'initialisation PostGIS
├── tests/                      # Tests pytest
└── docs/                       # Documentation métier
```

**Flux de données** : `Endpoints → Services → Repositories → DuckDB/PostGIS`

Voir [CLAUDE.md](CLAUDE.md) pour le contexte produit complet.

## Documentation

- [Lexique Filiation](docs/LEXIQUE_FILIATION.md) — vocabulaire cadastral (arpentage, conservation, lotissement)
- [Lexique Confiance](docs/LEXIQUE_CONFIANCE.md) — calcul du score de confiance multi-source

## Tests

```bash
pytest
```

Le projet suit une approche TDD. Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les conventions de test.

## Contribution

Les contributions sont les bienvenues ! Consultez :

- [CONTRIBUTING.md](CONTRIBUTING.md) — guide de contribution et normes de code
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — code de conduite
- [SECURITY.md](SECURITY.md) — politique de signalement de vulnérabilités

## Licence

MIT — voir [LICENSE](LICENSE).

## Remerciements

- **Boris Mericskay** (Université Rennes 2) — méthodologie d'analyse DVF
- **DVF open data** (DGFiP / data.gouv.fr) — données de transactions immobilières
- **BDNB** (CSTB / data.gouv.fr) — Base de Données Nationale des Bâtiments
- **IGN** — fonds cartographiques et cadastre
