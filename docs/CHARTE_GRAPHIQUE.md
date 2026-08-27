# Charte graphique — Foncier-Express

Document de référence. En cas de désaccord entre ce document et le code, c'est ce
document qui a raison, et le code qu'il faut corriger.

Jetons : [`frontend/src/styles/tokens.css`](../frontend/src/styles/tokens.css) (écran) ·
[`frontend/src/styles/tokens.js`](../frontend/src/styles/tokens.js) (carte et graphiques) ·
[`app/templates/report_styles.css`](../app/templates/report_styles.css) (PDF)
Configuration : [`frontend/tailwind.config.js`](../frontend/tailwind.config.js)
Contrôle : `npm run check:charte` — voir §10

---

## 1. Intention

Foncier-Express est un instrument de lecture d'un territoire, pas une vitrine.
L'application est libre, sans compte, et destinée au plus grand nombre : un
particulier qui vérifie un prix, un agent d'urbanisme, un notaire, un chercheur.

La charte tire toutes ses conséquences de ce constat.

**Le budget d'originalité est dépensé dans la représentation de la donnée, pas
dans l'habillage.** L'interface est volontairement discrète, neutre et prévisible.
Ce qui doit surprendre, c'est la façon dont l'information est montrée — un prix
écrit là où il a été relevé, une absence visible en tant qu'absence, une échelle
qui résiste au noir et blanc. Pas un dégradé ni une couleur d'accent mémorable.

**Corollaire à ne pas perdre de vue.** Ce qui fait qu'une interface a l'air
générée automatiquement, ce n'est pas la sobriété : c'est la décoration appliquée
par-dessus la donnée sans rien lui apporter — verre dépoli, dégradés, halos,
soulèvement au survol, arc-en-ciel vert-rouge. Une interface sobre s'en éloigne.
Une interface sobre qui retombe dans les gris et l'indigo par défaut de Tailwind
s'en rapproche à nouveau. Les neutres de cette charte sont choisis, pas hérités.

---

## 2. Les six règles

Elles priment sur toute considération esthétique.

1. **Une seule couleur d'accent dans tout le produit.** Le bleu `--fe-accent` ne
   dit qu'une chose : *ceci est interactif ou sélectionné*. Il n'est jamais une
   donnée, jamais un ornement, jamais un fond de section.
2. **Froid = interface, chaud = donnée.** Toute quantité passe par la rampe ocre.
   Aucune donnée n'emprunte le bleu de l'interface, et réciproquement.
3. **Jamais une seule variable visuelle pour porter une information.** Couleur +
   forme, couleur + étiquette, couleur + orientation de hachure. Une carte de
   cette application doit rester lisible imprimée en niveaux de gris.
4. **L'absence de donnée se voit.** Le pipeline répond `503 data_unavailable` ;
   l'interface affiche une hachure et la mention `NON RELEVÉ`. Jamais `0`, jamais
   un tiret seul, jamais une valeur par défaut, jamais une couleur neutre qui
   pourrait passer pour une mesure basse.
5. **Le mesuré et le modélisé ne se ressemblent pas.** Une contenance cadastrale
   se compose en romain ; une médiane, une interpolation ou un score se composent
   en italique, et le bloc qui les contient nomme sa source.
6. **Rien ne bouge sans porter d'information.** Deux durées existent : 120 ms pour
   les états d'interface, 300 ms pour une transition qui montre un changement de
   donnée. Le reste est supprimé.

---

## 3. Couleur

Toutes les valeurs vivent dans `tokens.css`. Aucun hexadécimal dans un `.vue`.

### 3.1 Surfaces et encres

| Jeton | Clair | Sombre | Emploi |
|---|---|---|---|
| `--fe-ground` | `#F7F6F3` | `#15181A` | fond de l'application |
| `--fe-surface` | `#FFFFFF` | `#1C2023` | panneaux, tables, champs |
| `--fe-surface-2` | `#EEEDE9` | `#23282B` | en-têtes de table, zones inactives |
| `--fe-rule` | `#DFDDD7` | `#2F3538` | filet standard |
| `--fe-rule-strong` | `#BAB7AF` | `#454C50` | séparation majeure |
| `--fe-ink` | `#1B1D1E` | `#E8E6E2` | texte principal, valeurs |
| `--fe-ink-2` | `#5A5E60` | `#A8ACAE` | texte secondaire |
| `--fe-ink-3` | `#66696B` | `#868B8D` | étiquettes, unités, graduations |

Les gris tirent légèrement vers le chaud. C'est peu perceptible et c'est voulu :
un gris parfaitement neutre a l'air d'un gris qu'on n'a pas choisi, et il jure
avec la rampe ocre des données.

### 3.2 Accent et sémantique

| Jeton | Clair | Sombre | Emploi |
|---|---|---|---|
| `--fe-accent` | `#1F5C8B` | `#6FB2E0` | lien, action primaire, sélection |
| `--fe-accent-soft` | `#E9F0F5` | `#15303F` | fond de ligne sélectionnée |
| `--fe-alert` | `#A32B0A` | `#E8785A` | contrainte réglementaire bloquante |
| `--fe-warn` | `#8A5A00` | `#D9A441` | donnée ancienne, échantillon insuffisant |

`alert` et `warn` sont réservés. Un prix élevé n'est pas une alerte : la donnée
ne porte pas de jugement, et l'interface non plus.

### 3.3 Rampe séquentielle unique

`--fe-ramp-1` → `--fe-ramp-5` : `#F3E9D9` `#DFC194` `#C29A55` `#96702F` `#5E421A`

Une seule rampe pour toute quantité ordonnée du produit — prix au m², potentiel
de densification, indice de confiance. Les trois modes de carte étant exclusifs,
il n'y a jamais d'ambiguïté, et l'utilisateur n'apprend qu'une seule échelle :
**plus c'est foncé, plus c'est intense.**

Clarté OKLab strictement décroissante (0,938 · 0,826 · 0,709 · 0,570 · 0,402),
donc lisible en niveaux de gris et sous toutes les formes de daltonisme.

Ce que cela remplace : la rampe `#22c55e → #ef4444` de
[`mapColorSchemes.js`](../frontend/src/composables/mapColorSchemes.js). Un
dégradé vert-rouge affirme que le vert est bon et le rouge mauvais. Pour un prix
immobilier, cette affirmation dépend entièrement de qui regarde — un vendeur et
un acheteur ne la liront pas dans le même sens.

### 3.4 Zones PLU

Catégoriel, donc validé pour le daltonisme (pire paire adjacente ΔE 17,4 en
deutéranopie, 23,1 en vision normale). Chaque zone est **doublée d'une
orientation de hachure**, qui reste seule porteuse à l'impression.

| Zone | Jeton | Clair | Hachure |
|---|---|---|---|
| U — urbanisé | `--fe-plu-u` | `#B4552F` | 45° |
| A — agricole | `--fe-plu-a` | `#B4AE20` | 90° |
| N — naturel | `--fe-plu-n` | `#2E7D4F` | 135° |
| AU — à urbaniser | `--fe-plu-au` | `#E0A11C` | croisée |

L'ordre de légende suit la nature de la zone : bâti, cultivé, naturel, puis en
mutation. Il est aussi celui qui maximise l'écart entre voisins de légende.

---

## 4. Typographie

**IBM Plex Sans** pour l'interface, **IBM Plex Mono** pour les identifiants
(références de parcelle, codes INSEE, sections cadastrales). Une seule
superfamille, dessinée pour les contextes techniques, avec des glyphes
distinguables — `0`/`O` et `1`/`l`/`I` ne se confondent pas, ce qui compte quand
on lit `35238 000 AB 0142`.

| Rôle | Taille | Graisse | Détail |
|---|---|---|---|
| Étiquette | 11 px | 600 | capitales, interlettrage +0,06em, `--fe-ink-3` |
| Méta / source | 12 px | 400 | `--fe-ink-3` |
| Courant, tables | 13 px | 400 | interligne 1,45 |
| Titre de section | 15 px | 600 | interligne 1,3 |
| Titre de page | 20 px | 600 | |
| Valeur principale | 28 px | 500 | `tabular-nums` obligatoire |

**Tous les chiffres sont tabulaires**, partout, sans exception. C'est la
différence entre une colonne de prix qu'on compare d'un regard et une colonne
qu'il faut lire ligne à ligne.

**L'italique est sémantique**, pas emphatique. Elle signale une valeur modélisée.
Elle n'est jamais le seul support de cette information : le cartouche qui
contient la valeur nomme toujours sa source et sa date.

---

## 5. Trame, géométrie, élévation

- Trame de **4 px**. Toutes les marges et hauteurs sont des multiples.
- Rayons : **2 px** pour les champs et badges, **4 px** pour les panneaux et
  boutons. Rien au-delà. Le `rounded-xl` généralisé est un tic d'interface, pas
  une décision.
- **Aucune ombre portée**, à une exception : `--fe-shadow-overlay`, pour les
  couches réellement flottantes (menu déroulant, popup de carte). La hiérarchie
  se fait par filets et par fonds, pas par profondeur simulée.
- **Aucun `backdrop-filter`.** Les six classes `.glass-*` de `style.css`
  disparaissent. Elles coûtent cher au rendu sur machine modeste — ce qui n'est
  pas neutre pour une application censée servir tout le monde — et elles réduisent
  le contraste du texte de façon non déterministe, puisqu'il dépend de ce qui
  passe dessous.

---

## 6. Représentation de la donnée

C'est ici que se joue la spécificité de l'application.

### 6.1 La valeur est écrite, pas encodée

À partir du zoom 16, une mutation affiche **son prix au m²**, en toutes lettres,
sur la carte. En dessous, agrégation en une valeur par îlot.

Une pastille colorée oblige à un aller-retour permanent avec la légende, et ne
livre jamais qu'un ordre de grandeur. Le chiffre écrit donne la valeur exacte, et
le semis donne quand même la forme d'ensemble. L'emprunt est assumé : c'est la
convention des cartes marines, où la profondeur est écrite et non coloriée.

### 6.2 Isoprix

Lignes fines `--fe-ink-3` reliant les points de même valeur, tous les 500 €/m²,
étiquette posée sur la ligne et non à côté. Elles donnent le relief du marché —
la pente, les ruptures, les seuils — que ni les pastilles ni les chiffres seuls
ne montrent.

### 6.3 L'absence est dessinée

Toute donnée manquante est une zone hachurée portant la mention `NON RELEVÉ`.
Elle n'est jamais grise-neutre : un gris neutre se lit comme une valeur basse.

C'est la traduction visuelle de la règle du projet — *ne jamais inventer une
donnée*. Aujourd'hui l'API la respecte ; l'interface doit la rendre visible.

### 6.4 Une médiane ne va jamais seule

Toute valeur agrégée est accompagnée de son effectif (`n = 12 mutations`) et de
sa dispersion (un mini-histogramme, ou l'écart interquartile). Une médiane sur
3 transactions et une médiane sur 300 ne se présentent pas de la même façon :
en dessous de 5 mutations, la valeur passe en `--fe-warn` avec la mention
`échantillon faible`.

### 6.5 L'indice de confiance montre ses sources

Plutôt qu'un score opaque sur 10, le composant liste les sources et leur état :
présente, absente, ancienne. L'utilisateur voit *pourquoi* la confiance est ce
qu'elle est, et peut juger si la source manquante compte pour son usage.

### 6.6 Comparaison au secteur inline

Une valeur qui a un point de comparaison porte un repère de référence sur sa
propre barre, pas un second chiffre à côté. L'écart se lit sans soustraction
mentale.

---

## 7. Composants

Le **cartouche** remplace la carte. C'est le conteneur unique de l'application :
un bandeau d'étiquette en haut, le contenu, une ligne de source en bas.

Cette ligne de source n'est pas optionnelle. Chaque bloc dit d'où vient ce qu'il
montre et de quand cela date (`DVF 2014-2025 · maj. 03/2026`). C'est ce qui rend
l'application vérifiable plutôt que simplement affirmative, et c'est ce que la
plupart des interfaces de données omettent.

Les autres composants — bouton, champ, table, badge de zone, échelle de rampe,
jauge, chronologie de filiation — sont spécifiés visuellement dans le styleguide
publié, qui sert de référence de rendu.

---

## 8. Accessibilité et robustesse

Engagements vérifiables, pas des intentions :

- **Contraste** : tout texte ≥ 4,5:1 sur son fond. Valeurs mesurées en tête de
  `tokens.css`, à revérifier à chaque modification de jeton.
- **Niveaux de gris** : toute carte et tout graphique restent lisibles en
  `filter: grayscale(1)`. C'est le test de daltonisme et le test d'impression en
  une seule vérification.
- **Zoom 200 %** : aucune perte de fonction, aucun défilement horizontal du
  document.
- **Clavier** : focus visible sur tout élément focalisable, sans exception.
- **`prefers-reduced-motion`** : respecté globalement dans `tokens.css`.
- **Impression** : les mêmes jetons servent l'écran et les fiches PDF générées
  par Playwright. Un seul système à maintenir au lieu de deux.

---

## 9. Ce qui est supprimé

| Supprimé | Motif |
|---|---|
| Palettes `sage`, `terracotta`, `cream`, `rouge` | quatre systèmes concurrents, aucun ne gouverne |
| Couleurs Tailwind par défaut dans les `.vue` | 25 hexadécimaux en dur, dont `#6366f1` et `#64748b` |
| `.glass`, `.glass-light`, `.glass-dark`, `.glass-sidebar`, `.glass-heavy`, `.card-glass` | coût de rendu, contraste non déterministe |
| `.btn-premium` (dégradé, halo, `translateY(-2px)`) | l'action ne se signale pas en bougeant |
| `shimmer`, `float`, `pulse-slow` | mouvement sans information |
| `.credit-ticket` | vestige d'un modèle payant abandonné |
| `--shadow-glow-primary`, `--shadow-glow-accent` | halos décoratifs |
| Rampe `#22c55e → #ef4444` | jugement implicite sur une donnée neutre |
| Cormorant Garamond + DM Sans | appariement par défaut, empattements peu lisibles à 13 px |

---

## 10. Migration — faite

Les six lots ont été appliqués. État vérifié au 27/08/2026 : `npm run check:charte`
ne relève aucun écart, `npm run build` passe sans avertissement CSS, les 168 tests
back-end passent, et les deux gabarits PDF se rendent sans couleur hors charte.

| Lot | Contenu | État |
|---|---|---|
| 1 | `tokens.css` importé par `main.js` | fait |
| 2 | `style.css` réécrit sur les jetons — 653 → 380 lignes | fait |
| 3 | `tailwind.config.js` basculé, vérificateur `check:charte` ajouté | fait |
| 4 | 25 fichiers de composants migrés (549 écarts → 0) | fait |
| 5 | Carte : rampe unique, valeurs écrites, hachures, fond désaturé | fait |
| 6 | Gabarits PDF unifiés sur une feuille de jetons partagée | fait |

### Comment la charte tient dans la durée

**`npm run check:charte`** — le point important. Tailwind **n'échoue pas** sur une
classe inconnue : il l'ignore silencieusement. Un `text-slate-500` oublié ne
casse donc rien, il produit juste du texte sans couleur, et la charte se dilue
sans que personne ne le voie. Le vérificateur, lui, échoue : il refuse les
palettes hors charte, les hexadécimaux en dur, les tailles de texte hors échelle,
les rayons non prévus, les ombres décoratives, les dégradés, le verre dépoli et
les animations sans information. Il tourne en CI avant le build.

Une exception justifiée se déclare sur la ligne concernée par le commentaire
`charte-ignore`. Deux fichiers sont exemptés d'office : `styles/tokens.css` et
`styles/tokens.js`, qui sont précisément l'endroit où vivent les valeurs.

### Décisions prises pendant la migration

- **L'échelle d'espacement de Tailwind est conservée.** Elle est déjà la trame de
  4 px ; la restreindre aurait cassé une cinquantaine de classes de taille — dont
  les `w-3.5` des icônes — sans rien gagner.
- **`useColorScale.js` supprimé.** Module mort, doublon de la rampe.
- **Vue de carte remise à plat** (`pitch: 0`). L'inclinaison à 45° déformait les
  parcelles, c'est-à-dire ce que l'utilisateur vient lire.
- **Double axe supprimé** dans `MarketTrendsChart`. Deux échelles verticales
  indépendantes laissent choisir la forme de leur croisement : prix et volume
  sont désormais deux graphiques empilés sur un axe des années commun.
- **Jeu de glyphes ajouté au style de carte.** Le semis de valeurs en a besoin —
  et son absence rendait déjà muet le compte des agrégats.
- **CDN Tailwind retiré de `land_report.html`.** Il exigeait un accès réseau au
  moment du rendu Playwright ; les deux gabarits partagent maintenant
  `app/templates/report_styles.css`.

### Reste à vérifier à l'œil

Deux points ne peuvent pas l'être sans un navigateur et un backend en marche :

1. **Le semis de valeurs au zoom ≥ 16** et le raccord des hachures, qui dépendent
   du jeu de glyphes IGN (`data.geopf.fr/annexes/ressources/vectorTiles/fonts/`).
   Si les glyphes ne se chargent pas, les valeurs et le compte des agrégats
   restent invisibles — le reste de la carte fonctionne.
2. **La densité du semis vers z14-15**, qui demandera sans doute un réglage de
   `text-padding` selon le secteur.
