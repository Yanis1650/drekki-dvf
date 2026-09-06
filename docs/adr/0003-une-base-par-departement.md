# 0003 — Une base par département plutôt qu'une base France entière

**Statut :** acceptée · **Date :** 2026-02

## Contexte

Le parcellaire français représente une centaine de millions de parcelles. Pour
le seul département 35, la base construite pèse 1,5 Go et contient 2,4 millions
de parcelles et 1,3 million de scores de densification.

Une base nationale unique aurait dépassé la mémoire du VPS de déploiement, et
imposé de reconstruire l'ensemble pour corriger une seule source départementale
— le zonage PLU, notamment, est publié commune par commune.

## Décision

Construire **une base DuckDB autonome par département**, nommée
`data/dept{XX}.duckdb`, et router la requête vers la bonne base à partir des
deux premiers caractères de l'identifiant de parcelle ou du code commune.

`DuckDBPool` tient les connexions ouvertes avec éviction LRU (dix par défaut).
Le routage gère la Corse (`2A`, `2B`) et l'outre-mer (`97X`), dont les codes ne
tiennent pas sur deux caractères.

Un mode « base unique » reste disponible (`MULTI_DEPT=false`) : c'est celui de
la démonstration en production, qui ne sert qu'un département.

## Conséquences

- Ajouter un département est un fichier de plus, sans reconstruction du reste.
- La mémoire du serveur borne le nombre de départements *simultanément
  consultés*, pas le nombre de départements *disponibles*.
- **Le coût :** toute requête réellement nationale devient impossible sans
  agrégation préalable. Les tendances de marché inter-départementales retombent
  sur la base « legacy » quand elle existe, sinon elles ne sont pas servies.
- Deux chemins de connexion coexistent — le pool et le registre partagé du mode
  base unique — qui doivent avoir la même durée de vie. C'est ce que verrouille
  `tests/test_lifecycle.py`.

## Alternatives écartées

**Une base France entière.** Ne tient pas sur la cible de déploiement, et fait
d'une correction locale une reconstruction globale.

**Un schéma par département dans une base unique.** DuckDB ne permet pas
d'ouvrir un schéma sans ouvrir le fichier : on aurait payé la taille totale à
chaque requête.

**Partitionnement par fichiers Parquet lus à la demande.** Séduisant pour le
stockage, mais l'extension spatiale et les jointures parcellaires exigent un
fichier de base persistant.
