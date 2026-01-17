Documents de filiation informatisés (DFI)
Caractéristiques du fichier
Le fichier est au format txt. Le point-virgule est le caractère séparateur. La taille des champs
est fixe.
Chaque lot d’analyse d’un même document de filiation fait l’objet de deux
lignes successives :
• celle de type 1 pour toutes ses parcelles mères (il peut n’y en avoir aucune dans
le cas d’extraction du domaine non cadastré) ;
• celle de type 2 pour toutes ses parcelles filles (il peut n’y en avoir aucune dans le cas de passage au domaine public).
Par ailleurs, en raison de la nature même des travaux, aucune filiation parcellaire ne peut
être établie au cas particulier de travaux d’aménagements fonciers (ou remembrements).
Contenu du fichier
➢ code département (3 caractères)
➢ code commune (3 caractères)
➢ préfixe de section éventuel (3 caractères, 000 par défaut)
➢ identifiant du DFI (7 caractères)
➢ nature du DFI (1 caractère) :
◦ 1 pour document d’arpentage
◦ 2 pour croquis de conservation
◦ 4 pour remaniement
◦ 5 pour document d’arpentage numérique
◦ 6 pour lotissement numérique
◦ 7 pour lotissement
◦ 8 pour rénovation
➢ date de validation du DFI (8 caractères, au format AAAAMMJJ)
➢ nom du géomètre (30 caractères), le fichier étant anonymisé, ce nom n’est pas
restitué
➢ numéro du lot d’analyse dans le DFI (5 caractères)
➢ type de ligne (1 caractère) :
◦ 1 pour la liste de toutes les parcelles mères ;
◦ 2 pour la liste de toutes les parcelles filles.
➢ puis au maximum 175 cellules de 6 caractères, pouvant contenir chacune un
identifiant de parcelle (section (2) + numéro de plan (4))
Exemple
Lignes d’un document d’arpentage validé le 13 août 1990 et présentant la division d’une
parcelle AC 26 en parcelles AC 214 et AC 215
023;001;000;0000450;1;19900813;XXXXXREDACTEURDUDOCUMENTXXXXXX;00001;1;AC0026;
023;001;000;0000450;1;19900813;XXXXXREDACTEURDUDOCUMENTXXXXXX;00001;2;AC0214;AC0215;