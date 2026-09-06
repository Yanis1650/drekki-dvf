# 0006 — Vérifier le rendu, pas seulement le build

**Statut :** acceptée · **Date :** 2026-09

## Contexte

La suite frontend compte 36 tests. Ils portent tous sur la logique de domaine :
calculs de marché, adaptation du contrat API, concurrence des requêtes, rendu
SSR de quelques composants isolés. **Aucun ne monte MapLibre, aucun ne monte
ApexCharts, aucun ne fait naviguer le routeur.**

Une régression réelle a traversé ce trou. Dependabot a proposé MapLibre 6 ; le
build échouait, l'export par défaut ayant disparu en v6. Le correctif tenait en
trois lignes — passer aux imports nommés — et tout redevenait vert : build,
36 tests, vérificateur de charte, et pas une erreur de console.

La carte se chargeait pourtant **vide**. Ni semis de mutations, ni cercle de
périmètre. Le fond IGN seul. Silencieusement.

Sur la même vue, mesurée sur la build de production chargée dans Chromium :

| | pixels ocre (donnée) | pixels bleus (interface) |
|---|---:|---:|
| MapLibre 5 | 1,752 % | 0,232 % |
| MapLibre 6 | 0,041 % | 0,039 % |

Aucun outil du dépôt ne voyait la différence. Un projet qui refuse d'inventer
une donnée ne peut pas se permettre d'en perdre l'affichage sans le savoir.

## Décision

Ajouter un test qui **charge la build de production dans un navigateur** et
mesure ce qui est réellement peint.

`frontend/tests/rendu/rendu.test.js` construit l'application contre le serveur
de fixtures, la sert, l'ouvre dans Chromium, puis :

- vérifie que le canvas MapLibre est monté et dimensionné ;
- compte les pixels aux couleurs de la charte à l'intérieur du canvas — ocre
  pour la donnée, bleu pour le périmètre ;
- exerce la navigation **par clic** vers Marché et Dossiers, puis le retour à la
  carte, et revérifie qu'elle rend encore ;
- compte les séries des graphiques et les valeurs écrites sur les points, que la
  charte exige ;
- échoue sur toute erreur de console.

Les seuils sont calés entre deux mesures réelles sur ces fixtures : 0,455 %
d'ocre quand la carte rend, 0,060 % quand elle est vide. Le seuil est à 0,25 %,
soit un facteur deux de marge de chaque côté.

Le test vit hors de `npm test`, sous `npm run test:rendu`. La suite unitaire
reste rapide et sans dépendance ; celle-ci demande un navigateur.

## Conséquences

- La régression qui a motivé cette décision est reproduite et attrapée : avec
  MapLibre 6, le test échoue sur `mutations non peintes : 0.060 % d'ocre`.
- Les montées de MapLibre, ApexCharts et vue-router sont désormais vérifiables
  avant merge, ce qu'aucun contrôle ne permettait.
- La CI installe un Chromium (~115 Mo) et exécute un build supplémentaire.
- **Le coût :** un test qui mesure des pixels est sensible au rendu logiciel du
  runner. Il compte des proportions, jamais une image de référence, et garde une
  marge d'un facteur deux — mais il restera plus fragile qu'une assertion sur du
  texte. C'est le prix pour vérifier la seule chose que rien d'autre ne voit.
- La mesure passe par une capture réinjectée dans un canvas 2D : le canvas de
  MapLibre est un contexte WebGL sans `preserveDrawingBuffer`, dont
  `getImageData` ne rend rien d'exploitable.

## Alternatives écartées

**Comparaison d'images de référence.** Le rendu d'une carte dépend des tuiles
servies, des polices et du pilote graphique du runner : la référence casserait à
chaque exécution pour de mauvaises raisons.

**Monter les composants avec un DOM simulé.** `jsdom` n'a pas de WebGL. On
testerait que le composant appelle MapLibre, ce qu'il faisait déjà correctement
en v6 — c'est exactement le défaut qui est passé.

**S'en remettre à une vérification manuelle avant chaque montée.** C'est ce qui
existait. Elle a été faite une fois, parce qu'un doute est né ; elle ne l'aurait
pas été à la dixième dépendance.
