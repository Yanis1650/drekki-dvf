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
                          │  foncier.duckdb
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

**Données DuckDB** : Le volume `foncier_data` contient la base DuckDB. Soit :
- vous avez déjà une base pré-construite à monter ;
- soit vous lancez l'ETL après le déploiement (voir ci-dessous).

### 4. Lancer les conteneurs

```bash
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

Vérifier les logs :

```bash
docker compose -f docker-compose.prod.yml logs -f
```

### 5. Construire les données DVF (ETL)

La base DuckDB est vide au démarrage. Pour charger les données :

```bash
# Entrer dans le conteneur backend
docker exec -it foncier-backend bash

# Exemple : un département (Ille-et-Vilaine = 35) ~1-2 GB
python data-pipeline/etl_build_dept.py 35

# Ou plusieurs départements (attention à la place disque)
# Chaque département ≈ 1-3 GB
exit
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
