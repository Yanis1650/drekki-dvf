# Refonte frontend — septembre 2026

## Audit de départ

- `App.vue` chargeait 200 mutations enrichies dans un rayon de 500 m ; `useMapContainer` remplaçait ensuite la source cartographique par `/land/geojson` à chaque déplacement. Les KPI ne représentaient donc pas les points affichés.
- Marché interrogeait `/analytics/trends` sur 5 km et dix ans, indépendamment du jeu de mutations du secteur. Son prix moyen incluait les aberrantes, contrairement au pied de carte. Le graphique étiquetait une moyenne comme une médiane.
- Le filtre « Fort ZAN » supposait `enrichment.zan_category`, absent du contrat de recherche. Les scores de proximité OSM ne sont pas des scores de densification.
- Le contrat renvoie `parcelles[]`, pas `id_parcelle`. Les points de recherche ne permettaient pas d’ouvrir une fiche.
- Les erreurs conservaient parfois les anciennes données ; aucune protection contre les réponses arrivant dans le désordre. Plusieurs absences étaient converties en zéro, notamment la confiance et les coefficients de densification.
- La fiche cumulait deux boutons de fermeture, une image satellite décorative et une estimation financière par simple multiplication surface × prix/m². Aucune suite de tests frontend n’était configurée.

## Contrats FastAPI examinés

Les chemins suivants sont relatifs à `/api/v1`.

- `GET /land/search/enriched` : `lat`, `lon`, `radius` (100–50 000 m), dates facultatives et `limit` (maximum 1 000). Réponse : `mutations[]` avec `mutation` et `enrichment` nullable, `enrichment_available`. Montants sérialisés en décimaux, `parcelles[]`, `is_outlier`. Aucun total non plafonné, curseur de pagination, millésime de publication ou rapport qualité d’ingestion.
- `GET /land/geojson` : mutations selon une emprise rectangulaire. Plus utilisé par le frontend pour éviter une seconde source de vérité DVF.
- `GET /land/parcelles` : fond de contexte cadastral et enrichissements selon l’emprise visible. Ce fond historique reste indépendant du filtre temporel des mutations ; sa portée est nommée dans l’interface et la légende.
- `GET /analytics/trends` : agrégat géographique indépendant. Remplacé dans Marché par une agrégation du jeu chargé ; l’écran ne prétend plus montrer dix années complètes.
- `GET /land/departements` : inventaire de fichiers départementaux. Ne suffit pas à certifier une couverture DVF complète ; pas utilisé comme indicateur de qualité.
- `GET /land/communes/{code}/densification/top` : classement communal, jusqu’à 100 parcelles, sans filtre de rayon ou de période. Le composant en demande 10 et explique son périmètre distinct.
- Fiche, historique, filiation et rapports : contrats existants conservés. La fiche indique que son historique complet est indépendant de la période du secteur.
- Erreurs structurées `503 data_unavailable` et `503 spatial_unavailable` : états visibles et action de reprise, distincts d’une recherche vide et d’une erreur réseau.

## Comportement livré

Le périmètre d’étude reste centré sur l’adresse sélectionnée. Rayon 500 m, 1 km ou 5 km ; toutes les dates disponibles ou deux dernières années. Le déplacement de la carte explore le contexte sans changer silencieusement l’étude. Un cercle matérialise ce périmètre.

`useStudyArea` possède le chargement, l’état de disponibilité et le jeu DVF. La carte reçoit ses mutations en props et ne les recharge plus. Le même composant KPI et le même module de calcul servent Carte et Marché. Les courbes annuelles sont calculées sur ce jeu, avec les mêmes exclusions des prix aberrants et manquants. Une mutation ne compte qu’une fois ; la table permet d’ouvrir chacune de ses parcelles.

Le bandeau qualité expose la période réellement observée, le nombre de prix exploitables, les aberrantes signalées, les positions manquantes et le plafond de résultats. Il indique explicitement les métadonnées non fournies. Un petit échantillon est signalé et les prix agrégés ont un effectif et un intervalle interquartile. Une absence de prix n’est jamais convertie en prix nul.

Les opportunités sont des résultats communaux modélisés, séparés des KPI DVF. La sélection ouvre la fiche ; les scores absents y sont signalés et les anciennes valeurs de remplacement ont été retirées. Le panneau est utilisable sur mobile, reçoit le focus et se ferme avec Échap. La recherche d’adresse fonctionne au clavier et ignore les réponses obsolètes.

## Organisation

- `src/domain/market.js` : adaptation du contrat, calculs, formatage et messages d’erreur.
- `src/domain/studyGeometry.js` : cercle géographique du périmètre.
- `src/composables/useStudyArea.js` : orchestration de la recherche, annulation et protection contre les réponses obsolètes.
- `StudyStatus`, `MapFooterKpi`, `MapLegend`, `DensificationOpportunities` : composants de présentation dédiés.
- Les services FastAPI et les traitements ETL n’ont pas été modifiés.

## Vérification

`npm test` : 16 tests, dont calculs, adaptation API, concurrence, reprise après erreur et rendu des vrais composants Vue. La CI exécute cette suite avant le contrôle de charte et la compilation. Aucune dépendance de test supplémentaire : runner Node et compilateur/renderer fournis par Vue.

Vérifications navigateur locales avec fixtures fictives : mêmes 12 mutations et prix moyen 3 150 €/m² sur Carte et Marché ; filtre deux ans → 4 mutations et 3 250 €/m² ; ouverture d’une opportunité et fiche sans confiance/densification ; état réseau indisponible sans anciens KPI ; affichage desktop et mobile 390 × 844.

La compilation et le contrôle de charte sont requis avant livraison. L’environnement local utilise Node 22 ; la CI reste sur Node 20 selon le contrat du projet. Les gros paquets MapLibre/ApexCharts produisent encore des avertissements de taille de bundle.

## Limites conservées et suites possibles

Les résultats sont un échantillon plafonné, pas une statistique exhaustive du territoire. La provenance détaillée de l’ingestion et la couverture réelle nécessitent de nouveaux contrats backend. Le champ d’aberrance peut être faux par défaut dans certaines bases anciennes : « non signalé » ne signifie donc pas « certifié ». Les enrichissements parcellaires ne sont pas filtrés par la période DVF.

Les tests navigateur utilisent un serveur de fixtures isolé ; ils ne valident ni les données de production ni la disponibilité du VPS. Aucun déploiement ni modification du VPS.

La proposition visuelle `design/frontend-concept.png` est une maquette conceptuelle avec données fictives. Elle guide l’organisation et la palette ; elle n’est pas une capture du frontend livré et ses libellés ou chiffres ne constituent pas un contrat de données.
