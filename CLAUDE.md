C'est un excellent socle. Pour que ton CLAUDE.md soit un véritable "cerveau" pour ton IDE, il doit refléter la maturité actuelle de ton projet : le passage à l'échelle nationale, l'historique 2014-2025 et ton architecture hybride.

Voici la version complétée et optimisée, intégrant tes dernières avancées stratégiques.

CLAUDE.md - Foncier Express (Standard 2026)
🎯 Objectif Produit
Transformer 11 ans de données brutes (2014-2025) en un rapport d'expertise foncière et de faisabilité en < 5 secondes.

🧪 Méthodologie Data (Expertise Mericskay + Modaal)
Nettoyage DVF : Nature mutation = 'Vente', exclusion des transactions < 2000€ (bruit fiscal), surface habitable > 9m².

Cardinalité : Agrégation stricte par id_mutation pour lier les bâtis à leurs parcelles cadastrales respectives.

Enrichissement Qualitatif : - OSM : Scoring de proximité (Éducation, Transports, Commerces) via fonction de décroissance exponentielle (Half-life).

BDNB : Intégration du DPE, de l'année de construction et de la hauteur du bâti.

Historique : Analyse des tendances sur 11 ans pour calculer la plus-value et la résilience du marché.

🏗️ Architecture Logicielle & Stack
Architecture : Clean Architecture (SOLID) avec limite stricte de 400 lignes par fichier.

Base de Données Hybride :

DuckDB (OLAP) : Moteur spatial pour le querying massif (DVF + Cadastre + BDNB).

PostgreSQL (OLTP) : Gestion des utilisateurs, des crédits (Pay-per-view) et de l'authentification.

Backend : FastAPI (Python 3.11), SQLAlchemy 2.0 (Async), ReportLab (PDF).

Frontend : Vue.js 3 (Composition API), MapLibre GL JS (Rendu WebGL), Tailwind CSS (Premium Glassmorphism).

📏 Conventions & Règles de Seniority
Fichiers : Max 400 lignes. Si dépassement -> Refactoring obligatoire (ISP/SRP).

Types : Typage strict (Pydantic côté API, TypeScript-like patterns côté Vue).

Sécurité : Les rapports PDF sont protégés par un système de crédits (1 crédit = 1 rapport).

UI : Design "Stripe-like" (Glassmorphism, Inter Font, micro-animations).

🚀 État d'avancement (Sprints)
[x] Sprint 1-2 : Pipeline ETL Polars & DuckDB (9.7M mutations indexées).

[x] Sprint 3 : Moteur d'enrichissement OSM (Scoring qualitatif fonctionnel).

[x] Sprint 4 : API FastAPI & Génération PDF (ReportLab).

[x] Sprint 5 : Modèle Économique (Système de crédits PostgreSQL).

[x] Sprint 6-7 : UI Alpha (MapLibre + Vue 3) & Intégration Parcelles.

[x] Sprint 8 : Refonte Design Premium & Bâtiments 3D (BDNB).

[x] Sprint 9 : Analyse Temporelle 2014-2025 & Graphiques d'Évolution.

[ ] Sprint 10 : Dockerisation Production & CI/CD.
