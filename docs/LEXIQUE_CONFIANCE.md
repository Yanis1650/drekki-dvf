# Lexique — Indice de Confiance

## Qu'est-ce que l'indice de confiance ?

L'**indice de confiance** mesure la fiabilité des données affichées pour une parcelle. Plus le score est élevé, plus les estimations (potentiel brut, densification, surface constructible) reposent sur des sources robustes et récentes.

---

## Pourquoi c'est important pour vous ?

L'indice vous indique **jusqu'où vous pouvez faire confiance aux chiffres** :

- **Score élevé** → Les estimations sont fiables. Vous pouvez vous appuyer dessus pour prioriser vos cibles.
- **Score faible** → Les données sont partielles. Prévoyez une vérification terrain (géomètre, PLU, état des lieux) avant de vous engager.
- **Comparer deux parcelles** → À potentiel similaire, privilégiez celle avec la confiance la plus élevée.

---

## Composantes du score

### 1. BDNB — Richesse données bâtiment (poids variable)

Mesure la quantité d'attributs bâtiment disponibles dans la Base de Données Nationale des Bâtiments.

| Données disponibles | Score |
|---------------------|-------|
| DPE + année construction + hauteur | 1.0 |
| DPE ou année construction | 0.6 |
| Parcelle identifiée mais données minimales | 0.3 |
| Aucune donnée BDNB | 0.0 |

---

### 2. Qualité source ZAN — Fiabilité du calcul de densification (poids variable)

Évalue la source utilisée pour le Coefficient d'Emprise au Sol (CES) potentiel.
**Découplée du score BDNB** : une parcelle sans données bâtiment est pénalisée une seule fois, pas deux.

| Source CES | Score | Signification |
|------------|-------|---------------|
| `bdnb_emprise` | 1.00 | Emprise au sol mesurée depuis BDNB — source la plus précise |
| `bdtopo` | 0.85 | Emprise depuis BD TOPO IGN |
| `plu_gpu` | 0.70 | CES réglementaire issu du PLU (GPU) |
| `rnu_proximite` + BDNB présent | 0.30 | Emprise inconnue mais bâtiment documenté |
| `rnu_proximite` sans BDNB | 0.10 | Pénalité unique consolidée — absence totale de données bâtiment |
| `bdnb_usage_only` | 0.40 | Usage BDNB connu, emprise non disponible |

> La valeur 0.45 (ancienne valeur `rnu_proximite` avant cette correction) créait une
> double pénalité car le score BDNB = 0 pénalisait déjà la même lacune.

---

### 3. DVF — Fiabilité et précision transactionnelle (poids variable)

Deux sous-scores calculés pour toutes les parcelles, mais utilisés différemment selon le contexte :

#### `score_dvf_fiabilite` (binaire)
*Question : peut-on calculer un prix au m² ?*

| Transactions connues | Score |
|----------------------|-------|
| ≥ 1 | 1.0 |
| 0 | 0.0 |

#### `score_dvf_precision` (granulaire)
*Question : avec quelle précision peut-on estimer la valeur marchande ?*

| Transactions connues | Score |
|----------------------|-------|
| ≥ 5 | 1.0 |
| ≥ 3 | 0.80 |
| ≥ 1 | 0.50 |
| 0 | 0.0 |

**Quel sous-score est utilisé dans la formule globale ?**
- Zones agricoles/naturelles (`zone_non_mutable = True`) → `score_dvf_fiabilite`
  *Une parcelle agricole peu transactée n'est pas moins fiable, juste moins liquide.*
- Zones urbanisées/à urbaniser → `score_dvf_precision`

---

### 4. Fraîcheur — Récence de la dernière transaction (zones U/AU uniquement)

Mesure la récence de la dernière vente enregistrée dans DVF.

| Dernière vente | Score |
|----------------|-------|
| 2023 ou après | 1.0 |
| 2020–2022 | 0.8 |
| 2017–2019 | 0.5 |
| 2014–2016 | 0.3 |
| Avant 2014 ou inconnue | 0.0 |

> **Non pertinent pour les zones A/N** : une parcelle agricole peu transactée
> n'est pas moins fiable. Le poids Fraîcheur est redistribué sur BDNB et ZAN.

---

## Formule globale (pondération conditionnelle)

### Zones U et AU (constructibles)

```
Confiance = BDNB × 30% + DVF précision × 25% + ZAN × 25% + Fraîcheur × 20%
```

### Zones A et N (`zone_non_mutable = True`)

```
Confiance = BDNB × 40% + DVF fiabilité × 25% + ZAN × 35%
```

Les 20% de Fraîcheur sont redistribués : +10% sur BDNB, +10% sur ZAN.

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

La mention « Source ZAN : BDNB (emprise sol) » indique l'origine du Coefficient d'Emprise au Sol (CES)
utilisé pour le potentiel de densification. Les sources possibles, par ordre de précision décroissante :
`bdnb_emprise` → `bdtopo` → `plu_gpu` → `bdnb_usage_only` → `rnu_proximite`.
