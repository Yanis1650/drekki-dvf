# Méthodologie DVF

Ce document décrit le contrat de données appliqué par Foncier-Express. Il
complète les métadonnées de chaque ingestion et permet d'interpréter les prix
et les indicateurs sans leur attribuer une précision qu'ils n'ont pas.

## Périmètre

La méthode de référence est `mericskay_2021`, formalisée dans
`app/domain/dvf_methodology.py`. Elle traite les ventes DVF géolocalisées,
pas une estimation notariale ni une expertise immobilière individuelle.

- nature de mutation : `Vente` ;
- valeur foncière strictement supérieure à 1 000 € ;
- surface habitable totale strictement supérieure à 9 m² ;
- prix au m² calculé sur les locaux `Maison` et `Appartement`.

Une mutation DVF peut comporter plusieurs lignes. Les lignes sont regroupées
par `id_mutation` avant le calcul du prix au m² afin de ne pas compter une
même vente plusieurs fois.

## Provenance et publication

Chaque ingestion conserve les URL, dates de mise à jour, hashes SHA-256,
tailles et millésimes publiés par data.gouv.fr. Le pipeline produit d'abord
une candidate DuckDB et son rapport JSON de qualité. Une candidate validée
peut ensuite devenir une release immuable avec son manifeste et un pointeur
`current.json`.

La release DVF seule n'est pas encore la base départementale complète servie
par l'API : le cadastre, la BDNB, le PLU, la densification et la filiation
doivent y avoir été intégrés. La promotion applicative ne doit donc intervenir
qu'après les contrôles de cette base finale.

## Contrôles et rapport de qualité

Le rapport JSON bloque la promotion si la candidate est absente, illisible,
sans table `mutations_aggregated`, sans colonne canonique, vide, dupliquée ou
invalide sur les champs, dates, valeurs, surfaces, parcelles liées, coordonnées
ou prix au m². Les coordonnées sont aussi contrôlées dans leurs bornes
géographiques universelles.

Le rapport `schema_version: 2` rend également visibles, sans les confondre avec
des règles métier bloquantes, le volume par année et commune, les taux de
géolocalisation et de liaison aux parcelles ainsi que la médiane des prix au m²
par type de local. Ces métriques permettent d'interpréter une release avant de
la servir.

À partir de la deuxième release, le pipeline lit automatiquement le rapport JSON
immuable pointé par `data/releases/current.json` (ou un rapport fourni avec
`--baseline-quality-report`). La candidate est alors bloquée si son volume passe
sous 75 % de cette référence validée. Ce seuil est volontairement explicite et
conservateur : une baisse peut être légitime après correction de source, mais
elle doit être assumée et documentée au lieu d'être publiée silencieusement.

La base départementale finale a son propre contrat : une sonde de disponibilité
vérifie la présence de `mutations_aggregated`, `france_foncier_test`,
`parcelles`, `densification_scores` et `confidence_scores`. Les données
optionnelles (filiation, POI, risques) restent signalées séparément par l'API
plutôt que d'empêcher la carte et le marché de fonctionner.

## Contrat de score de confiance

Les nouvelles bases départementales stockent la composante de confiance liée à
la densification sous le nom canonique `score_densification`. Les bases déjà
déployées avec l'ancien nom interne `score_zan` restent compatibles en lecture
via l'API le temps de leur renouvellement. Cela évite une migration forcée sur
le VPS tout en supprimant l'ambiguïté des prochains builds.

## Valeurs extrêmes

Les bases départementales conservent un indicateur `is_outlier` : aucune vente
n'est supprimée. Les bornes actuelles sont P5/P95 par commune et année pour
un échantillon d'au moins dix ventes, puis par département et année en repli.

Ce signal décrit une valeur extrême au sein de son groupe ; il ne prouve pas
une erreur. La prochaine itération devra le stratifier par type de local et
compléter l'indicateur par sa borne, sa méthode et son niveau d'échantillon.

## Limites d'interprétation

Les transactions complexes, ventes en bloc, dépendances et parcelles
multiple peuvent rendre un prix au m² moins représentatif. Les prix affichés
servent donc à contextualiser un marché local, jamais à produire une valeur
d'expertise automatique. L'utilisateur doit toujours consulter le nombre de
transactions, la période couverte et le niveau de confiance associé.
