# 0007 — La limite de 200 lignes est outillée, avec un cliquet

**Statut :** acceptée · **Date :** 2026-09

## Contexte

La limite de 200 lignes par fichier était annoncée trois fois — `CONTRIBUTING.md`
et deux fois dans `ARCHITECTURE.md` — comme obligatoire, refactoring imposé
au-delà. Aucun outil ne la vérifiait.

Mesure au moment de la décision : **32 fichiers au-dessus, 3 516 lignes en trop**,
jusqu'à 467 lignes pour un seul fichier. La règle la plus visible du dépôt était
sa moins tenue.

C'est le même mécanisme que celui qui avait laissé fondre la charte graphique
(voir [ADR-0005](0005-charte-verifiee-par-script.md)) : une convention qui ne
casse rien quand on l'enfreint disparaît par accumulation, sans qu'aucun moment
précis puisse être désigné.

## Décision

Vérifier la règle en CI, avec deux régimes.

**Régime normal.** Tout fichier absent du registre est tenu à 200 lignes. Un
fichier neuf ne peut plus naître trop gros — c'est là que se joue l'essentiel,
puisque c'est ainsi que la dette s'était constituée.

**Régime de dette.** Les 32 fichiers déjà au-dessus portent un plafond
nominatif, égal à leur taille au jour de l'outillage, inscrit dans
`scripts/taille_registre.json`. Ce plafond **ne peut que descendre** :
`--maj` l'abaisse quand un fichier a maigri, jamais l'inverse. Une entrée
disparaît quand le fichier repasse sous la limite.

Le registre est une dette, pas une dispense. Il est chiffré à chaque exécution —
« 32 fichiers, 3 438 lignes à résorber » — précisément pour qu'on ne l'oublie pas.

Une première résorption accompagne la décision : `IFiliationRepository` a rejoint
les autres contrats de dépôt, qui forment désormais un paquet d'un module par
contrat. `filiation_repository.py` passe de 445 à 367 lignes.

## Conséquences

- La règle existe enfin au sens où le code peut la faire échouer.
- La dette est visible, chiffrée et décroissante par construction.
- Le découpage des contrats de dépôt suit celui, déjà en place, des mixins
  DuckDB : une responsabilité, un module. La cohérence était déjà là, elle est
  maintenant appliquée partout.
- **Le coût :** un compteur de lignes ne mesure pas la complexité. Un fichier de
  190 lignes illisible passe, un fichier de 210 lignes limpide échoue. La limite
  vaut comme signal, pas comme jugement — d'où les exemptions permanentes
  possibles, avec leur raison inscrite dans le script.
- Sept des fichiers en dette sont les scripts ETL que
  [PIPELINE.md](../PIPELINE.md) recense comme n'ayant plus aucune référence dans
  le dépôt. Les supprimer résorberait à lui seul une grande part de la dette,
  sans aucune refonte. Cette décision reste ouverte.

## Alternatives écartées

**Repartir à zéro et refondre les 32 fichiers.** Une refonte simultanée de
3 500 lignes, sur du code dont une partie n'a pas de test dédié, aurait fait plus
de dégâts que la dette elle-même. Le cliquet obtient le même résultat sans le
grand soir.

**Se contenter de corriger la documentation** en écrivant la règle réellement
suivie, c'est-à-dire aucune. C'était honnête mais renonçait à un principe qui a
de la valeur : les fichiers courts de ce dépôt — les mixins DuckDB, les étapes
d'ETL, les composants de la fiche — sont ceux qu'on relit le plus facilement.

**Un seuil plus généreux, 400 lignes par exemple**, que presque tout le code
respecterait déjà. Il aurait rendu la règle indolore, donc inutile : elle
n'aurait plus rien empêché.
