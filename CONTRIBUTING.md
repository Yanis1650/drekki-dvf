# Contribuer à Foncier-Express

Merci pour votre intérêt ! Toute contribution est bienvenue : code, documentation, signalement de bugs, idées de fonctionnalités.

## Code de conduite

En participant, vous acceptez le [Code de conduite](CODE_OF_CONDUCT.md).

## Démarrage rapide

1. **Fork** le dépôt et clonez votre fork
2. Créez une branche : `git checkout -b feature/ma-fonctionnalite` (ou `fix/bug-xyz`)
3. Installez les dépendances :

```bash
pip install -e ".[dev]"
cd frontend && npm ci
```

4. Copiez les fichiers d'environnement :

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

5. Vérifiez que les tests passent : `pytest`

## Workflow Git

1. Commitez vos changements avec des messages clairs (voir format ci-dessous)
2. Pushez votre branche : `git push origin feature/ma-fonctionnalite`
3. Ouvrez une **Pull Request** vers `main`

Les statuts GitHub Actions doivent être verts avant revue : tests et Ruff du
backend, charte et build du frontend, builds Docker et revue des dépendances.
La configuration et les contrôles exécutés sont détaillés dans
[`docs/GITHUB_AUTOMATION.md`](docs/GITHUB_AUTOMATION.md).

### Format des commits

```
type(scope): description courte

Explication détaillée si nécessaire.

Fixes #123
```

**Types** : `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

**Exemples** :

```
feat(api): ajouter endpoint filiation par commune
fix(map): corriger le zoom sur parcelles multi-polygones
docs(readme): ajouter section pipeline ETL
```

## Normes de code

### Backend (Python)

- **Linting** : `ruff check .`
- **Typage** : MyPy en mode strict
- **Limite** : 200 lignes max par fichier (refactoriser si dépassement)
- **Architecture** : Clean Architecture — flux `Endpoints → Services → Repositories`
- **Tests** : TDD recommandé, couverture obligatoire pour services et repositories

### Frontend (Vue.js)

- Composition API avec `<script setup>`
- Composables pour la logique réutilisable
- Vérifier que le build passe : `npm run build`

## Tests

```bash
# Lancer tous les tests
pytest

# Lancer avec couverture
pytest --cov=app

# Linting
ruff check .
```

Toute nouvelle fonctionnalité doit être accompagnée de tests unitaires ou d'intégration.

## Données et environnement

- Ne jamais committer de secrets, mots de passe ou clés API
- Utiliser `.env` pour la configuration locale (voir `.env.example`)
- Les données DVF et cadastre sont des open data ; le pipeline ETL est dans `data-pipeline/`
- Ne pas committer de fichiers de données (`.duckdb`, `.parquet`, `.csv`)

## Review de PR

Les mainteneurs examineront votre PR avec les critères suivants :

- [ ] Les tests passent (`pytest`)
- [ ] Le linting passe (`ruff check .`)
- [ ] Pas de secrets ou données personnelles
- [ ] Le code suit l'architecture existante
- [ ] La documentation est à jour si nécessaire

## Questions ?

Ouvrez une [issue](../../issues) ou une [discussion](../../discussions).
