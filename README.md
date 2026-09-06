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
  <a href="https://github.com/Yanis1650/drekki-dvf/actions/workflows/ci.yml"><img src="https://github.com/Yanis1650/drekki-dvf/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI GitHub Actions"></a>
</p>

---

## Aperçu

Foncier-Express transforme **11 ans de données DVF** (Demande de Valeurs Foncières, 2014-2025) en une application cartographique interactive avec :

- **Carte des transactions** : visualisation géospatiale des ventes immobilières par parcelle
- **Filiation cadastrale** : arbre généalogique des parcelles (arpentage, lotissement, réunion)
- **Indice de confiance** : scoring multi-source (BDNB, DVF, densification, fraîcheur)
- **Rapports PDF** : fiche d'expertise foncière générée en < 5 secondes
- **Enrichissement qualitatif** : proximité transports, éducation, commerces via OSM
  — étape ETL optionnelle, **non chargée dans la base de démonstration** : l'API
  répond alors `enrichment_available: false` et l'interface omet les scores au
  lieu d'en inventer

Le projet s'appuie sur la méthodologie de Boris Mericskay (Université Rennes 2) pour le nettoyage et l'agrégation des données DVF.

**Démonstration en ligne :** <https://foncier-express.drekky.fr> — Ille-et-Vilaine,
167 124 mutations DVF agrégées de 2014 à mi-2025 sur 333 communes, 2,4 millions de
parcelles cadastrales. Le détail du contenu servi est dans
[`docs/PIPELINE.md`](docs/PIPELINE.md).

**Libre et sans compte.** Pas d'inscription, pas de crédits, pas de paiement :
toutes les fonctionnalités, rapports PDF compris, sont accessibles sans
authentification. L'API est en lecture seule.

**Ne jamais inventer une donnée.** Le pipeline ETL est modulaire, et toutes les
sources ne sont pas forcément chargées pour un département donné. Quand une
donnée manque, l'API le dit (`503 data_unavailable`) au lieu de renvoyer une
valeur par défaut : une filiation absente ne devient pas « parcelle originelle »,
et un score d'environnement non mesuré ne devient pas 5/10.

## Tech Stack

| Couche | Technologies |
|--------|-------------|
| **Backend** | FastAPI, Polars, DuckDB (OLAP) |
| **Frontend** | Vue.js 3 (Composition API), MapLibre GL JS, Tailwind CSS |
| **Fond de carte** | IGN Géoplateforme (libre, sans clé d'API) |
| **Data Pipeline** | Polars, DuckDB, OSMnx (enrichissement) |
| **PDF** | Jinja2 + Playwright (HTML → PDF) |

## Prérequis

- **Python 3.11+**
- **Node.js 18+**

Aucune base de données à installer : l'API lit un fichier DuckDB.

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

### 5. Données DVF et pipeline canonique

Le pipeline DVF récupère les métadonnées des **DVF géolocalisées** depuis
data.gouv.fr, archive chaque publication dans une couche brute versionnée, puis
construit une base DuckDB *candidate*. Chaque run écrit un manifeste contenant
les URL, hashes SHA-256, tailles, millésimes et statut des ressources : c'est la
preuve de provenance des chiffres servis par l'API.

```bash
# Récupération + manifeste + transformation DuckDB
python data-pipeline/run_dvf_pipeline.py

# Prévisualiser la publication courante sans télécharger
python data-pipeline/run_dvf_ingestion.py --dry-run

# Construire ensuite une base déployable pour un département
python data-pipeline/etl_build_dept.py 35
```

Les fichiers DVF sont révisés par publication : une correction peut toucher un
millésime antérieur. Le pipeline ne présume donc pas que seule l'année courante
change. La commande canonique écrit par défaut dans
`data/candidates/foncier-<release>.duckdb` : elle ne remplace pas la base servie
par l'API. Les artefacts bruts restent ignorés par Git dans `data/raw/` ; seul
leur manifeste de provenance est exploité à l'exécution.

`data-pipeline/run_etl.py` est le transformateur DVF de référence.
`data-pipeline/etl_dvf.py` est conservé temporairement pour compatibilité et ne
doit plus être utilisé pour une nouvelle base. Le répertoire compte une
trentaine de scripts dont trois seulement sont des points d'entrée :
[`docs/PIPELINE.md`](docs/PIPELINE.md) dit lesquels, et ce que sont devenus les
autres.

À la fin d'un run, le pipeline produit également
`foncier-<release>.quality.json`. Ses neuf contrôles bloquants vérifient le
schéma canonique, la présence et l'unicité des mutations, les champs requis,
les règles Mericskay (vente, valeur et surface), les dates et le prix au m².
Une candidate en échec reste disponible pour diagnostic mais ne peut pas être
promue.

```bash
# Après un rapport de qualité valide, archive une release immuable
# et met à jour data/releases/current.json de manière atomique.
python data-pipeline/run_dvf_pipeline.py --promote
```

La promotion copie la base, le rapport de qualité et le manifeste d'ingestion
dans `data/releases/`. Une release existante n'est jamais écrasée si son hash
diffère : il faut alors utiliser un nouvel identifiant de publication.

Les filtres, limites d'interprétation et étapes encore nécessaires avant de
servir une release sont détaillés dans
[`docs/METHODOLOGIE_DVF.md`](docs/METHODOLOGIE_DVF.md).

Le pipeline enchaîne 8 étapes (jointure DVF × cadastre × BDNB, densification,
zonage PLU, BD TOPO, RNU, score de confiance, filiation DFI, optimisation).
Chaque source absente de `data/` fait sauter son étape : l'API le signalera
alors par un `503 data_unavailable` plutôt que d'inventer une valeur. Le
diagramme des deux chaînes et le rôle de chaque script sont dans
[`docs/PIPELINE.md`](docs/PIPELINE.md).

### 6. Démarrage

Deux terminaux, l'un pour l'API, l'autre pour l'interface.

**Terminal 1 — backend** (port 8000) :

```bash
# Linux / macOS
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (port 5173) :

```bash
cd frontend
npm run dev
```

| Adresse | Contenu |
|---------|---------|
| http://localhost:5173 | Application |
| http://localhost:8000/docs | Documentation interactive de l'API |
| http://localhost:8000/health | Sonde de santé |

Le frontend lit l'URL de l'API dans `frontend/.env` (`VITE_API_BASE_URL`).
Sans ce fichier, il retombe sur `http://localhost:8000/api/v1`.

Un bandeau orange s'affiche en haut de l'application si le backend ne répond
pas — c'est le symptôme d'un `uvicorn` non démarré, pas d'une erreur de build.

Sous Windows, `.\start.ps1` lance les deux processus et ouvre le navigateur.

#### Vérifier en une commande

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"duckdb","version":"0.1.0"}
```

## Architecture

```
foncier-express/
├── app/                        # Backend FastAPI (Clean Architecture)
│   ├── api/v1/endpoints/       # Routes HTTP
│   ├── domain/                 # Modèles purs (aucune dépendance externe)
│   ├── infrastructure/         # Pool DuckDB, disponibilité des données
│   ├── repositories/           # Accès aux données (DuckDB)
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
├── tests/                      # Tests pytest
└── docs/                       # Documentation métier
```

**Flux de données** : `Endpoints → Services → Repositories → DuckDB`

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour les détails techniques complets.

## Documentation

- [Décisions d'architecture](docs/adr/) — pourquoi DuckDB en lecture seule, pourquoi un `503` plutôt qu'une valeur par défaut, pourquoi une base par département
- [Pipeline de données](docs/PIPELINE.md) — les deux chaînes, quel script lancer, contenu réel de la base servie
- [Architecture](docs/ARCHITECTURE.md) — design technique, principes SOLID, couche de données
- [Méthodologie DVF](docs/METHODOLOGIE_DVF.md) — filtres, agrégation et limites d'interprétation
- [Charte graphique](docs/CHARTE_GRAPHIQUE.md) — couleur, typographie, absence de donnée, et son vérificateur
- [Déploiement VPS](docs/DEPLOYMENT.md) — guide de mise en production (Docker, 35 Go / 11 GB RAM)
- [Lexique Filiation](docs/LEXIQUE_FILIATION.md) — vocabulaire cadastral (arpentage, conservation, lotissement)
- [Lexique Confiance](docs/LEXIQUE_CONFIANCE.md) — calcul du score de confiance multi-source
- [Automatisation GitHub](docs/GITHUB_AUTOMATION.md) — CI, sécurité, surveillance DVF et release contrôlée

## Tests

```bash
pytest                                              # 194 tests backend
mypy app/domain app/infrastructure app/schemas      # périmètre strict
ruff check app data-pipeline tests

cd frontend
npm test                                            # 36 tests
npm run check:charte                                # conformité à la charte
```

La CI exécute ces cinq contrôles, puis construit le frontend et les deux images
Docker de production. Le périmètre de `mypy` est volontairement étroit : le
reste du paquet ne passe pas encore le mode strict, et une configuration
stricte qu'on n'exécute pas est un faux signal — voir la section `[tool.mypy]`
de `pyproject.toml`.

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les conventions de test.

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
