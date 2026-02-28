---
name: cursorrules
description: Règles architecturales Foncier-Express (référence vers .cursor/rules/)
---

# Foncier-Express — Règles

Les règles applicables au projet sont définies dans `.cursor/rules/` :

- **architecture.mdc** — Domain purity, DI, limite 200 lignes, pas de dépendances circulaires
- **tests.mdc** — TDD, conventions de tests (Red-Green-Refactor, couverture services/repos)
- **frontend.mdc** — Vue 3 Composition API, MapLibre, glassmorphism
- **backend.mdc** — Polars lazy, GIS SRID 2154, Pydantic v2
- **devops.mdc** — Docker, PostGIS, healthcheck

Le fichier `.cursorrules` à la racine contient les règles globales courtes.
