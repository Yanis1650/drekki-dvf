# Lexique — Historique Parcellaire (DFI)

## Qu'est-ce que l'historique parcellaire ?

L'**historique parcellaire** (ou **filiation cadastrale**) retrace la généalogie administrative d'une parcelle : d'où elle provient, par quelles opérations cadastrales elle a été créée, et quelles parcelles l'ont précédée.

Exemple : *« Issue de la parcelle DI0003 (modifiée en 1990) »* signifie que la parcelle actuelle a été **créée à partir** de la parcelle DI0003 lors d'une opération de mise à jour du plan cadastral en 1990.

---

## Vocabulaire

| Terme | Signification |
|-------|---------------|
| **Parcelle mère** | Parcelle d'origine qui a été divisée, réunie ou modifiée |
| **Parcelle fille** | Parcelle actuelle issue de la transformation de la parcelle mère |
| **Section** | Zone du plan cadastral (lettres : A, B, DI, etc.) |
| **Numéro de plan** | Identifiant unique de la parcelle dans la section (ex. 0003, 0214) |

---

## Types d'opérations (nature DFI)

Les DFI (Documents de Filiation Informatisés) documentent les modifications du plan cadastral depuis les années 1980-1990. Chaque opération est classée par **nature** :

| Code | Nature | Signification |
|------|--------|---------------|
| **1** | Arpentage | Document d'arpentage — mesure et délimitation officielle par un géomètre. Division ou réunion de parcelles avec levé terrain. |
| **2** | Conservation | Croquis de conservation — mise à jour du plan lors de constats terrain (ventes partielles, divisions à l'amiable, changements de limites). Procédure légère sans arpentage complet. |
| **4** | Remaniement | Rénovation ou refonte du plan cadastral d'une commune. |
| **5** | Arpentage numérique | Arpentage réalisé en mode numérique (DAF). |
| **6** | Lotissement numérique | Création de lotissement en mode numérique. |
| **7** | Lotissement | Division d'une parcelle en plusieurs lots destinés à la vente ou à la construction. |
| **8** | Rénovation | Rénovation du plan cadastral (remise à jour générale). |

---

## Explication de « Conservation »

**Conservation** (code 2) = **Croquis de conservation**.

C'est la procédure la plus courante de mise à jour du plan. Elle intervient notamment quand :

- Un propriétaire vend une partie de sa parcelle (vente partielle)
- Des limites sont modifiées à l'amiable entre voisins
- Une parcelle est incorporée au domaine public
- Une parcelle non cadastrée est rattachée au plan

Le géomètre-cadastreur établit un **croquis** constatant les changements, sans réaliser un arpentage complet. Le plan cadastral est ensuite mis à jour.

---

## Source des données

- **Source** : DGFiP (Direction Générale des Finances Publiques)
- **Diffusion** : data.gouv.fr, mise à jour trimestrielle
- **Périmètre** : modifications depuis l'informatisation (1980-1990 selon les départements)
- **Non inclus** : aménagements fonciers ruraux (remembrements) — aucune correspondance géographique parcelle à parcelle

---

## Limites connues de l'implémentation

### Profondeur bornée à 10 niveaux

La reconstruction récursive de l'arbre ancêtre s'arrête à **10 générations** par défaut (`depth_limit=10`).
Les communes ayant subi plusieurs remaniements cadastraux successifs peuvent dépasser cette limite.
Lorsqu'un nœud est tronqué, le champ `truncated: true` est exposé dans la réponse API et dans le modèle `FiliationNode`. Le frontend doit afficher un indicateur visuel (ex. « ⚠ historique incomplet »).

### Détection de cycles

Des erreurs de saisie dans les données DFI peuvent créer des références circulaires (A → B → C → A). Le module détecte ces cycles via un set `visited_ids` maintenu pendant la récursion. En cas de cycle, un **ERROR** est loggé, l'arbre partiel est retourné avec `truncated: true`, et aucune exception n'est levée côté API.

### Aménagements fonciers ruraux (remembrements)

Les opérations de **remembrement** (SAFER, aménagement foncier agricole et forestier) ne figurent **pas** dans les données DFI. Ces opérations redistribuent des parcelles sans correspondance géographique 1-à-1 ; la chaîne de filiation DFI ne s'applique pas. Pour ces communes :

- L'arbre ancêtre peut être vide (pas d'ancêtre retrouvé) même pour des parcelles récentes
- Ce comportement est **normal** — ce n'est pas un bug de l'implémentation
- Aucune correction n'est possible sans source de données complémentaire (SAFER, registre parcellaire graphique)

### Validation géométrique optionnelle

Le champ `coherence_geo` compare la surface de la parcelle fille avec celle de sa mère via `ST_Intersection`. Cette validation est **optionnelle** :

| Valeur | Condition |
|--------|-----------|
| `OK` | Overlap ≥ 80% |
| `PARTIELLE` | Overlap ≥ 30% (division avec reste, cas normal) |
| `DOUTEUSE` | Overlap < 30% (possible erreur de saisie DFI — WARNING loggé) |
| `NON_VERIFIABLE` | Géométrie absente ou extension spatiale non disponible |

La valeur `DOUTEUSE` ne bloque pas la réponse API mais doit être traitée comme un signal d'alerte.

---

## Références

- [Documents de filiation informatisés (DFI)](https://data.economie.gouv.fr/explore/dataset/documents-de-filiation-informatises-dfi-des-parcelles/)
- [BOI-CAD-MAJ-20 : Croquis de conservation](https://bofip.impots.gouv.fr/bofip/5184-PGP.html)
- [Historique des parcelles cadastrales (data.gouv.fr)](https://www.data.gouv.fr/fr/datasets/historique-des-parcelles-cadastrales-filiation/)
