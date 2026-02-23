---
trigger: always_on
---

# Règles Foncier-Express

Les règles détaillées sont dans `.cursor/rules/` :

- **architecture.mdc** — Clean Architecture, SOLID, limite 200 lignes, pas de dépendances circulaires (toujours actif)
- **frontend.mdc** — Vue 3, MapLibre, Tailwind (frontend/**)
- **backend.mdc** — FastAPI, Polars, GIS (app/**, data-pipeline/**)
- **devops.mdc** — Docker, PostGIS (docker-compose*, Dockerfile*)
