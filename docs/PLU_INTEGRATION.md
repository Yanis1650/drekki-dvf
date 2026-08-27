# Intégration PLU/PLUi — Guide d'implémentation

## Contexte

Les Plans Locaux d'Urbanisme (PLU) déterminent les règles constructives parcelle par parcelle.
Le pipeline ETL les utilise à l'étape 3 (GPU) pour assigner à chaque parcelle INCONNU un CES
potentiel réglementaire plutôt qu'une valeur de fallback RNU.

**Deux types de documents** coexistent sur le territoire :
- **PLU communal** : partition `DU_<INSEE>` — un document par commune
- **PLUi intercommunal (EPCI)** : partition `DU_<SIREN_EPCI>` — un document couvre plusieurs communes membres

Le pipeline résout les deux cas via une table de mapping commune → partition.

---

## Architecture des données

### Tables DuckDB créées par `import_plu.py`

#### `plu_commune_partition`
| Colonne        | Type    | Description                                |
|----------------|---------|--------------------------------------------|
| `code_commune` | VARCHAR | Code INSEE commune (4 ou 5 chiffres)       |
| `partition`    | VARCHAR | Identifiant GPU ex: `DU_35238`, `DU_243500139` |

Index : `idx_pcp_commune(code_commune)`

Source : couche `doc_urba` du GeoPackage GPU, filtrée sur :
- état dans `{Approuvé, Opposable, Applicable, En vigueur}`
- code INSEE non NULL et longueur valide (4 ou 5 caractères)

#### `plu_zones`
| Colonne     | Type     | Description                                   |
|-------------|----------|-----------------------------------------------|
| `partition` | VARCHAR  | Clé de jointure avec `plu_commune_partition`  |
| `typezone`  | VARCHAR  | Type CNIG normalisé (U, AU, A, N, …)          |
| `libelle`   | VARCHAR  | Libellé libre (informatif, non utilisé pour CES) |
| `datappro`  | DATE     | Date d'approbation du PLU                     |
| `geometry`  | GEOMETRY | Polygone de zone (projection locale Lambert 93) |

Index : `idx_pz_partition(partition)`

Source : couche `zone_urba` du GeoPackage GPU.

### Colonnes ajoutées dans `densification_scores`

| Colonne              | Type    | Description                                         |
|----------------------|---------|-----------------------------------------------------|
| `source_ces`         | VARCHAR | `'plu_gpu'` si CES issu du PLU, sinon `'rnu_proximite'` |
| `plu_datappro`       | DATE    | Date d'approbation du PLU source                    |
| `libelle_zone`       | VARCHAR | Libellé libre de la zone PLU                        |
| `zone_non_mutable`   | BOOLEAN | `TRUE` pour zones A et N (faible constructibilité)  |

### Table de diagnostic

#### `plu_coverage_issues`
| Colonne            | Type    | Description                      |
|--------------------|---------|----------------------------------|
| `code_commune`     | VARCHAR | Code INSEE                       |
| `parcelles_inconnu`| INTEGER | Nombre de parcelles non résolues |
| `motif`            | VARCHAR | Voir motifs ci-dessous           |

**Motifs** :
- `no_plu_gpu` — commune absente de `plu_commune_partition` (pas de PLU importé)
- `partition_without_zones` — partition mappée mais aucune zone spatiale trouvée
- `plu_recently_revised` — `datappro` < 180 jours → re-run ETL recommandé

---

## Récupération des données depuis le WFS GPU

`download_plu_wfs.py` construit le GeoPackage source. Deux pièges de l'API GPU
ont chacun fait perdre l'essentiel des données du département 35 — les deux
silencieusement, sans erreur ni avertissement.

### Piège 1 — `zone_urba.insee` est quasi vide

Le champ `insee` de la couche `zone_urba` n'est renseigné que pour une petite
minorité de zones. Filtrer dessus paraît naturel et donne un résultat
plausible, mais ampute le jeu de données :

| Filtre sur `wfs_du:zone_urba` | Zones renvoyées (dept 35) |
|-------------------------------|---------------------------|
| `insee LIKE '35%'`            | 1 018                     |
| `partition IN (…)`            | **22 235**                |

C'est ce qui avait fait conclure que le PLUi de Rennes Métropole n'était pas
publié sur le WFS, et justifié le téléchargement manuel d'une archive de
184 Mo. Ses 4 069 zones y étaient depuis le début, sous la partition
`DU_243500139`, simplement sans `insee`.

**Toujours filtrer `zone_urba` sur `partition`.**

Les partitions viennent de la couche `doc_urba_com`, qui porte le lien
commune ↔ document. C'est la seule qui rattache une commune à un document
**intercommunal** : un PLUi a une partition `DU_<SIREN_EPCI>`, qu'aucun filtre
par code département ne peut retrouver.

### Piège 2 — le serveur tronque sans le dire dans le corps

Le WFS GPU plafonne ses réponses à **5 000 features** et ne supporte pas
`startIndex`. Il signale la coupure dans l'en-tête GeoJSON :

```json
{ "numberMatched": 9627, "numberReturned": 5000, "features": [ … ] }
```

Comparer le nombre de features reçues au `count` demandé (9 999) ne détecte
rien : la réponse paraît complète. Le seul test fiable est
`numberReturned < numberMatched`, encapsulé dans `WfsResult.truncated`. Un lot
tronqué est alors redécoupé partition par partition ; si une partition seule
dépasse encore le plafond, le script le signale explicitement plutôt que de
laisser croire à un import complet.

### Couverture obtenue (département 35)

| Indicateur                     | Avant | Après  |
|--------------------------------|-------|--------|
| Communes avec partition PLU    | 57    | **287** |
| Zones PLU importées            | 5 087 | **22 235** |

Sur 332 communes, 301 déclarent un document d'urbanisme et 287 en publient
effectivement les zones. Les autres relèvent du RNU, sans PLU opposable.

---

## Scripts

### `import_plu.py` — Import du GeoPackage GPU

Importe les couches `doc_urba` et `zone_urba` d'un GeoPackage GPU dans DuckDB.
Doit être exécuté **avant** `etl_build_dept.py`.

```bash
# Avec GeoPackage local
python import_plu.py 35 --db data/dept35.duckdb --gpkg data/plu_35.gpkg

# Avec téléchargement automatique depuis la Géoplateforme IGN
python import_plu.py 35 --db data/dept35.duckdb --download
```

**Source GeoPackage** : `https://data.geopf.fr/telechargement/resource/pack_plu`
Un fichier par département, ~200–800 MB selon la densité communale.

**Détection du champ commune** : le script détecte automatiquement le nom du champ
INSEE dans `doc_urba` (variantes CNIG selon millésime : `insee`, `code_commune`, `code_insee`).

**Validation de contenu** : après détection du champ, le script compte et logue les
lignes avec code INSEE NULL ou de longueur invalide (hors 4–5 caractères). Ces lignes
sont exclues du mapping mais n'interrompent pas l'import.

### `validate_plu.py` — Validation du mapping PLUi

Vérifie sur données réelles que le mapping PLUi fonctionne. Mesure le taux de
`rnu_proximite` sur les **parcelles bâties uniquement** (`emprise_sol_m2 > 0`).

```bash
python validate_plu.py data/dept35.duckdb
python validate_plu.py data/dept35.duckdb --commune 35238
```

**Seuil** : `MAX_RNU_FALLBACK_RATE = 0.15`
Exit code 1 si, pour une commune avec partition PLU connue, plus de 15 % de ses
parcelles bâties ont `source_ces = 'rnu_proximite'`. Les communes sans partition
connue (pas de PLU GPU) ne déclenchent pas d'échec.

Ce script est appelé automatiquement dans `etl_build_dept.py` après `step_gpu`,
en mode **non-bloquant** : un avertissement est loggé mais l'ETL ne s'arrête pas.

---

## Étape GPU dans le pipeline ETL (`etl_build_steps/gpu.py`)

### Flux de résolution

```
parcelle.code_commune
    → JOIN plu_commune_partition → partition
    → JOIN plu_zones (ST_Intersects centroïde × zone) → typezone
    → normalisation typezone → parent_zone (U/AU/A/N/autre)
    → CES potentiel + catégorie + flag zone_non_mutable
```

### Normalisation `typezone` → `parent_zone`

```sql
CASE
    WHEN typezone LIKE 'AU%' THEN 'AU'   -- AU avant A (ordre crucial)
    WHEN typezone LIKE 'U%'  THEN 'U'
    WHEN typezone LIKE 'A%'  THEN 'A'
    WHEN typezone LIKE 'N%'  THEN 'N'
    ELSE 'autre'
END
```

### Table de correspondance CES

| Zone parent | CES potentiel | Catégorie      | `zone_non_mutable` |
|-------------|---------------|----------------|--------------------|
| U           | 0.50          | MOYEN          | FALSE              |
| AU          | 0.30          | FORT           | FALSE              |
| A           | 0.05          | NON_MUTABLE    | TRUE               |
| N           | 0.02          | NON_MUTABLE    | TRUE               |
| autre       | 0.40          | FAIBLE         | FALSE              |

Le flag `zone_non_mutable` permet d'interpréter `surface_constructible_restante`
sans écraser la valeur calculée.

### Cas non résolus

Les parcelles qui restent `INCONNU` après l'étape GPU sont tracées dans
`plu_coverage_issues`. Les causes les plus fréquentes :
1. Commune hors périmètre du GeoPackage téléchargé
2. PLUi dont la commune n'est pas listée dans `doc_urba`
3. Centroïde de la parcelle hors des zones connues (erreur géométrique GPU)

---

## Migration sur base existante

Pour ajouter les colonnes PLU à une base déjà construite sans rebuild complet :

```bash
duckdb data/dept35.duckdb < migrations/add_plu_datappro.sql
```

Puis ré-exécuter `import_plu.py` et relancer uniquement `step_gpu`.

---

## Ressources

- **Géoportail de l'Urbanisme** : https://www.geoportail-urbanisme.gouv.fr/
- **Standard CNIG PLU** : http://cnig.gouv.fr/
- **Géoplateforme IGN (téléchargements)** : https://data.geopf.fr/
- **DuckDB Spatial** : https://duckdb.org/docs/extensions/spatial
