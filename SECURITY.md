# Politique de sécurité

## Versions supportées

| Version | Support          |
|---------|------------------|
| 0.1.x   | :white_check_mark: Actif |

## Signaler une vulnérabilité

Si vous découvrez une vulnérabilité de sécurité, **merci de ne pas ouvrir une issue publique**.

Signalez-la de préférence par l'un des moyens suivants :

- **GitHub Security Advisories** : utilisez l'onglet [Security](../../security) du dépôt, puis "Report a vulnerability"
- **Email** : contactez les mainteneurs directement (adresse dans le profil GitHub)

Les vulnérabilités seront évaluées et une réponse sera fournie sous 72 heures. Un correctif sera publié dès que possible.

## Bonnes pratiques pour les contributeurs

- Ne jamais committer de secrets, mots de passe ou clés API
- Utiliser les variables d'environnement via `.env` (voir `.env.example`)
- Valider et assainir toutes les entrées utilisateur
- Suivre les conventions du projet (voir [CONTRIBUTING.md](CONTRIBUTING.md))
- Ne pas désactiver les vérifications de sécurité dans le code

## Dépendances

Les dépendances sont gérées via `pyproject.toml` (backend) et `package.json` (frontend). Vérifiez régulièrement les vulnérabilités connues :

```bash
# Python
pip audit

# Node.js
npm audit
```
