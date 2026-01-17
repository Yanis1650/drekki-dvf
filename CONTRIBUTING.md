# Contributing to Foncier-Express

Merci de votre intérêt pour le projet ! Voici quelques directives pour contribuer.

## Flux de travail (Workflow)

1. Forkez le projet.
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`).
3. Commitez vos changements (`git commit -m 'Add some AmazingFeature'`).
4. Pushez votre branche (`git push origin feature/AmazingFeature`).
5. Ouvrez une Pull Request.

## Normes de Code

- **Backend**: Nous utilisons `ruff` pour le linting. Assurez-vous de lancer `ruff check .` avant de commiter.
- **Frontend**: Suivez les conventions Vue.js et assurez-vous que le projet build correctement (`npm run build`).

## Tests

Toute nouvelle fonctionnalité doit être accompagnée de tests unitaires ou d'intégration.
```bash
pytest
```
