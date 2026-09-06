# 0005 — La charte graphique est vérifiée par un script, pas par revue

**Statut :** acceptée · **Date :** 2026-08

## Contexte

Le projet s'est doté d'une charte stricte : une seule rampe ocre pour toute
quantité ordonnée, un seul bleu réservé à l'interface, des hachures pour
l'absence de donnée, six tailles de texte, deux rayons, une ombre. Le tout
défini dans `frontend/src/styles/tokens.css`, qui fait seul autorité.

Le problème est mécanique : **Tailwind n'échoue pas sur une classe inconnue.**
Un `text-slate-500` oublié ne produit aucune règle CSS, aucune erreur, aucun
avertissement. Le texte perd sa couleur, personne ne le remarque, et la charte
fond au fil des commits sans qu'aucun moment précis puisse être désigné.

Une revue humaine attrape la première occurrence, rarement la trentième.

## Décision

Remplacer la palette Tailwind par défaut dans `tailwind.config.js` — écrire
`text-slate-500` ne produit plus rien du tout — et ajouter un vérificateur,
`npm run check:charte`, qui **échoue** sur neuf familles d'écarts : palettes hors
charte, blanc et noir en dur, hexadécimaux, tailles de texte hors échelle,
rayons hors charte, ombres décoratives, dégradés, verre dépoli, animations
décoratives.

Le script tourne dans la CI, au même rang que les tests. Une ligne peut se
soustraire à une règle en la nommant : le commentaire `charte-ignore` rend
l'exception visible et justifiable en revue, au lieu de la rendre invisible.

Deux fichiers sont exemptés, avec leur raison inscrite dans le script :
`tokens.css` — c'est là que les hexadécimaux vivent — et `tokens.js`, qui porte
leurs valeurs de repli pour les contextes sans DOM.

## Conséquences

- La charte ne peut plus se dégrader silencieusement : elle casse la CI.
- Les exceptions existent, mais elles sont écrites et comptées.
- Le vérificateur documente la charte autant qu'il la fait respecter : ses
  messages disent *pourquoi* chaque règle existe, pas seulement qu'elle est
  violée.
- **Le coût :** une analyse par expressions régulières ligne à ligne. Elle ne
  comprend pas le CSS, ne suit pas une valeur à travers une variable, et ne dira
  jamais si une couleur est *bien employée* — seulement si elle vient de la
  charte.

## Alternatives écartées

**Stylelint.** Comprend le CSS, mais pas les classes utilitaires dans un
`template` Vue, qui sont l'essentiel de la surface à contrôler.

**Revue humaine seule.** C'était l'état initial. Elle a laissé passer quatre
palettes concurrentes et six classes `.glass-*`.

**Un thème Tailwind restrictif sans vérificateur.** Nécessaire mais insuffisant :
la configuration restreint ce que Tailwind *génère*, pas ce qu'un développeur
*écrit*. Une classe inconnue reste silencieuse — c'est le défaut d'origine.
