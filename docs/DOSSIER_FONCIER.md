# Un parcours commun aux prospecteurs et aux particuliers

Le dossier suit trois étapes : comprendre les données disponibles, préparer les vérifications utiles, puis noter une décision personnelle. La priorité reste la qualification d’un foncier pour la prospection. Un particulier peut choisir « Préparer une visite » dans le même dossier, sans créer un profil ni changer d’application.

## Première version

- Le premier onglet de la fiche est désormais « Dossier ».
- Deux objectifs : « Étudier le potentiel » et « Préparer une visite ». Ils changent l’ordre et le contenu des questions pratiques, pas les données ni les faits.
- Les repères distinguent données renvoyées, calculs sur l’historique et potentiel modélisé. Chaque repère nomme sa source et ses limites de datation.
- Les questions portent sur les règles, l’accès et les limites, les ventes et la confrontation au terrain. Chacune explique pourquoi elle est proposée. Il s’agit de règles de lecture explicites, pas d’un moteur de conformité réglementaire ou de faisabilité.
- Une vérification ne peut être marquée « renseignée par moi » sans observation ou référence. Modifier l’observation réinitialise cette marque. Changer d’objectif réinitialise les marques tout en gardant les notes.
- Le suivi « À qualifier / À approfondir / Visite prévue / Écarté » est une décision personnelle ; aucun score ne décide automatiquement de poursuivre ou d’abandonner.
- « Mes dossiers » permet de retrouver les parcelles enregistrées et de filtrer le suivi. Les indicateurs techniques existants restent accessibles par dévoilement progressif.
- Le dossier peut être exporté en texte avec sources, inconnues et notes personnelles. Le rapport PDF technique existant est distinct et ne contient pas ces notes.

## Analyse multicritère et disposition — septembre 2026

La référence [Haven Score](https://app.haven-score.fr/) a été explorée sur Rennes : carte, synthèse, thèmes et sous-indicateurs. Foncier Express reprend le principe de lecture progressive avec sa propre palette crème, bleu fonctionnel et ocre pour les quantités. Sur ordinateur, l’inspecteur est une colonne distincte, redimensionnable ; sur mobile, la fiche occupe l’écran. La carte suit les changements de largeur. Les agrégats de mutations sont ocres et restent au-dessus du fond cadastral.

Le dossier inclut six thèmes : prix et marché, terrain et potentiel, règles et servitudes, accès et quotidien, risques et nuisances, bâti et travaux. Les repères disponibles sont issus de la fiche, de la densification et de l’historique DVF. Une éventuelle classe énergie est identifiée comme valeur agrégée à vérifier, pas comme diagnostic certifié et actuel.

**Cette version calcule une adéquation personnelle, pas un score automatique d’habitabilité.** L’utilisateur écrit une observation ou référence, puis attribue une note de 0 à 5 et une priorité de 0 à 3. Une note sans observation n’est pas prise en compte. Les priorités initiales dépendent de l’objectif. Changer d’objectif conserve les observations, mais réinitialise appréciations et points bloquants pour les réexaminer. Modifier une observation remet également son appréciation à vérifier.

Le résultat est une moyenne pondérée ramenée sur 100 seulement si tous les critères actifs sont évalués. Sinon, une fourchette simule les critères manquants de 0 à 5 ; ce n’est pas un intervalle statistique. Le cercle indique la couverture pondérée, avec le nombre de critères évalués en son centre. Aucun résultat n’est inventé en l’absence d’évaluation. Un point déclaré bloquant prévaut dans la synthèse, même si son poids est nul. Les thèmes absents restent explicitement non relevés. Risques, nuisances et services ne sont pas encore raccordés à des sources externes dans ce module.

L’enregistrement et l’export texte incluent les critères, poids, observations et points bloquants. Les anciens dossiers sont compatibles et commencent avec des critères non évalués. Les changements non enregistrés sont signalés ; changer d’onglet technique conserve le brouillon, fermer ou changer de parcelle nécessite de l’enregistrer. La liste de dossiers expose la couverture et les points bloquants sans classer des scores issus de priorités différentes.

## Persistance et limites

L’enregistrement est explicite et local au navigateur (`foncier-express:dossiers:v1`). Les notes ne sont pas envoyées à l’API et ne sont pas synchronisées entre appareils. Il faut enregistrer avant de fermer le dossier et exporter pour conserver une sauvegarde indépendante du navigateur. Une panne de stockage est affichée ; une sauvegarde corrompue ou d’un format non reconnu n’est pas écrasée.

Les données de parcelle sont rechargées à chaque ouverture. Les annotations conservent leur statut de déclarations de l’utilisateur, et la liste indique leur date d’enregistrement. Cette version ne certifie pas qu’une observation ancienne reste valable après une mise à jour de source. Elle ne propose ni analyse automatique du PLU complet, ni estimation actuelle de prix, ni simulation de construction.

L’endpoint de densification est consulté indépendamment de la fiche, pour conserver le potentiel disponible même lorsqu’aucune fiche liée à une mutation n’existe. Une réponse manquante ne devient pas une surface nulle.

## Validation

La suite frontend comprend 33 tests : règles de synthèse, séparation entre faits et modélisation, objectifs, stockage et réouverture, isolation des parcelles, refus de vérification sans note, données corrompues, quota et export ; calcul multicritère, fourchette incomplète, vrais zéros, poids invalides, point bloquant ignoré, compatibilité des anciens dossiers et restitution des sources. Les tests existants de calcul DVF, concurrence et rendu sont conservés. La charte et la compilation sont vérifiées.

Vérification navigateur sur l’origine isolée 5174 avec le backend local : saisie d’un critère, changement d’onglet, enregistrement, fermeture/réouverture, rechargement complet, point bloquant à poids nul, changement d’objectif, disposition ordinateur et mobile 390 × 844. Les observations de test ne sont pas enregistrées sur l’origine 5173 utilisée par l’utilisateur.

Les étapes ultérieures pourront porter sur les preuves documentaires versionnées et la robustesse des scénarios, après validation de ce parcours avec les utilisateurs. Elles ne font pas partie de cette première version.
