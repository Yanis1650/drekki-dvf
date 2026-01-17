---
name: cursorrules
description: This is a new rule
---

# Overview

Insert overview text here. The agent will only see this should they choose to apply the rule.

# FONCIER-EXPRESS: CORE ARCHITECTURAL RULES

## 1. SOLID & CLEAN ARCHITECTURE
- **Domain Purity:** Le dossier `app/domain` ne doit contenir aucune dépendance externe (pas de SQLAlchemy, pas de Polars). Uniquement des DataClasses ou modèles Pydantic de base.
- **Dependency Injection:** Utilise le système de `Depends()` de FastAPI pour injecter les repositories dans les services.
- **Interface Segregation:** Chaque repository doit implémenter une interface abstraite (ABC).

## 2. POLARS & DATA ENGINEERING RULES
- **Lazy First:** Utilise systématiquement `pl.scan_csv()` ou `pl.scan_parquet()`. Ne jamais appeler `.collect()` avant le dernier moment nécessaire.
- **Schema Enforcement:** Chaque pipeline Polars doit avoir un schéma de sortie défini pour garantir l'intégrité des types.
- **No Pandas:** L'usage de Pandas est interdit sauf si une bibliothèque tierce l'impose. Préfère `Polars` ou `PyArrow`.

## 3. SPATIAL & GIS RULES
- **SRID Consistency:** Stockage interne et calculs en Lambert-93 (EPSG:2154). Conversion en WGS84 (EPSG:4326) uniquement pour l'affichage Frontend ou les exports GeoJSON.
- **Spatial Indexing:** Toute table PostGIS ou vue DuckDB doit posséder un index spatial (GIST pour PostGIS, RTREE pour DuckDB) avant toute requête d'intersection.

## 4. CODE QUALITY & LIMITS
- **File Length:** Limite stricte de 400 lignes. Si dépassé, scinder en sous-services (ex: `dvf_cleaning_service.py` et `dvf_aggregation_service.py`).
- **Error Handling:** Ne jamais utiliser de `except Exception: pass`. Chaque erreur doit être logguée avec `logging` et renvoyer une `HTTPException` claire au client.
- **Pydantic V2:** Utilise les types `Annotated` pour la validation de données complexes (ex: coordonnées GPS, codes parcelles).