# Déploiement Foncier-Express sur VPS

Guide pour déployer sur un VPS avec **35 Go disque** et **11 Go RAM**.

## Architecture déployée

```
                    ┌─────────────────────────────────┐
                    │  Nginx (port 80)                │
                    │  - / → frontend (Vue SPA)       │
                    │  - /api/ → backend (FastAPI)    │
                    └──────────────┬──────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
   ┌──────────────┐                        ┌──────────────┐
   │  Frontend    │                        │  Backend     │
   │  (Nginx)     │                        │  (uvicorn)   │
   │  ~128 MB     │                        │  ~4 GB max   │
   └──────────────┘                        └──────┬───────┘
                                                  │
                                                  │ DuckDB (fichier, lecture seule)
                                                  ▼
                                          ┌──────────────┐
                                          │  /app/data/  │
                                          │  dept35.duckdb (par département)
                                          └──────────────┘
```

Deux conteneurs, aucune base de données à administrer : l'application est libre
et sans compte, il n'y a donc aucune donnée transactionnelle à stocker.

## Prérequis sur le VPS

- **OS** : Ubuntu 22.04 LTS (recommandé)
- **Docker** 24+ et **Docker Compose** v2
- **Domaine** pointant vers l'IP du VPS (optionnel mais recommandé pour HTTPS)

## Étapes de déploiement

### 1. Installer Docker sur le VPS

```bash
# Ubuntu 22.04
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Déconnexion/reconnexion requise
```

### 2. Cloner le projet

```bash
git clone https://github.com/<votre-org>/foncier-express.git
cd foncier-express
```

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
nano .env
```

**Aucun secret n'est requis** : l'application ne gère ni comptes ni paiements.

La seule variable qu'il est recommandé de renseigner en production restreint les
origines autorisées :

```env
# Domaines autorisés à appeler l'API (défaut : "*")
CORS_ALLOW_ORIGINS=https://foncier.votredomaine.fr
```

**Données DuckDB** : Le dossier `./data/` est monté dans le backend. Soit :
- vous transférez un `dept35.duckdb` construit en local (voir section ci-dessous) ;
- soit vous lancez l'ETL après le déploiement sur le VPS.

### 4. Lancer les conteneurs

```bash
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

Vérifier les logs :

```bash
docker compose -f docker-compose.prod.yml logs -f
```

### 5. Données DuckDB — Deux options

#### Option A : Build local + transfert (recommandé)

1. **En local**, depuis la racine du dépôt :

```powershell
.\.venv\Scripts\Activate.ps1
python data-pipeline/etl_build_dept.py 35
```

> **Note** : Exécuter chaque commande sur une ligne séparée (ne pas tout coller en une fois).

→ Crée `data/dept35.duckdb` (~1-2 GB).

2. **Transférer vers le VPS** :

```powershell
# Créer le dossier data sur le VPS
ssh user@TON_IP_VPS "mkdir -p foncier-express/data"

# Envoyer le fichier (remplacer user et TON_IP_VPS)
scp data\dept35.duckdb user@TON_IP_VPS:foncier-express/data/
```

3. **Sur le VPS** : les conteneurs utilisent déjà `./data/`. Redémarrer le backend si besoin :

```bash
cd foncier-express
docker compose -f docker-compose.prod.yml restart backend
```

#### Option B : ETL directement sur le VPS

La base DuckDB est vide au démarrage. Pour charger les données sur le VPS :

```bash
# Nécessite que foncier.duckdb existe sur le VPS (ou les données sources)
docker exec -it foncier-backend python data-pipeline/etl_build_dept.py 35
```

**Estimation disque par département :**

| Département | Données brutes | DuckDB après ETL |
|-------------|----------------|------------------|
| 35 (Ille-et-Vilaine) | ~500 MB | ~1-2 GB |
| 75 (Paris) | ~200 MB | ~500 MB |
| France entière | ~15 GB | ~25-35 GB |

Pour rester sous 35 Go : **max 5-10 départements** selon la densité.

### 6. HTTPS avec Let's Encrypt (recommandé)

Si vous avez un domaine (ex: `foncier.votredomaine.fr`) :

```bash
# Installer certbot
sudo apt install certbot

# Obtenir un certificat (standalone ou webroot)
sudo certbot certonly --standalone -d foncier.votredomaine.fr
```

Ensuite, ajouter un reverse proxy (nginx ou Caddy) devant le conteneur frontend, ou intégrer le certificat dans la config nginx. Exemple minimal avec Caddy :

```bash
# Caddyfile
foncier.votredomaine.fr {
    reverse_proxy localhost:80
}
```

## Ressources et limites

| Service | RAM max | Disque estimé |
|---------|---------|---------------|
| Backend | 4 GB | - |
| Frontend | 128 MB | ~50 MB (image) |
| DuckDB (données) | - | 1-3 GB / département |
| **Total** | ~4-5 GB | 5-35 GB selon données |

## Commandes utiles

```bash
# Arrêter
docker compose -f docker-compose.prod.yml down

# Redémarrer un service
docker compose -f docker-compose.prod.yml restart backend

# Voir l'utilisation disque
docker system df
df -h

# Logs
docker compose -f docker-compose.prod.yml logs -f backend
```

## Dépannage

**Le backend ne démarre pas :** vérifier que `DUCKDB_PATH` pointe vers un fichier
présent dans le volume monté (`./data`). Attention : `foncier.duckdb` (France
entière, ~69 Go) ne tient pas sur un VPS de 35 Go — déployer une base par
département (`dept35.duckdb`, ~1,5 Go).

**Pas de données sur la carte :** la base DuckDB est vide. Lancer l'ETL pour au
moins un département.

**Une section reste vide (filiation, environnement) :** c'est voulu. Le jeu de
données correspondant n'a pas été construit, et l'API répond `503
data_unavailable` plutôt que d'inventer une valeur. Lancer l'étape ETL manquante
(`etl_dfi.py` pour la filiation, `etl_poi.py` pour l'environnement).

**Extension spatiale indisponible :** l'API répond `503 spatial_unavailable` sur
les routes géographiques et reste opérationnelle sur le reste. DuckDB télécharge
`spatial` au premier lancement : vérifier l'accès réseau sortant du conteneur.
Sous Windows, une stratégie de contrôle d'application (Smart App Control / WDAC)
peut bloquer le chargement du binaire — travailler alors dans Docker ou WSL2.

**Out of memory :** Réduire à 1 worker dans `Dockerfile.backend` (`--workers 1`).
