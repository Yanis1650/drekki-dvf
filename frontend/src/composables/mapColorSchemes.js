/**
 * Expressions MapLibre pour les trois modes de carte, alignées sur la charte.
 *
 * Deux règles gouvernent ce fichier :
 *
 *  - Une seule rampe ordonnée pour toute quantité. Les trois modes étant
 *    exclusifs, l'utilisateur n'apprend qu'une échelle : plus c'est foncé, plus
 *    c'est intense. Le dégradé vert-rouge d'origine disparaît — il affirmait
 *    qu'un prix bas est bon et qu'un prix haut est mauvais, ce qui dépend
 *    entièrement de si l'on achète ou si l'on vend.
 *
 *  - Aucune information ne repose sur la seule couleur. Les zones PLU sont
 *    doublées d'une orientation de hachure, et l'absence de donnée est une
 *    hachure, jamais un gris neutre.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md
 */
import { ramp, token } from '../styles/tokens';

/** Seuils de la rampe, en €/m². Ils sont aussi ceux de la légende. */
export const PRIX_PALIERS = [2500, 3000, 3600, 4300];

/** Potentiel de densification, du plus fort au plus faible. */
export const ZAN_ORDRE = ['FORT', 'MOYEN', 'FAIBLE', 'SATURE'];

/** Zones PLU, dans l'ordre de légende de la charte, avec leur hachure. */
export const PLU_ZONES = [
  { code: 'U', libelle: 'Urbanisé', token: '--fe-plu-u', hachure: 45 },
  { code: 'A', libelle: 'Agricole', token: '--fe-plu-a', hachure: 90 },
  { code: 'N', libelle: 'Naturel', token: '--fe-plu-n', hachure: 135 },
  { code: 'AU', libelle: 'À urbaniser', token: '--fe-plu-au', hachure: 'x' },
];

/** Identifiant de l'image de hachure d'une zone PLU. */
export const pluHatchId = (code) => `hachure-plu-${code.toLowerCase()}`;

/** Identifiant de l'image de hachure d'absence de donnée. */
export const HATCH_ABSENT = 'hachure-absente';

/**
 * Remplissage par paliers d'une quantité continue.
 * `step` et non `interpolate` : la légende annonce cinq classes, la carte en
 * montre cinq. Un dégradé continu ne se relit pas dans une légende.
 */
function palierFill(property, paliers, defaut = 'transparent') {
  const couleurs = ramp();
  const expr = ['step', ['coalesce', ['get', property], -1], defaut];
  expr.push(0, couleurs[0]);
  paliers.forEach((seuil, i) => expr.push(seuil, couleurs[i + 1]));
  return expr;
}

/** Parcelles sans valeur mesurable : elles reçoivent la hachure, pas une teinte. */
export const absenceFilter = (property) => [
  'any',
  ['!', ['has', property]],
  ['==', ['get', property], null],
];

export function parcelFill(mode) {
  const couleurs = ramp();
  if (mode === 'zan') {
    // Catégories ordonnées : plus le potentiel est fort, plus le palier est foncé.
    return [
      'match', ['get', 'densification_categorie'],
      'FORT', couleurs[4],
      'MOYEN', couleurs[3],
      'FAIBLE', couleurs[2],
      'SATURE', couleurs[1],
      'transparent',
    ];
  }
  if (mode === 'urbanisme') {
    const expr = ['match', ['get', 'zone_plu']];
    PLU_ZONES.forEach((z) => expr.push(z.code, token(z.token)));
    expr.push('transparent');
    return expr;
  }
  return palierFill('prix_m2_moyen', PRIX_PALIERS);
}

export function pointFill(mode) {
  if (mode === 'zan') {
    return palierFill('zan_score', [0.3, 0.5, 0.7, 0.9]);
  }
  return palierFill('prix_m2', PRIX_PALIERS);
}

/** Opacité de remplissage par mode. */
export function fillOpacity(mode) {
  return mode === 'urbanisme' ? 0.35 : 0.55;
}

/** Propriété dont l'absence déclenche la hachure, par mode. */
export function absenceProperty(mode) {
  if (mode === 'zan') return 'densification_categorie';
  if (mode === 'urbanisme') return 'zone_plu';
  return 'prix_m2_moyen';
}

/** Libellés de la légende, dans l'ordre de la rampe. */
export function legendItems(mode) {
  const couleurs = ramp();
  if (mode === 'zan') {
    return [
      { couleur: couleurs[4], libelle: 'Fort potentiel' },
      { couleur: couleurs[3], libelle: 'Moyen' },
      { couleur: couleurs[2], libelle: 'Faible' },
      { couleur: couleurs[1], libelle: 'Saturé' },
    ];
  }
  if (mode === 'urbanisme') {
    return PLU_ZONES.map((z) => ({ token: z.token, libelle: `${z.code} — ${z.libelle}`, hachure: z.hachure }));
  }
  const bornes = ['< 2 500', '2 500 – 3 000', '3 000 – 3 600', '3 600 – 4 300', '4 300 +'];
  return couleurs.map((couleur, i) => ({ couleur, libelle: `${bornes[i]} €/m²` }));
}
