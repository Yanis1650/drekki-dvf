# Automatisation GitHub

Le dépôt ne dépend pas d'une validation locale : chaque Pull Request vers
`main` est contrôlée par GitHub Actions. Les workflows sont versionnés dans
`.github/` et s'exécutent avec le principe du moindre privilège
(`contents: read`).

## Contrôles automatisés

| Workflow | Déclencheur | Ce qu'il garantit |
|---|---|---|
| `CI` | Pull Request, push sur `main` ou branche Codex, déclenchement manuel | Ruff et pytest sur Python 3.11 ; charte, build et audit npm du frontend ; construction réelle des deux images Docker et validation Compose. |
| `Dependency review` | Pull Request vers `main` | Refuse l'introduction d'une dépendance à vulnérabilité élevée ou critique. |
| `DVF source check` | Chaque lundi à 05:23 UTC, ou manuel | Vérifie le contrat de métadonnées data.gouv et publie la release détectée dans le résumé du run, sans télécharger de données. |
| `DVF candidate release` | Manuel uniquement | Ingestion, ETL, contrôles qualité et promotion facultative d'une publication DVF sur un runner dédié. |

Dependabot crée aussi chaque semaine des Pull Requests pour les dépendances
Python, npm et les actions GitHub. Elles sont soumises aux mêmes contrôles que
les contributions humaines.

## Pipeline DVF de production

Une release nationale DVF est trop volumineuse pour un runner GitHub hébergé.
Le workflow `DVF candidate release` attend donc un runner Linux auto-hébergé
portant le label `dvf`, avec Python 3.11, au moins 80 Go libres et 16 Go de RAM.
Le runner est le seul endroit où les données brutes, candidates et bases
DuckDB sont créées ; elles sont ignorées par Git et ne sont jamais téléversées
comme artefact.

Le workflow archive pendant 90 jours uniquement les preuves légères : le
manifeste d'ingestion, le rapport JSON des neuf contrôles et le manifeste de
release. La promotion (`promote: true`) doit être protégée en créant
l'environnement GitHub `dvf-production` et en lui ajoutant un reviewer requis.
Une candidate qui échoue aux contrôles est conservée pour diagnostic mais ne
peut pas être promue par le script.

## Réglages GitHub à activer après le premier push

1. Dans **Settings → Actions**, autoriser les workflows du dépôt.
2. Dans **Settings → Branches**, créer une règle pour `main` exigeant les
   statuts `Backend · Python 3.11`, `Frontend · Node 20`,
   `Containers · production build` et `New vulnerable dependencies`.
3. Dans **Settings → Environments**, créer `dvf-production` avec un reviewer
   requis avant toute promotion DVF.
4. Dans **Security → Code Security**, activer la configuration CodeQL par
   défaut pour ajouter l'analyse statique gérée par GitHub, sans dupliquer une
   configuration générée dans le dépôt.

Les entrées manuelles (`workflow_dispatch`) deviennent disponibles dès que les
workflows sont présents sur la branche par défaut. Le premier push de cette
branche doit donc être fusionné ou faire l'objet d'une Pull Request vers
`main` avant d'essayer une release DVF.
