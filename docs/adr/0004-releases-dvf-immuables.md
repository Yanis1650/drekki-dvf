# 0004 — Une release DVF est immuable et franchit une porte qualité

**Statut :** acceptée · **Date :** 2026-08

## Contexte

Les DVF géolocalisées sont republiées environ deux fois par an, et une
publication peut **corriger un millésime antérieur** : on ne peut pas supposer
que seule l'année courante bouge.

Le pipeline d'origine écrasait la base servie. Trois problèmes en découlaient :

- impossible de savoir de quelle publication venait un chiffre affiché ;
- impossible de revenir en arrière si une publication arrivait tronquée ;
- une régression silencieuse — la moitié des mutations disparaissant à cause
  d'un changement de format amont — ne se voyait qu'à l'écran, après coup.

## Décision

Séparer trois états, et n'en rendre qu'un servable.

1. **Brut versionné.** Chaque ressource téléchargée est archivée sans écrasement
   sous `data/raw/`, avec un manifeste qui note URL, SHA-256, taille, millésime
   et statut.
2. **Candidate.** La transformation écrit `data/candidates/foncier-<release>.duckdb`,
   qui ne remplace jamais la base servie. Neuf contrôles bloquants produisent un
   rapport JSON versionné — **écrit même en cas d'échec**, parce qu'un échec est
   précisément ce qu'on a besoin de lire.
3. **Release.** La promotion n'est possible que si les contrôles passent et si le
   hash de la candidate correspond à celui du rapport. Elle copie de façon
   atomique vers `data/releases/`, refuse d'écraser une release existante dont le
   contenu diffère, et met à jour le pointeur `current.json`.

Un des neuf contrôles compare le volume à la dernière release approuvée : une
candidate qui perd plus de 25 % des mutations est refusée. La baseline est
retrouvée seule via `current.json` — l'opérateur n'a pas à recopier un nom de
rapport à la main.

## Conséquences

- Tout chiffre servi remonte à une publication identifiée et à un fichier dont
  le hash est connu.
- Un retour arrière est une écriture de pointeur, pas une reconstruction.
- Une régression amont est bloquée avant d'atteindre l'écran, et laisse une
  trace exploitable.
- **Le coût :** trois copies du même jeu de données sur le disque du runner, et
  une promotion qui reste un geste humain explicite (`--promote`). C'est
  volontaire : publier une donnée foncière n'est pas une opération à automatiser
  jusqu'au bout.
- La première publication n'a pas de baseline : le contrôle de régression est
  alors ignoré, non pas échoué.

## Alternatives écartées

**Écraser la base servie après les contrôles.** Supprime le coût disque, mais
rend le retour arrière impossible et fait disparaître la traçabilité, qui est
l'essentiel de la valeur.

**Promotion automatique dès que les contrôles passent.** Neuf contrôles ne
couvrent pas tout ce qu'une publication peut casser. Le geste manuel est le
dernier filet.

**Versionner les bases dans Git (LFS).** Des fichiers de plusieurs gigaoctets,
reconstructibles depuis une source publique, n'ont rien à faire dans un dépôt de
code.
