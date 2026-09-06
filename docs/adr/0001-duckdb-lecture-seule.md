# 0001 — DuckDB en lecture seule plutôt qu'une base transactionnelle

**Statut :** acceptée · **Date :** 2026-02

## Contexte

L'application interroge des données publiques figées entre deux publications :
mutations DVF, parcelles cadastrales, attributs BDNB, zonage PLU. Elle n'écrit
rien. Il n'y a ni compte, ni panier, ni dossier stocké côté serveur — les
dossiers de décision vivent dans le `localStorage` du navigateur.

Les requêtes réelles sont analytiques : agrégats par commune ou par année,
recherche par rayon, jointures sur plusieurs millions de lignes parcellaires.
Aucune ne met à jour une ligne.

La première version reposait sur PostgreSQL + PostGIS, avec la gestion de
comptes et de crédits que cela suppose.

## Décision

Servir un fichier **DuckDB ouvert en lecture seule**, construit hors ligne par
le pipeline. Aucune base transactionnelle, aucun serveur de base de données à
administrer, aucune migration à jouer en production.

## Conséquences

- Le déploiement se réduit à deux conteneurs : l'API et nginx. Il n'y a pas de
  volume de données à sauvegarder — la base se reconstruit depuis le pipeline.
- Les agrégats sont rapides sans travail d'indexation : le stockage en colonnes
  et le moteur vectorisé sont faits pour ces requêtes.
- Publier une nouvelle donnée est un remplacement de fichier, pas une migration.
  C'est précisément ce que rend sûr [ADR-0004](0004-releases-dvf-immuables.md).
- **Le coût :** aucune écriture n'est possible à chaud. Toute évolution du
  schéma passe par une reconstruction. Et un fichier ouvert en lecture seule est
  partagé entre les threads du serveur — ce partage doit être explicite, ce qui
  a demandé un registre de connexions par fichier plutôt qu'une connexion par
  requête (`app/infrastructure/duckdb_pool.py`).

## Alternatives écartées

**PostgreSQL + PostGIS.** Le bon choix si l'application écrivait. Elle n'écrit
pas : on aurait payé l'administration, la sauvegarde et la latence réseau d'un
serveur transactionnel pour une charge exclusivement analytique.

**Parquet + DuckDB en mémoire à chaque requête.** Écarté pour la latence de
lecture des fichiers à froid, et parce que l'extension spatiale et les index
n'auraient pas survécu d'une requête à l'autre.

**SQLite + SpatiaLite.** Adapté à la lecture seule, mais orienté lignes : les
agrégats sur plusieurs millions de parcelles y sont d'un ordre de grandeur plus
lents.
