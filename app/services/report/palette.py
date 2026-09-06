"""Couleurs du rapport PDF, nommees par leur role.

Ces valeurs sont reprises telles quelles de l'ancien `report_generator.py` :
les extraire ne change rien au rendu. Elles sont regroupees ici pour qu'on
puisse les voir d'un coup et les faire evoluer en un seul endroit.

**Elles ne viennent pas de la charte.** Ce sont des couleurs de palettes
Tailwind — indigo, green, blue, violet, slate — que `tokens.css` bannit
explicitement cote interface. `check-charte` ne les voit pas : il ne scanne
que `frontend/src`. Les aligner sur les jetons `--fe-*` changerait l'apparence
des PDF deja produits, donc c'est une decision a prendre, pas un effet de bord
de refonte.
"""

# Traces des graphiques
ACCENT = "#6366f1"           # radar et carte : remplissage, ligne, points
ACCENT_FONCE = "#4338ca"     # carte : contour de la parcelle
ACCENT_VIF = "#4f46e5"       # accent d'un intitule dans le PDF
NEUTRE = "#94a3b8"           # barres de reference (minimum, maximum)
BIEN = "#22c55e"             # barre du bien analyse
BIEN_BORD = "#16a34a"        # contour de cette meme barre

# En-tetes de tableau : un fond clair et son texte, par section
CADASTRE_FOND = "#eff6ff"
CADASTRE_TEXTE = "#1e40af"
PRIX_FOND = "#f0fdf4"
PRIX_TEXTE = "#166534"
DETAILS_FOND = "#f5f3ff"
DETAILS_TEXTE = "#4c1d95"
