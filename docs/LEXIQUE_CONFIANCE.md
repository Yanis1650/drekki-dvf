# Lexique — Indice de Confiance

## Qu'est-ce que l'indice de confiance ?

L'**indice de confiance** mesure la fiabilité des données affichées pour une parcelle. Plus le score est élevé, plus les estimations (potentiel brut, densification, etc.) sont basées sur des sources robustes et récentes.

---

## Pourquoi c'est important pour vous ?

L'indice vous indique **jusqu'où vous pouvez faire confiance aux chiffres** :

- **Score élevé** → Les estimations (potentiel brut, surface constructible, prix au m²) sont fiables. Vous pouvez vous appuyer dessus pour prioriser vos cibles.
- **Score faible** → Les données sont partielles. Prévoyez une vérification terrain (géomètre, PLU, état des lieux) avant de vous engager.
- **Comparer deux parcelles** → À potentiel similaire, privilégiez celle avec la confiance la plus élevée.

En résumé : *« Ces chiffres, vous pouvez les croire à X % »* — le score vous dit combien compléter par une expertise humaine.

---

## Calcul du score global

Le score global est une **moyenne pondérée** de quatre composantes :

| Composante | Poids | Signification |
|------------|-------|----------------|
| **BDNB** | 30% | Richesse des données bâtiment : emprise au sol, DPE, année de construction, hauteur. Plus la parcelle est documentée dans la Base de Données Nationale des Bâtiments, plus le score est élevé. |
| **DVF** | 25% | Profondeur historique des transactions. Plus il y a de ventes enregistrées (DVF) sur la parcelle, plus on peut estimer le prix au m² avec précision. |
| **Densification** | 25% | Qualité du calcul ZAN (potentiel de densification). Dépend de la source du CES : BDNB (emprise), BD TOPO, PLU, RNU, etc. |
| **Fraîcheur** | 20% | Récence de la dernière vente. Une vente récente (ex. 2023) donne un meilleur score qu'une vente ancienne (avant 2014). |

**Formule :** Score = (BDNB × 30%) + (DVF × 25%) + (Densification × 25%) + (Fraîcheur × 20%)

---

## Niveaux de confiance

| Label | Seuil | Signification |
|-------|-------|---------------|
| **Élevée** | ≥ 75% | Données riches et fiables — les estimations sont robustes. |
| **Moyenne** | 55–75% | Données correctes — utiliser les chiffres avec discernement. |
| **Faible** | 35–55% | Données partielles — à compléter par une expertise terrain. |
| **Insuffisante** | < 35% | Données limitées — les estimations sont indicatives. |

---

## Source ZAN

La mention « Source ZAN : BDNB (emprise sol) » indique l'origine du Coefficient d'Emprise au Sol (CES) utilisé pour le potentiel de densification : BDNB (emprise au sol), BD TOPO IGN, PLU (GPU), RNU (proximité), etc.
