# 0002 — Une donnée absente est un `503`, jamais une valeur par défaut

**Statut :** acceptée · **Date :** 2026-02

## Contexte

Le pipeline est modulaire : selon les sources chargées pour un département,
certaines tables n'existent pas. Une base sans ETL POI n'a pas de points
d'intérêt ; une base sans DFI n'a pas de filiation cadastrale.

Le code d'origine absorbait ces cas dans un `except` générique qui renvoyait une
liste vide ou une valeur neutre. Trois conséquences observées :

- un score d'environnement non mesuré ressortait à `5/10`, indiscernable d'une
  mesure réelle ;
- une filiation absente devenait « parcelle originelle », c'est-à-dire une
  affirmation cadastrale fausse ;
- une indisponibilité temporaire de l'extension spatiale devenait un `500`
  « erreur serveur », impossible à distinguer d'un bug.

Le produit s'adresse à des décisions foncières. Une valeur inventée y coûte plus
cher qu'une absence annoncée.

## Décision

Distinguer trois situations, et ne jamais les confondre :

| Situation | Réponse |
|---|---|
| Le jeu de données n'est pas chargé | `503`, `error: "data_unavailable"`, nom du jeu |
| L'extension spatiale est indisponible | `503`, `error: "spatial_unavailable"` |
| Requête valide, aucun résultat | `200` avec une liste vide |

Les deux exceptions dérivent de `ResourceUnavailableError`, et **chaque endpoint
la ré-émet avant son `except Exception` générique**. Sans cette reprise, le
filet générique reconvertit l'indisponibilité en erreur serveur.

La règle se prolonge jusqu'à l'interface : une absence s'y écrit `NON RELEVÉ`,
se peint en hachures sur la carte, et n'est jamais remplacée par un zéro ni par
une moyenne de secteur.

## Conséquences

- Le contrat d'API porte l'information de disponibilité, ce qui permet à
  l'interface d'afficher l'état réel de chaque source plutôt qu'une supposition.
- Une base partiellement chargée reste utilisable : les requêtes tabulaires
  répondent même quand l'extension spatiale manque.
- **Le coût :** chaque endpoint doit écrire sa reprise explicite. C'est trois
  lignes répétées quatorze fois, avec le risque qu'un nouvel endpoint les
  oublie — d'où la couverture des endpoints HTTP dans `tests/test_api_endpoints.py`.

## Alternatives écartées

**Renvoyer `200` avec un champ `available: false`.** Plus simple à consommer,
mais un client distrait affiche quand même le corps de la réponse. Le code de
statut est ce qu'un client ne peut pas ignorer par accident.

**Valeurs neutres documentées.** C'était l'état initial. La documentation ne
suit pas la donnée jusqu'à l'écran : un `5/10` reste un `5/10` dans une capture
d'écran, dans un export, dans un rapport PDF.
