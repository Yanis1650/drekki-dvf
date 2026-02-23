# Bilan Foncier-Express — Roadmap technique
> À partir du 19 février 2026

---

## Situation au 19 février 2026

| Métrique | Avant | Après | Verdict |
|---|---|---|---|
| Lignes france_foncier_test | 939 265 | 164 941 | ÷5.7 ✅ |
| Match spatial 1:1 | 0.04% | 100% | ✅ |
| Join DVF → BDNB | 16.7% | 95.4% | +78.7 pts ✅ |
| Couverture DPE | 8.6% | 52.0% | +43.4 pts ✅ |
| annee_construction | 0% | 93.3% | ✅ |
| Densification FORT | 95.9% | 9.9% | Discriminant ✅ |
| Score de confiance médiane | — | 0.76 | Nouveau ✅ |
| Parcelles INCONNU densification | — | ~62% | ⚠️ À traiter |

**3 chantiers dans l'ordre :** ① Réduire les 62% INCONNU → ② Interface utilisateur → ③ Extension France entière

---

## Chantier 1 — Réduire les 62% INCONNU (cible : < 10%)

Les parcelles sans données BDNB sont précisément les terrains nus et sous-exploités — les plus intéressantes pour un promoteur. Sans les couvrir, le score ZAN rate sa cible principale.

Les Fichiers Fonciers (MAJIC/DGFIP) ne sont **pas accessibles en open data**. Les deux sources exploitables immédiatement :

| Source | Statut | Ce qu'elle apporte |
|---|---|---|
| GPU / Géoportail Urbanisme | ✅ Disponible | Zone PLU, COS max, hauteur max |
| BD TOPO IGN (bâtiments) | ✅ Open data 2021 | Emprise bâtie réelle, hauteur, nature |
| OSM / Overture Maps | ✅ Open data | Emprise bâtie en complément BD TOPO |
| Fichiers Fonciers (MAJIC) | ❌ Pas open data | Convention Cerema requise |

### Étape A — GPU dans le score ZAN

```python
# etl_gpu_integration.py

import duckdb

conn = duckdb.connect('data/foncier.duckdb')

# 1. Charger les zones GPU dept 35
conn.execute('''
    CREATE OR REPLACE TABLE gpu_zones AS
    SELECT
        id_parcelle,
        libelle_zone,
        CASE
            WHEN libelle_zone LIKE 'U%'   THEN 'urbanise'
            WHEN libelle_zone LIKE 'AU%'  THEN 'a_urbaniser'
            WHEN libelle_zone LIKE 'A%'   THEN 'agricole'
            WHEN libelle_zone LIKE 'N%'   THEN 'naturel'
            ELSE 'inconnu'
        END AS type_zone,
        COALESCE(cos_maximal, 0.60) AS cos_max,
        COALESCE(hauteur_max, 12.0) AS hauteur_max
    FROM read_parquet('data/gpu_dept35.parquet')
    WHERE departement = '35'
''')

# 2. Mettre à jour les INCONNU avec le PLU réel
conn.execute('''
    UPDATE densification_scores d
    SET
        source_ces  = 'plu_gpu',
        potentiel   = CASE
            WHEN g.type_zone = 'urbanise'     THEN GREATEST(0, g.cos_max - d.ces_calcule)
            WHEN g.type_zone = 'a_urbaniser'  THEN 0.75
            WHEN g.type_zone = 'agricole'     THEN 0.05
            WHEN g.type_zone = 'naturel'      THEN 0.02
            ELSE d.potentiel
        END,
        score_label = CASE
            WHEN g.type_zone IN ('agricole', 'naturel') THEN 'non_mutable'
            WHEN potentiel > 0.40                       THEN 'fort'
            WHEN potentiel > 0.20                       THEN 'moyen'
            WHEN potentiel > 0.05                       THEN 'faible'
            ELSE 'sature'
        END
    FROM gpu_zones g
    WHERE d.id_parcelle = g.id_parcelle
      AND d.score_label = 'inconnu'   -- ne toucher que les INCONNU
''')

print(conn.execute("""
    SELECT score_label, COUNT(*), ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(),1) AS pct
    FROM densification_scores GROUP BY 1 ORDER BY 2 DESC
""").fetchdf())
```

### Étape B — BD TOPO IGN (bâtiments)

Téléchargement : https://geoservices.ign.fr/bdtopo — Thème BATI, Dept 35, format GeoPackage (~800 MB décompressé).

```python
# etl_bdtopo_bati.py

import duckdb

conn = duckdb.connect('data/foncier.duckdb')
conn.load_extension('spatial')

# 1. Charger les bâtiments BD TOPO
conn.execute('''
    CREATE OR REPLACE TABLE bdtopo_bati AS
    SELECT
        cleabs            AS id_bdtopo,
        nature,
        hauteur           AS hauteur_m,
        ST_Area(geometry) AS emprise_m2,
        geometry
    FROM ST_Read('data/bdtopo_35.gpkg', layer='batiment')
    WHERE nature NOT IN ('Serre', 'Abri de jardin', 'Réservoir')
''')

# 2. Spatial join BD TOPO → parcelles (même logique que le fix spatial)
conn.execute('''
    CREATE OR REPLACE TABLE bdtopo_parcelle AS
    SELECT
        p.id_parcelle,
        SUM(b.emprise_m2)  AS emprise_bdtopo_m2,
        MAX(b.hauteur_m)   AS hauteur_max_m,
        COUNT(*)           AS nb_batiments_bdtopo
    FROM parcelles p
    JOIN bdtopo_bati b ON ST_Intersects(p.geometry, b.geometry)
    WHERE p.code_commune LIKE '35%'
    GROUP BY p.id_parcelle
''')

# 3. Mettre à jour les INCONNU restants après le GPU
conn.execute('''
    UPDATE densification_scores d
    SET
        source_ces     = 'bdtopo',
        emprise_sol_m2 = bt.emprise_bdtopo_m2,
        ces_calcule    = bt.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2, 0),
        score_label    = CASE
            WHEN (bt.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2,0)) < 0.10 THEN 'fort'
            WHEN (bt.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2,0)) < 0.30 THEN 'moyen'
            WHEN (bt.emprise_bdtopo_m2 / NULLIF(d.surface_parcelle_m2,0)) < 0.55 THEN 'faible'
            ELSE 'sature'
        END
    FROM bdtopo_parcelle bt
    WHERE d.id_parcelle = bt.id_parcelle
      AND d.score_label = 'inconnu'   -- ne toucher que les INCONNU restants
''')
```

### Distribution cible après GPU + BD TOPO

```
fort          ~25%   terrains nus en zone U, zones AU
moyen         ~30%   sous-exploités, marge constructible
faible        ~20%   occupation correcte, peu de marge
sature        ~10%   CES proche du max réglementaire
non_mutable   ~12%   zones N et A
inconnu        <5%   ni GPU ni BD TOPO — acceptable
```

---

## Chantier 2 — Interface utilisateur

### Badge de confiance — ParcelPanel.vue

C'est la fonctionnalité qui différencie l'app d'AppDVF. Le score de confiance doit être visible immédiatement, avec le détail des composantes sur demande.

```vue
<!-- ParcelPanel.vue -->
<template>
  <div class="parcel-panel">

    <!-- Badge confiance -->
    <div class="confidence-header" :class="confidenceClass">
      <span class="badge-label">Fiabilité des données</span>
      <span class="badge-value">{{ parcelle.confidence_label }}</span>
      <span class="badge-score">{{ Math.round(parcelle.confidence_global * 100) }}%</span>
    </div>

    <!-- Détail sur expansion -->
    <details class="confidence-detail">
      <summary>Voir le détail des sources</summary>
      <div class="score-row">
        <span>Croisement BDNB</span>
        <span>{{ scoreIcon(parcelle.score_bdnb) }}</span>
      </div>
      <div class="score-row">
        <span>Données DVF</span>
        <span>{{ scoreIcon(parcelle.score_dvf) }}</span>
      </div>
      <div class="score-row">
        <span>Score ZAN (source : {{ parcelle.source_plu }})</span>
        <span>{{ scoreIcon(parcelle.score_zan_qualite) }}</span>
      </div>
    </details>

    <!-- Avertissement si données partielles -->
    <p v-if="parcelle.warning" class="warning-banner">
      ⚠️ {{ parcelle.warning }}
    </p>

    <!-- Score ZAN -->
    <section class="data-section">
      <h3>Potentiel de densification</h3>
      <div class="zan-badge" :class="parcelle.score_label">
        {{ zanLabel(parcelle.score_label) }}
      </div>
      <dl>
        <dt>Zone PLU</dt><dd>{{ parcelle.libelle_zone || 'Non renseigné' }}</dd>
        <dt>CES actuel</dt><dd>{{ pct(parcelle.ces_calcule) }}</dd>
        <dt>Potentiel</dt><dd>{{ pct(parcelle.potentiel_densification) }}</dd>
        <dt>Source</dt><dd>{{ parcelle.source_ces }}</dd>
      </dl>
    </section>

  </div>
</template>

<script setup>
const confidenceClass = computed(() => ({
  high:   props.parcelle.confidence_global >= 0.80,
  medium: props.parcelle.confidence_global >= 0.55,
  low:    props.parcelle.confidence_global  < 0.55,
}));

const scoreIcon = (s) => s >= 0.8 ? '✅ Élevé' : s >= 0.5 ? '⚠️ Partiel' : '❌ Faible';
const zanLabel  = (l) => ({
  fort:        '🟢 Fort',
  moyen:       '🟡 Moyen',
  faible:      '🟠 Faible',
  sature:      '🔴 Saturé',
  non_mutable: '⛔ Non mutable',
  inconnu:     '⬜ Inconnu',
})[l];
const pct = (v) => v != null ? (v * 100).toFixed(1) + '%' : '—';
</script>
```

### Filtre et export CSV — endpoint FastAPI

```python
# app/api/v1/endpoints/search.py

@router.get('/parcelles/search')
async def search_parcelles(
    code_commune:   str   | None = None,
    score_label:    str   | None = None,   # fort|moyen|faible
    confidence_min: float        = 0.5,
    prix_m2_max:    float | None = None,
    annee_min:      int   | None = None,
    surface_min:    float | None = None,
    export_csv:     bool         = False,
    db = Depends(get_db)
):
    df = db.execute('''
        SELECT
            f.id_parcelle,
            f.code_commune,
            f.valeur_fonciere,
            ROUND(f.valeur_fonciere / NULLIF(f.surface_terrain,0), 0) AS prix_m2,
            f.surface_terrain,
            f.date_mutation,
            d.score_label,
            d.potentiel_densification,
            d.source_ces,
            g.libelle_zone,
            c.confidence_global,
            c.confidence_label
        FROM france_foncier_test f
        LEFT JOIN densification_scores d USING (id_parcelle)
        LEFT JOIN gpu_zones g            USING (id_parcelle)
        LEFT JOIN confidence_scores c    USING (id_parcelle)
        WHERE c.confidence_global >= ?
          AND (? IS NULL OR f.code_commune = ?)
          AND (? IS NULL OR d.score_label  = ?)
          AND (? IS NULL OR f.valeur_fonciere / NULLIF(f.surface_terrain,0) <= ?)
          AND (? IS NULL OR f.surface_terrain >= ?)
          AND (? IS NULL OR YEAR(f.date_mutation) >= ?)
        ORDER BY d.potentiel_densification DESC
        LIMIT 500
    ''', [confidence_min,
          code_commune, code_commune,
          score_label,  score_label,
          prix_m2_max,  prix_m2_max,
          surface_min,  surface_min,
          annee_min,    annee_min]).pl()

    if export_csv:
        return Response(
            content=df.write_csv(),
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename=export_foncier.csv'}
        )
    return df.to_dicts()
```

---

## Chantier 3 — Extension France entière

> ⚠️ **Prérequis** : terminer les chantiers 1 et 2 d'abord. Étendre un pipeline avec 62% d'INCONNU, c'est multiplier le problème par 96.

### Architecture disque par département

Un seul `foncier.duckdb` France entière dépasse les 50 GB du VPS. L'architecture par département permet une montée en charge progressive.

```
data/
├── dept35.duckdb     (~1.5 GB)  ← existant, validé
├── dept29.duckdb     (~1.2 GB)  ← prochain
├── dept22.duckdb     (~800 MB)
├── dept56.duckdb     (~900 MB)
└── ...               96 fichiers × ~1 GB moy = ~96 GB France entière

Budget VPS :
  ~96 GB données + ~12 GB OS/app = ~108 GB total
  → Upgrade VPS 150-200 GB si France entière
  → Alternative : architecture on-demand (LRU cache par département)
```

### Script générique par département

```python
# etl_build_dept.py

import duckdb, sys

DEPT = sys.argv[1]   # ex: '29'
OUT  = f'data/dept{DEPT}.duckdb'

conn = duckdb.connect(OUT)
conn.load_extension('spatial')

# 1. Mutations DVF filtrées
conn.execute(f'''
    CREATE TABLE mutations_aggregated AS
    SELECT * FROM read_parquet('data/dvf_france.parquet')
    WHERE code_departement = '{DEPT}'
      AND YEAR(date_mutation) >= 2020
''')

# 2. Spatial join corrigé (même logique que le fix dept 35)
conn.execute(f'''
    CREATE TABLE france_foncier AS
    WITH mutations AS (
        SELECT *, ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:2154') AS pt
        FROM mutations_aggregated WHERE longitude IS NOT NULL
    ),
    joined AS (
        SELECT m.*, p.id_parcelle,
               ROW_NUMBER() OVER (PARTITION BY m.id_mutation ORDER BY ST_Area(p.geometry)) AS rn
        FROM mutations m
        JOIN read_parquet('data/cadastre_{DEPT}.parquet') p
            ON m.code_commune = p.code_commune
           AND p.section IS NOT NULL AND p.numero IS NOT NULL
           AND ST_Contains(p.geometry, m.pt)
    )
    SELECT * EXCLUDE rn FROM joined WHERE rn = 1
''')

# 3. GPU + BD TOPO + densification + confiance
# ... appel aux ETL existants paramétrés par DEPT ...

conn.execute('VACUUM')
conn.execute('CHECKPOINT')
conn.close()
print(f'dept{DEPT}.duckdb généré ✅')
```

### Router multi-département — FastAPI

```python
# app/db/connection.py

import duckdb
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=10)   # garde les 10 derniers depts en mémoire
def get_conn(dept: str) -> duckdb.DuckDBPyConnection:
    path = Path(f'data/dept{dept}.duckdb')
    if not path.exists():
        raise FileNotFoundError(f'Département {dept} non disponible')
    return duckdb.connect(str(path), read_only=True)

# Usage dans les endpoints — le département est déduit de l'id_parcelle
@router.get('/parcelles/{id_parcelle}/fiche')
async def get_fiche(id_parcelle: str):
    dept = id_parcelle[0:2]   # ex: '35' depuis '350060000A0012'
    conn = get_conn(dept)
    ...
```

---

## Planning

| Période | Chantier | Tâches | Livrable |
|---|---|---|---|
| Semaine 1 | GPU | Intégrer GPU dans densification_scores | INCONNU < 35% |
| Semaine 2 | BD TOPO | Télécharger + spatial join + mise à jour INCONNU | INCONNU < 10% |
| Semaine 3 | UI | Badge confiance + filtre multi-critères + export CSV | App demo-ready |
| Semaine 4 | Validation | Test terrain 20 parcelles Rennes, comparaison Géofoncier | Données validées |
| Mois 2 | France | Pipeline multi-dept, extension Bretagne d'abord | Bretagne ~5 GB |

---

## Ce qui différencie l'app

- **Score ZAN avec source PLU réelle** (GPU) — pas une estimation nationale approximative
- **Niveau de confiance exposé** par parcelle — transparent sur la qualité des croisements
- **Export CSV filtrable** pour usage professionnel — le workflow que ni AppDVF ni Géofoncier ne proposent
