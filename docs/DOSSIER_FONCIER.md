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

## Persistance et limites

L’enregistrement est explicite et local au navigateur (`foncier-express:dossiers:v1`). Les notes ne sont pas envoyées à l’API et ne sont pas synchronisées entre appareils. Il faut enregistrer avant de fermer le dossier et exporter pour conserver une sauvegarde indépendante du navigateur. Une panne de stockage est affichée ; une sauvegarde corrompue ou d’un format non reconnu n’est pas écrasée.

Les données de parcelle sont rechargées à chaque ouverture. Les annotations conservent leur statut de déclarations de l’utilisateur, et la liste indique leur date d’enregistrement. Cette version ne certifie pas qu’une observation ancienne reste valable après une mise à jour de source. Elle ne propose ni analyse automatique du PLU complet, ni estimation actuelle de prix, ni simulation de construction.

L’endpoint de densification est consulté indépendamment de la fiche, pour conserver le potentiel disponible même lorsqu’aucune fiche liée à une mutation n’existe. Une réponse manquante ne devient pas une surface nulle.

## Validation

La suite frontend comprend 26 tests : règles de synthèse, séparation entre faits et modélisation, objectifs, stockage et réouverture, isolation des parcelles, refus de vérification sans note, données corrompues, quota et export ; tests existants de calcul, concurrence et rendu conservés. La charte et la compilation sont vérifiées.

Les étapes ultérieures pourront porter sur les preuves documentaires versionnées et la robustesse des scénarios, après validation de ce parcours avec les utilisateurs. Elles ne font pas partie de cette première version.
