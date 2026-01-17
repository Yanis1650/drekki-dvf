# Intégration PLU - Guide d'Implémentation

## Contexte

L'API GPU (Géoportail de l'Urbanisme) n'est pas directement accessible via un endpoint REST simple. Les données PLU sont disponibles via :

1. **WFS (Web Feature Service)** : Standard OGC pour interroger des données géographiques
2. **Fichiers CNIG** : Téléchargement des PLU au format standardisé
3. **API Géoplateforme** : Nouvelle API IGN (remplace GPU)

## Approches Possibles

### Option 1 : WFS (Recommandé pour production)

**Avantages** :
- Données officielles et à jour
- Interrogation par coordonnées
- Standard OGC

**Inconvénients** :
- Configuration complexe
- Requêtes lentes (réseau)

**Exemple d'implémentation** :
```python
from owslib.wfs import WebFeatureService

wfs = WebFeatureService(
    url='https://data.geopf.fr/wfs',
    version='2.0.0'
)

# Interroger par bbox
response = wfs.getfeature(
    typename='LANDUSE.ZONING',
    bbox=(lon-0.001, lat-0.001, lon+0.001, lat+0.001),
    srsname='EPSG:4326'
)
```

---

### Option 2 : Fichiers CNIG (Recommandé pour ce projet)

**Avantages** :
- Données locales (pas de réseau)
- Requêtes rapides
- Intégration DuckDB facile

**Inconvénients** :
- Nécessite téléchargement initial
- Mise à jour manuelle

**Implémentation** :

1. **Télécharger les PLU** :
   - Source : https://www.geoportail-urbanisme.gouv.fr/
   - Format : GeoJSON ou Shapefile
   - Scope : Département 35 (Ille-et-Vilaine)

2. **Importer dans DuckDB** :
```sql
CREATE TABLE plu_zones AS
SELECT 
    code_commune,
    libelle_zone,  -- U, AU, A, N
    ST_GeomFromText(geometry) as geometry
FROM read_json('data/plu_35.geojson');

CREATE INDEX idx_plu_spatial ON plu_zones USING RTREE(geometry);
```

3. **Modifier ETL densification** :
```python
# Dans etl_densification.py, remplacer:
# CAST(0.40 AS DECIMAL(5, 4)) as ces_potentiel

# Par:
CASE 
    WHEN plu.libelle_zone LIKE 'U%' THEN 0.50
    WHEN plu.libelle_zone LIKE 'AU%' THEN 0.30
    WHEN plu.libelle_zone LIKE 'A%' THEN 0.05
    WHEN plu.libelle_zone LIKE 'N%' THEN 0.02
    ELSE 0.40
END as ces_potentiel

# Ajouter LEFT JOIN:
LEFT JOIN plu_zones plu ON ST_Contains(plu.geometry, ST_Centroid(p.geometry))
```

---

### Option 3 : Valeurs par défaut par commune (Solution temporaire)

**Avantages** :
- Simple et rapide
- Pas de dépendance externe

**Inconvénients** :
- Approximation grossière
- Pas de différenciation intra-commune

**Implémentation** :
```python
# Mapping commune → CES potentiel moyen
CES_BY_COMMUNE = {
    "35238": 0.45,  # Rennes (urbain dense)
    "35281": 0.35,  # Saint-Malo (urbain moyen)
    # ... autres communes
}

# Dans ETL:
CASE 
    WHEN code_commune = '35238' THEN 0.45
    WHEN code_commune = '35281' THEN 0.35
    ELSE 0.40
END as ces_potentiel
```

---

## Recommandation

**Pour ce projet** : **Option 2 (Fichiers CNIG)**

**Raison** :
- Données locales → Performances optimales
- Intégration DuckDB native
- Pas de dépendance réseau
- Précision maximale (zone par zone)

**Étapes d'implémentation** :

1. Télécharger PLU Dept 35 depuis Géoportail
2. Convertir en GeoJSON si nécessaire
3. Créer table `plu_zones` dans DuckDB
4. Modifier `etl_densification.py` pour JOIN spatial
5. Re-exécuter ETL

---

## Ressources

- **Géoportail de l'Urbanisme** : https://www.geoportail-urbanisme.gouv.fr/
- **Standard CNIG** : http://cnig.gouv.fr/
- **OWSLib (WFS)** : https://geopython.github.io/OWSLib/
- **DuckDB Spatial** : https://duckdb.org/docs/extensions/spatial

---

## TODO

- [ ] Télécharger PLU Dept 35
- [ ] Créer script `data-pipeline/import_plu.py`
- [ ] Modifier `etl_densification.py` pour intégrer PLU
- [ ] Tester sur échantillon de parcelles
- [ ] Documenter dans CHECKPOINT_13.md
