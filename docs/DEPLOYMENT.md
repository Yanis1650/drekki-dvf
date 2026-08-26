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
   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
   │  Frontend    │        │  Backend     │        │  PostGIS     │
   │  (Nginx)     │        │  (uvicorn)   │───────▶│  (PostgreSQL)│
   │  ~128 MB     │        │  ~4 GB max   │        │  ~1 GB max   │
   └──────────────┘        └──────┬───────┘        └──────────────┘
                                  │
                                  │ DuckDB (fichier)
                                  ▼
                          ┌──────────────┐
                          │  /app/data/  │
                          │  dept35.duckdb (par département)
                          └──────────────┘
```

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

**Variables obligatoires en production :**

```env
POSTGIS_PASSWORD=<mot_de_passe_fort>
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

#### Option A : Build local + transfert (recommandé si vous avez déjà `foncier.duckdb`)

1. **En local** (avec `foncier.duckdb` déjà présent dans `data/`) :

```powershell
cd C:\Users\yanis\Desktop\emancipation\foncier-express
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
| PostGIS | 1 GB | ~500 MB (schema) |
| Backend | 4 GB | - |
| Frontend | 128 MB | ~50 MB (image) |
| DuckDB (données) | - | 1-3 GB / département |
| **Total** | ~5-6 GB | 5-35 GB selon données |

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

**Le backend ne démarre pas :** Vérifier que PostGIS est healthy et que `POSTGIS_PASSWORD` est défini.

**Pas de données sur la carte :** La base DuckDB est vide. Lancer l'ETL pour au moins un département.

**Out of memory :** Réduire à 1 worker dans `Dockerfile.backend` (`--workers 1`).
