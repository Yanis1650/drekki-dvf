# Documentation Technique — Foncier-Express

> Plateforme d'analyse foncière combinant 11 ans de données immobilières françaises,
> analyse de densification ZAN et cartographie interactive.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture technique](#2-architecture-technique)
3. [Données mobilisées](#3-données-mobilisées)
4. [Pipeline ETL](#4-pipeline-etl)
5. [Modèles de données](#5-modèles-de-données)
6. [Calculs et algorithmes](#6-calculs-et-algorithmes)
7. [API REST](#7-api-rest)
8. [Frontend](#8-frontend)
9. [Génération de rapports PDF](#9-génération-de-rapports-pdf)
10. [Déploiement](#10-déploiement)
11. [Lexique](#11-lexique)

---

## 1. Vue d'ensemble

### Qu'est-ce que Foncier-Express ?

Foncier-Express est une plateforme d'analyse foncière qui transforme des données publiques brutes
(transactions immobilières, cadastre, bâtiments, urbanisme) en intelligence actionnable pour
les professionnels du secteur.

### Cas d'usage principaux

| Profil utilisateur | Usage |
|--------------------|-------|
| **Promoteur immobilier** | Identifier des parcelles à fort potentiel de densification |
| **Urbaniste / Collectivité** | Évaluer la conformité ZAN et les gisements fonciers |
| **Investisseur foncier** | Analyser les tendances de prix au m² sur un secteur |
| **Notaire / Expert** | Générer un rapport d'expertise foncière en quelques secondes |

### Périmètre des données

- **Historique** : 2014 – 2025 (11 ans de transactions DVF)
- **Volume** : 9,7 millions de mutations immobilières (France entière)
- **Granularité** : à la parcelle cadastrale (identifiant à 14 caractères)

---

## 2. Architecture technique

### Stack technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| **API** | FastAPI (Python 3.11) | Endpoints REST, validation Pydantic |
| **OLAP** | DuckDB + extension Spatial | Requêtes analytiques massives (DVF, cadastre, BDNB) |
| **ETL** | Polars | Nettoyage et agrégation des données DVF |
| **Frontend** | Vue.js 3 (Composition API) | Interface cartographique |
| **Cartographie** | MapLibre GL JS | Rendu WebGL des parcelles et transactions |
| **Styles** | Tailwind CSS | Design glassmorphism |
| **PDF** | Jinja2 + Matplotlib + ReportLab | Génération de rapports HTML → PDF |

### Architecture backend (Clean Architecture)

```
app/
├── api/v1/endpoints/    # Couche HTTP — routes FastAPI (thin layer)
├── domain/              # Modèles purs — aucune dépendance externe
├── schemas/             # Schémas Pydantic (validation entrée/sortie API)
├── services/            # Logique métier (orchestration)
├── repositories/        # Accès aux données (DuckDB)
├── infrastructure/      # Connexions DB, pool DuckDB, config
├── templates/           # Templates HTML pour rapports PDF
└── scripts/             # Utilitaires CLI
```

**Flux de données :**
```
HTTP Request
    → Endpoint (validation, routing)
    → Service (logique métier)
    → Repository (accès données)
    → DuckDB
    → Pydantic Schema (sérialisation)
    → HTTP Response
```

**Principes SOLID appliqués :**
- **Single Responsibility** : chaque fichier a une seule responsabilité, max 200 lignes
- **Dependency Inversion** : les services dépendent d'interfaces abstraites (ABC)
- **Interface Segregation** : repositories découpés en mixins thématiques
- **No Circular Dependencies** : flux unidirectionnel strict

### Architecture base de données

#### DuckDB (OLAP)

Base analytique embarquée optimisée pour les requêtes massives sur 9,7M+ mutations :

- Extension `spatial` pour les requêtes géospatiales (ST_Area, ST_Intersects, ST_Transform…)
- Fichiers par département : `dept{XX}.duckdb`
- Pool LRU de connexions (10 connexions max, thread-safe)
- Systèmes de coordonnées : stockage Lambert-93 (EPSG:2154), exposition WGS84 (EPSG:4326)

**Tables principales :**

| Table | Contenu |
|-------|---------|
| `france_foncier_test` | Table centrale : DVF nettoyé + cadastre + BDNB (golden join) |
| `parcelles` | Géométries cadastrales (polygones WKT) |
| `densification_scores` | Scores ZAN par parcelle (CES actuel/potentiel, catégorie) |
| `confidence_scores` | Score de confiance multi-source par parcelle |
| `filiation` | Généalogie cadastrale (DFI : parcelles mères/filles) |
| `bdnb_stats` | Données bâtiment agrégées par parcelle (DPE, hauteur, emprise) |
| `bdtopo_bati` | Emprises bâties BD TOPO (utilisées en fallback) |

#### Tables optionnelles

Le pipeline étant modulaire, ces tables peuvent être absentes selon les étapes
ETL réellement exécutées pour un département :

| Table | Étape ETL | Sans elle |
|-------|-----------|-----------|
| `dfi_filiations` | `etl_dfi.py` | `/filiation` répond `503 data_unavailable` |
| `points_interet` | `etl_poi.py` | scores d'environnement omis (`enrichment_available: false`) |

L'API ne substitue jamais de valeur par défaut à une donnée absente : voir
`app/infrastructure/data_availability.py`.

---

## 3. Données mobilisées

### Sources de données

| Source | Producteur | Contenu | Fréquence | Accès |
|--------|------------|---------|-----------|-------|
| **DVF** | DGFiP | 9,7M transactions immobilières (2014–2025) | Semestrielle | Open data — data.gouv.fr |
| **Cadastre** | IGN / DGFiP | Géométries des parcelles, sections, numéros | Trimestrielle | Open data — cadastre.data.gouv.fr |
| **BDNB** | CSTB | Inventaire national des bâtiments (DPE, hauteur, emprise, usage) | Semi-annuelle | Open data — bdnb.io |
| **BD TOPO** | IGN | Emprises bâties topographiques, géométries précises | Annuelle | Open data — geoservices.ign.fr |
| **PLU / GPU** | Collectivités | Zonage urbain (CES réglementaire par zone) | Variable | Géoportail de l'Urbanisme |
| **OSM** | Communauté | POI : écoles, transports, commerces, espaces verts | Temps réel | Open data — openstreetmap.org |
| **DFI** | DGFiP | Généalogie cadastrale (divisions, lotissements, réunions) | Trimestrielle | Open data — data.gouv.fr |
| **RNU** | DGALN | Classification urbanistique de proximité (fallback) | Statique | Intégré |

---

### Détail par source

#### DVF — Demande de Valeurs Foncières

Données fiscales de toutes les transactions immobilières françaises publiées par la DGFiP.

**Champs utilisés :**

| Champ | Type | Description |
|-------|------|-------------|
| `id_mutation` | str | Identifiant unique de la transaction |
| `date_mutation` | date | Date de la transaction |
| `nature_mutation` | enum | Type d'acte (Vente, Adjudication, Échange…) |
| `valeur_fonciere` | decimal | Montant de la transaction (€) |
| `code_commune` | str | Code INSEE de la commune (5 chiffres) |
| `type_local` | enum | Type de bien (Maison, Appartement, Dépendance) |
| `surface_reelle_bati` | decimal | Surface habitable déclarée (m²) |
| `id_parcelle` | str | Identifiant cadastral (14 caractères) |

**Filtres de nettoyage appliqués (méthode Mericskay) :**
- `nature_mutation = 'Vente'` uniquement (exclusion adjudications, échanges, expropriations)
- `valeur_fonciere >= 1000 €` (exclusion des transferts symboliques)
- `surface_reelle_bati > 9 m²` (exclusion des locaux non habitables)
- Types Maison + Appartement uniquement pour le calcul du prix/m²

---

#### Cadastre — IGN / DGFiP

Plan cadastral numérique : polygones de toutes les parcelles françaises.

**Identifiant parcelle (14 caractères) :**
```
35 238 000 AB 0003
│  │   │   │  └── Numéro de plan (4 chiffres)
│  │   │   └───── Section (2 lettres)
│  │   └───────── Préfixe (3 chiffres, souvent 000)
│  └───────────── Code commune INSEE (3 derniers chiffres)
└──────────────── Code département (2 chiffres)
```

**Champs utilisés :**

| Champ | Description |
|-------|-------------|
| `id_parcelle` | Identifiant cadastral unique |
| `code_commune` | Code INSEE |
| `section` | Lettre(s) de section |
| `numero` | Numéro de plan |
| `geometry` | Polygone WKT (Lambert-93 → WGS84) |
| `surface_m2` | Surface cadastrale officielle |

---

#### BDNB — Base de Données Nationale des Bâtiments (CSTB)

Inventaire national des bâtiments, consolidé par le Centre Scientifique et Technique du Bâtiment.

**Champs utilisés :**

| Champ | Description | Usage dans l'appli |
|-------|-------------|-------------------|
| `dpe_energie` | Étiquette DPE (A-G) | Score de confiance BDNB |
| `annee_construction` | Année de construction | Score de confiance BDNB |
| `hauteur_moyenne` | Hauteur moyenne du bâtiment (m) | Estimation surface plancher |
| `nb_niveau` | Nombre de niveaux | Calcul surface plancher |
| `type_usage` | Usage du bâtiment | Détermination CES potentiel |
| `emprise_sol_m2` | Surface d'emprise au sol (m²) | Calcul CES actuel |
| `cadastre_parcelle_id` | Jointure vers le cadastre | Rattachement parcelle |

**Logique d'estimation de la surface plancher :**
```
Si nb_niveau connu    : surface_plancher = emprise × nb_niveau
Si hauteur connue     : surface_plancher = emprise × ROUND(hauteur / 3.0)
Sinon                 : surface_plancher = emprise (1 niveau supposé)
```

---

#### BD TOPO — IGN

Base topographique de référence de l'IGN. Utilisée en **fallback** pour les parcelles sans données BDNB.

**Champs utilisés :**

| Champ | Description |
|-------|-------------|
| `cleabs` | Identifiant unique BD TOPO |
| `nature` | Nature du bâtiment |
| `usage_1` | Usage dominant |
| `hauteur` | Hauteur du bâtiment (m) |
| `nombre_d_etages` | Nombre d'étages |
| `geometry` | Polygone d'emprise (Lambert-93) |

**Filtres appliqués lors du chargement :**
- Exclusion des constructions légères (`construction_legere = True`)
- Exclusion des bâtiments détruits (`etat_de_l_objet = 'Detruit'`)
- Correction des géométries corrompues via `shapely.make_valid()`

---

#### PLU / GPU — Plans Locaux d'Urbanisme

Documents d'urbanisme municipaux définissant les règles de construction (CES réglementaire par zone).

**Zones et CES potentiel associé :**

| Zone PLU | Libellé | CES potentiel appliqué |
|----------|---------|----------------------|
| `U*` | Zone urbaine | 0.50 |
| `AU*` | Zone à urbaniser | 0.30 |
| `A*` | Zone agricole | 0.05 |
| `N*` | Zone naturelle | 0.02 |
| Défaut | Non renseigné | 0.40 |

**Intégration :** Jointure spatiale `ST_Contains(plu.geometry, ST_Centroid(parcelle.geometry))`

**Source :** Géoportail de l'Urbanisme (fichiers CNIG) ou API WFS Géoplateforme IGN.

---

#### OSM — OpenStreetMap

Points d'intérêt géolocalisés pour le scoring de qualité de localisation.

**Catégories utilisées :**

| Catégorie | POI types | Pondération |
|-----------|-----------|-------------|
| Éducation | schools, kindergartens, universities | Proximité positive |
| Transport | bus_stop, train_station, subway | Proximité positive |
| Nuisances | airports, railways, industrial | Proximité négative |
| Espaces verts | park, forest, garden | Proximité positive |
| Commerce | shops, supermarkets, restaurants | Proximité positive |

**Fonctions de décroissance distance :** exponentielle, linéaire ou sigmoïde (configurable).

---

#### DFI — Documents de Filiation Informatisés

Généalogie administrative des parcelles : historique des divisions, réunions et lotissements depuis
l'informatisation du cadastre (années 1980–1990 selon les départements).

**Types d'opérations (nature DFI) :**

| Code | Nature | Description |
|------|--------|-------------|
| 1 | Arpentage | Mesure et délimitation officielle par géomètre |
| 2 | Conservation | Croquis de conservation (vente partielle, modification limites) |
| 4 | Remaniement | Refonte du plan cadastral d'une commune |
| 5 | Arpentage numérique | Arpentage en mode numérique (DAF) |
| 6 | Lotissement numérique | Création de lotissement en mode numérique |
| 7 | Lotissement | Division en lots destinés à la vente/construction |
| 8 | Rénovation | Rénovation générale du plan cadastral |

**Champs utilisés :**

| Champ | Description |
|-------|-------------|
| `id_dfi` | Identifiant du document (7 caractères) |
| `code_departement` | Département concerné |
| `nature_dfi` | Type d'opération (voir tableau ci-dessus) |
| `date_validation` | Date de validation de l'opération |
| `parcelle_mere` | Identifiant de la parcelle source |
| `parcelle_fille` | Identifiant de la parcelle créée |

---

## 4. Pipeline ETL

### Vue d'ensemble

```
Données brutes (CSV, GeoPackage, JSON)
        ↓
data-pipeline/etl_build_dept.py  ← Point d'entrée (par département)
        ↓
Étape 1 : golden_join.py         ← DVF × Cadastre × BDNB
Étape 2 : densification.py       ← Calcul CES (BDNB)
Étape 3 : gpu.py                 ← Intégration PLU/GPU
Étape 4 : bdtopo.py              ← Fallback BD TOPO pour INCONNU
Étape 5 : rnu.py                 ← Fallback RNU pour INCONNU restants
Étape 6 : confidence.py          ← Score de confiance multi-source
Étape 7 : optimize.py            ← VACUUM, index, checkpoint DuckDB
        ↓
dept{XX}.duckdb  ← Base analytique finale
```

### Étape 1 — Golden Join (`golden_join.py`)

**Objectif :** Créer la table centrale `france_foncier_test` en croisant DVF, cadastre et BDNB.

**Opération :**
```sql
-- Jointure spatiale : point de transaction contenu dans polygone cadastral
SELECT dvf.*, cadastre.geometry, bdnb.*
FROM dvf_filtered dvf
JOIN parcelles cadastre ON ST_Contains(cadastre.geometry, dvf.point)
LEFT JOIN bdnb_stats bdnb ON cadastre.id_parcelle = bdnb.cadastre_parcelle_id
```

**Filtres DVF appliqués (méthode Mericskay) :**
- `nature_mutation IN ('Vente')` uniquement
- `valeur_fonciere >= 1000`
- `surface_reelle_bati > 9` pour les biens bâtis
- Types `Maison` et `Appartement` uniquement pour les calculs de prix/m²
- Agrégation par `id_mutation` (1 vente peut inclure maison + dépendances → ne somme que le bâti principal)

---

### Étape 2 — Densification (`densification.py`)

**Objectif :** Calculer pour chaque parcelle le potentiel de densification ZAN via le Coefficient
d'Emprise au Sol (CES).

**Logique de calcul :**

```python
# CES actuel (depuis BDNB)
ces_actuel = MIN(emprise_sol_m2 / surface_parcelle_m2, 1.0)

# CES potentiel (selon usage du bâtiment)
ces_potentiel = {
    'Residentiel collectif' : 0.60,
    'Residentiel individuel': 0.40,
    'Tertiaire & Autres'    : 0.60,
    'Dependance'            : 0.25,
    'Secondaire'            : 0.35,
    défaut                  : 0.40,
}

# Potentiel de densification
potentiel = MAX(0, ces_potentiel - ces_actuel)
surface_constructible_restante = potentiel × surface_parcelle_m2
```

**Catégorisation :**

| Catégorie | Seuil potentiel | Interprétation |
|-----------|-----------------|----------------|
| `FORT` | ≥ 0.25 | Parcelle fortement sous-densifiée |
| `MOYEN` | ≥ 0.10 | Densification modérée possible |
| `FAIBLE` | > 0.02 | Faible marge de manœuvre |
| `SATURE` | ≤ 0.02 | Parcelle saturée |
| `INCONNU` | — | Données insuffisantes (traité aux étapes 4 et 5) |

---

### Étape 3 — GPU (`gpu.py`)

**Objectif :** Intégrer le CES réglementaire PLU pour remplacer la valeur par défaut (0.40).

Jointure spatiale entre les polygones de zones PLU et les centroïdes de parcelles pour attribuer
le CES potentiel réglementaire propre à chaque zone d'urbanisme.

---

### Étape 4 — BD TOPO (`bdtopo.py`)

**Objectif :** Résoudre les parcelles catégorisées `INCONNU` (pas de données BDNB) en utilisant
les emprises bâties de la BD TOPO IGN.

**Processus :**
1. Chargement du GeoPackage BD TOPO (couche `batiment`)
2. Filtrage des géométries corrompues via `shapely.make_valid()`
3. Jointure spatiale `ST_Intersects(parcelle, batiment)` sur les parcelles `INCONNU`
4. Calcul du CES actuel depuis l'emprise BD TOPO
5. Mise à jour des scores avec `source_ces = 'bdtopo'`

**Après cette étape :** `source_ces` peut valoir `bdtopo`, la confiance associée est de 0.85.

---

### Étape 5 — RNU (`rnu.py`)

**Objectif :** Fallback pour les parcelles encore `INCONNU` après BD TOPO.
Classification par proximité selon le Réseau National d'Urbanisme.

Après cette étape : `source_ces = 'rnu_proximite'`, confiance associée : 0.45.

---

### Étape 6 — Confidence (`confidence.py`)

**Objectif :** Calculer le score de confiance global par parcelle.

Voir section [6.1 Score de Confiance](#61-score-de-confiance).

---

### Étape 7 — Optimize (`optimize.py`)

**Objectif :** Finaliser et optimiser la base DuckDB.

Opérations effectuées :
- `VACUUM` (récupération espace disque)
- `CHECKPOINT` (flush WAL → fichier principal)
- Création des index : `idx_mutations_commune`, `idx_fft_date`, index spatiaux R-tree

---

## 5. Modèles de données

### Modèles domaine (`app/domain/`)

#### Parcelle

```python
class Parcelle:
    id_parcelle: str          # 14 caractères : DDDCCCPPPSSNNNN
    code_commune: str         # 5 chiffres INSEE
    geometry_wkt: str         # Polygone WKT (WGS84)
    surface_m2: Decimal
```

#### Transaction (enregistrement DVF brut)

```python
class Transaction:
    id_mutation: str
    date_mutation: date
    nature_mutation: NatureMutation   # Enum : Vente, Adjudication...
    valeur_fonciere: Decimal          # €
    code_commune: str
    type_local: TypeLocal             # Enum : Maison, Appartement, Dépendance
    surface_reelle_bati: Decimal      # m²
```

#### MutationAggregate (après nettoyage Mericskay)

```python
class MutationAggregate:
    id_mutation: str
    date_mutation: date
    parcelles: list[str]
    surface_habitable_totale: Decimal   # Somme Maison + Appartement uniquement
    nombre_locaux: int
    valeur_fonciere: Decimal

    @computed_field
    def prix_m2(self) -> Decimal:
        return self.valeur_fonciere / self.surface_habitable_totale
```

#### DensificationScore

```python
class DensificationScore:
    id_parcelle: str
    surface_parcelle_m2: Decimal
    surface_plancher_m2: Decimal
    emprise_sol_m2: Optional[Decimal]
    ces_actuel: Optional[Decimal]      # 0.0 – 1.0
    ces_potentiel: Decimal             # 0.0 – 1.0
    source_ces: str                    # bdnb_emprise | bdtopo | plu_gpu | rnu_proximite
    type_usage: Optional[str]
    nb_niveau: Optional[int]

    @computed_field
    def potentiel_densification(self) -> Decimal:
        return max(0, self.ces_potentiel - (self.ces_actuel or 0))

    @computed_field
    def surface_constructible_restante(self) -> Decimal:
        return self.potentiel_densification * self.surface_parcelle_m2

    @computed_field
    def categorie(self) -> str:
        # FORT / MOYEN / FAIBLE / SATURE / INCONNU
```

#### EnrichmentScore

```python
class EnrichmentScore:
    id_parcelle: str
    schools_score: Decimal      # 0 – 10
    transport_score: Decimal    # 0 – 10
    nuisances_score: Decimal    # 0 – 10
    green_spaces_score: Decimal # 0 – 10
    commerce_score: Decimal     # 0 – 10

    @computed_field
    def global_score(self) -> Decimal:
        # Moyenne pondérée des 5 composantes
```

### Modèles filiation (`app/domain/filiation_models.py`)

```python
class ParcelFiliation:
    id_dfi: str                     # 7 caractères
    code_departement: str
    nature_dfi: NatureDFI           # Enum : Arpentage, Conservation, Lotissement...
    date_validation: date
    parcelle_mere: str              # Parcelle source
    parcelle_fille: str             # Parcelle créée

class FiliationNode:
    id_parcelle: str
    parent: Optional[FiliationNode] # Récursif (arbre)
    children: list[FiliationNode]
    date_division: date
    nature_operation: NatureDFI
    depth: int                      # 0 = racine
```

### Modèles analytiques (`app/domain/analytics_models.py`)

```python
class YearlyTrend:
    year: int
    avg_price_m2: Decimal
    transaction_volume: int
    yoy_change_pct: Decimal         # Variation year-over-year

class MarketTrends:
    location: str
    trends: list[YearlyTrend]
    potential_gain_pct: Decimal     # Pente de la régression (% annuel)
    trend_direction: str            # "bullish" | "bearish" | "stable"
    confidence_score: Decimal       # 0 – 10
```

---

## 6. Calculs et algorithmes

### 6.1 Score de Confiance

**Objectif :** Mesurer la fiabilité des données disponibles pour une parcelle.

**Formule (moyenne pondérée sur 4 composantes) :**

```
Confiance = (score_BDNB × 0.30) + (score_DVF × 0.25)
          + (score_Densification × 0.25) + (score_Fraîcheur × 0.20)
```

**Composante BDNB (poids 30%) :**

| Condition | Score |
|-----------|-------|
| DPE + année construction + hauteur tous présents | 1.00 |
| DPE ou année construction présent | 0.60 |
| ID cadastral BDNB présent uniquement | 0.30 |
| Aucune donnée BDNB | 0.00 |

**Composante DVF (poids 25%) :**

| Nombre de transactions | Score |
|------------------------|-------|
| ≥ 5 | 1.00 |
| ≥ 3 | 0.80 |
| ≥ 1 | 0.50 |
| 0 | 0.00 |

**Composante Densification (poids 25%) :**

| Source CES | Score | Explication |
|------------|-------|-------------|
| `bdnb_emprise` | 1.00 | Emprise sol mesurée dans BDNB |
| `bdtopo` | 0.85 | Emprise sol depuis BD TOPO IGN |
| `plu_gpu` | 0.70 | Zonage PLU intégré |
| `rnu_proximite` | 0.45 | Classification RNU (fallback) |
| `bdnb_usage_only` | 0.40 | BDNB sans emprise mesurée |
| `inconnu` | 0.10 | Source non identifiée |

**Composante Fraîcheur (poids 20%) :**

| Année dernière vente | Score |
|----------------------|-------|
| ≥ 2023 | 1.00 |
| ≥ 2020 | 0.80 |
| ≥ 2017 | 0.50 |
| ≥ 2014 | 0.30 |
| Aucune ou antérieure | 0.00 |

**Niveaux de confiance :**

| Label | Seuil | Signification pratique |
|-------|-------|------------------------|
| **Élevée** | ≥ 0.75 | Estimations robustes — exploitables directement |
| **Moyenne** | 0.55 – 0.75 | Données correctes — à utiliser avec discernement |
| **Faible** | 0.35 – 0.55 | Données partielles — vérification terrain recommandée |
| **Insuffisante** | < 0.35 | Données limitées — indicatif uniquement |

---

### 6.2 Potentiel de Densification ZAN

**Objectif :** Quantifier le potentiel constructible d'une parcelle au regard de sa densité actuelle
et des règles d'urbanisme (conformité Zero Artificialisation Nette).

**Calcul du CES actuel :**
```
CES_actuel = MIN(emprise_sol_m2 / surface_parcelle_m2, 1.0)
```

**Calcul du CES potentiel (selon usage) :**
```
Résidentiel collectif  → 0.60
Résidentiel individuel → 0.40
Tertiaire & Autres     → 0.60
Dépendance             → 0.25
Secondaire             → 0.35
Défaut (inconnu)       → 0.40
```

**Potentiel brut :**
```
Potentiel = MAX(0, CES_potentiel - CES_actuel)
Surface constructible restante = Potentiel × Surface_parcelle_m2
```

**Estimation surface plancher :**
```
Si nb_niveau connu    : Surface_plancher = emprise × nb_niveau
Si hauteur connue     : Surface_plancher = emprise × MAX(1, ROUND(hauteur / 3.0))
Sinon                 : Surface_plancher = emprise
```

**Catégorisation ZAN :**

| Catégorie | Seuil | Exemple (1000 m² de parcelle) |
|-----------|-------|-------------------------------|
| `FORT` | potentiel ≥ 0.25 | ≥ 250 m² constructibles restants |
| `MOYEN` | potentiel ≥ 0.10 | 100 – 250 m² constructibles |
| `FAIBLE` | potentiel > 0.02 | 20 – 100 m² constructibles |
| `SATURE` | potentiel ≤ 0.02 | Parcelle saturée |

---

### 6.3 Prix au m² (méthode Mericskay)

**Référence :** Boris Mericskay & Demoraes (2021), Université Rennes 2.

**Objectif :** Calculer un prix/m² fiable en éliminant les transactions aberrantes et en gérant
la cardinalité 1-N des mutations DVF (une vente = maison + dépendances multiples).

**Algorithme :**

```python
# 1. Filtrage des mutations
mutations = dvf.filter(
    nature == 'Vente',
    valeur >= 1000,
    type_local IN ['Maison', 'Appartement'],
    surface_reelle_bati > 9
)

# 2. Agrégation par id_mutation (gestion 1-N)
# Ne somme que les surfaces de type Maison et Appartement
# Exclut les dépendances du calcul de surface
aggregated = mutations.groupby('id_mutation').agg(
    surface_habitable_totale = sum(surface WHERE type IN ['Maison', 'Appartement']),
    valeur_fonciere = first(valeur_fonciere),  # Valeur unique par mutation
)

# 3. Calcul prix/m²
prix_m2 = valeur_fonciere / surface_habitable_totale
```

---

### 6.4 Tendances de marché

**Objectif :** Calculer la tendance d'évolution du prix/m² sur une commune ou un rayon géographique.

**Régression linéaire :**
```python
from statistics import linear_regression

slope, intercept = linear_regression(années, prix_m2_annuels)
croissance_annuelle_pct = (slope / prix_moyen) × 100
```

**Direction de tendance :**

| Condition | Direction |
|-----------|-----------|
| Croissance > +2%/an | `bullish` (haussier) |
| Croissance < -2%/an | `bearish` (baissier) |
| Entre -2% et +2% | `stable` |

**Score de confiance de tendance (0 – 10) :**

| Facteur | Contribution max | Critère |
|---------|-----------------|---------|
| Durée d'historique | 4 pts | ≥10 ans = 4, ≥5 ans = 3, ≥3 ans = 2, sinon 1 |
| Volume moyen de transactions | 4 pts | ≥1000/an = 4, ≥500 = 3, ≥100 = 2, sinon 1 |
| Cohérence des données | 2 pts | Volume min/an ≥50 = 2, ≥10 = 1, sinon 0 |

---

### 6.5 Scoring d'enrichissement OSM

**Objectif :** Évaluer qualitativement la localisation d'une parcelle via la proximité des POI.

**Fonctions de décroissance distance :**

```python
# Exponentielle (décroissance rapide)
score = exp(-distance / rayon_référence)

# Linéaire
score = max(0, 1 - distance / rayon_max)

# Sigmoïde (transition douce)
score = 1 / (1 + exp(k × (distance - seuil)))
```

**Score global (moyenne pondérée des 5 catégories) :**
- Éducation, Transport, Espaces verts, Commerce : pondération positive
- Nuisances : pondération négative (score inversé)

---

## 7. API REST

### Base URL : `/api/v1/`

### Recherche spatiale (`/land/search`)

| Méthode | Endpoint | Description | Paramètres clés |
|---------|----------|-------------|-----------------|
| GET | `/search` | Transactions dans un rayon | `lat`, `lon`, `radius_m`, `date_from`, `date_to` |
| GET | `/search/enriched` | Transactions + scores d'enrichissement | Idem + retourne enrichissement |
| GET | `/commune/{code}/stats` | Statistiques prix par commune | `code_commune`, `date_from`, `date_to` |
| GET | `/commune/{code}` | Toutes les mutations d'une commune | `code_commune`, `date_from`, `date_to` |

### Parcelles (`/land/parcelles`)

| Méthode | Endpoint | Description | Paramètres clés |
|---------|----------|-------------|-----------------|
| GET | `/parcelles/search` | Recherche multi-critères | `code_commune`, `categorie`, `confidence_min`, `prix_m2_max`, `surface_min`, `export_csv` |
| GET | `/parcelles/{id}/fiche` | Profil complet d'une parcelle | `id_parcelle` |
| GET | `/parcelles/{id}/densification` | Détail densification | `id_parcelle` |
| GET | `/communes/{code}/densification/top` | Top opportunités ZAN | `code_commune`, `limit` |

### Analytique (`/analytics`)

| Méthode | Endpoint | Description | Paramètres clés |
|---------|----------|-------------|-----------------|
| GET | `/trends` | Tendances de marché | `code_commune` OU `lat`+`lon`+`radius`, `years` |
| GET | `/parcel/{id}/history` | Historique transactions d'une parcelle | `parcel_id` |

### Filiation (`/filiation`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/{id_parcelle}` | Arbre généalogique cadastral de la parcelle |

### Rapports (`/land/report`)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/report/{id_mutation}` | Génère un rapport expert PDF/HTML |

### GeoJSON cartographique (`/land/geojson`)

| Méthode | Endpoint | Description | Paramètres |
|---------|----------|-------------|------------|
| GET | `/geojson` | Transactions en points GeoJSON | `bbox` (min_lon,min_lat,max_lon,max_lat) |
| GET | `/parcelles` | Polygones parcelles GeoJSON | `bbox`, `filter` (zan / recent) |

### Santé

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Healthcheck API |
| GET | `/api/v1/health` | Healthcheck v1 (même contrat) |

L'API est **libre, sans authentification et en lecture seule** : toutes les
routes sont des `GET` et aucune ne demande d'identification.

### Codes d'erreur spécifiques

| Code | `error` | Signification |
|------|---------|---------------|
| `503` | `data_unavailable` | Jeu de données non chargé dans cette base (voir §2) |
| `503` | `spatial_unavailable` | Extension DuckDB `spatial` non chargeable sur ce serveur |

---

## 8. Frontend

### Structure

```
frontend/src/
├── App.vue                   # Point d'entrée, gestion d'état global
├── components/
│   ├── MapContainer.vue      # Wrapper MapLibre GL JS
│   ├── ParcelPanel.vue       # Panneau latéral (détails parcelle)
│   ├── SearchHUD.vue         # Interface de recherche
│   └── parcel/               # Sous-composants parcelle
│       ├── ParcelHeader.vue
│       ├── ConfidenceBadge.vue
│       └── FiliationTree.vue
├── composables/
│   ├── useParcelSelection.js # Sélection parcelle + synchronisation URL
│   ├── useMapContainer.js    # Logique carte MapLibre
│   └── mapColorSchemes.js    # Schémas de couleurs
└── api/
    └── client.js             # Client Axios centralisé
```

### Patterns

- **Composition API** avec `<script setup>` (Vue 3)
- **Composables** pour la logique réutilisable (pas de store global)
- **URL deep linking** : `?parcel=35238000AB0003` permet de partager une vue directement
- **Client API centralisé** : toutes les requêtes passent par `api/client.js` (intercepteurs auth)

### Cartographie

- **Rendu WebGL** via MapLibre GL JS
- **Couches** :
  - Points de transactions (colorés par prix/m²)
  - Polygones de parcelles (colorés par catégorie ZAN ou confiance)
- **Filtrage viewport** : requêtes bbox pour ne charger que la zone visible
- **Interaction** : clic → sélection parcelle → appel `/fiche` → panneau latéral

---

## 9. Génération de rapports PDF

### Pipeline de génération (`< 5 secondes`)

```
1. Appel GET /report/{id_mutation}
        ↓
2. Collecte données (DuckDB)
   ├── Données parcelle (fiche complète)
   ├── Historique transactions
   ├── Score densification
   ├── Score confiance
   └── Score enrichissement (si les POI sont chargés)
        ↓
3. Génération graphiques (Matplotlib)
   ├── Courbe prix/m² historique
   └── Radar chart enrichissement (omis si aucun score réel)
        ↓
4. Rendu HTML (Jinja2 template)
        ↓
5. Conversion PDF (ReportLab ou Playwright)
        ↓
6. Retour PDF au client
```

> La section « scores de localisation » est omise du rapport lorsque les POI ne
> sont pas chargés : un radar rempli de valeurs par défaut serait indiscernable
> d'une mesure réelle.

### Contenu du rapport

- Identité de la parcelle (commune, section, numéro, surface)
- Score de confiance détaillé
- Historique des transactions (tableau + graphique)
- Potentiel de densification ZAN (CES actuel vs potentiel)
- Scores de localisation OSM (radar)
- Généalogie cadastrale simplifiée

---

## 10. Déploiement

### Infrastructure cible

- **VPS** : 35 Go de stockage, 11 Go de RAM
- **Conteneurisation** : Docker Compose (`docker-compose.prod.yml`)

### Services Docker

```yaml
services:
  backend:     # FastAPI (Python 3.11) — lecture seule sur DuckDB
  frontend:    # Nginx (build Vue.js)
```

Aucune base transactionnelle : l'application est libre et sans compte, il n'y a
donc pas de données utilisateur à stocker.

> `foncier.duckdb` (France entière) pèse ~69 Go et ne tient pas sur le VPS cible
> de 35 Go. Déployer une base par département (`dept35.duckdb`, ~1,5 Go).

---

## 11. Lexique

| Terme | Définition |
|-------|------------|
| **CES** | Coefficient d'Emprise au Sol — ratio entre l'emprise au sol d'un bâtiment et la surface de la parcelle |
| **DVF** | Demande de Valeurs Foncières — base de données fiscale des transactions immobilières publiée par la DGFiP |
| **ZAN** | Zéro Artificialisation Nette — objectif légal (loi Climat et Résilience 2021) de stopper l'étalement urbain en densifiant l'existant |
| **BDNB** | Base de Données Nationale des Bâtiments — inventaire national produit par le CSTB |
| **BD TOPO** | Base de Données Topographiques — référentiel géographique de l'IGN |
| **PLU** | Plan Local d'Urbanisme — document d'urbanisme définissant les règles de construction par zone |
| **GPU** | Géoportail de l'Urbanisme — plateforme nationale centralisant les PLU numériques |
| **OSM** | OpenStreetMap — base de données géographique collaborative mondiale |
| **DFI** | Documents de Filiation Informatisés — données de généalogie cadastrale produites par la DGFiP |
| **RNU** | Règlement National d'Urbanisme — règles s'appliquant en l'absence de PLU |
| **OLAP** | Online Analytical Processing — moteur optimisé pour les requêtes analytiques (ici : DuckDB) |
| **Lambert-93** | EPSG:2154 — système de projection officiel français |
| **WGS84** | EPSG:4326 — système de coordonnées géographiques mondial (GPS, web) |
| **Filiation** | Généalogie d'une parcelle : traçabilité des divisions, réunions et lotissements depuis les années 1980–1990 |
| **Mutation** | Acte notarié enregistrant le transfert de propriété d'un bien immobilier |
| **Parcelle mère** | Parcelle d'origine ayant été divisée ou modifiée |
| **Parcelle fille** | Parcelle créée à partir d'une parcelle mère |
