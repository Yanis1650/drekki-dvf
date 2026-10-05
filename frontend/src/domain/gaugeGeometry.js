/**
 * Géométrie de la jauge en demi-cercle du potentiel de densification.
 *
 * L'angle va de 0 (extrémité gauche) à 180 (extrémité droite) en passant par
 * le haut. Un arc SVG se décrit par ses deux extrémités, son rayon et deux
 * indicateurs : le sens de parcours, et « grand arc », qui choisit lequel des
 * deux cercles de ce rayon relie les extrémités. Il ne vaut 1 qu'au-delà de
 * 180°, ce que la jauge n'atteint jamais.
 *
 * Il valait 1 dès 90° : entre 50 et 100 % de CES, l'arc était tracé sur
 * l'autre cercle, décalé au-dessus de la piste grise.
 */

/** Point du cercle de centre (cx, cy) et de rayon r, à l'angle donné. */
export function polarToCartesian(cx, cy, r, angle) {
  const rad = (angle - 180) * Math.PI / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

/** Chemin SVG de l'arc entre deux angles, sur le cercle de la piste. */
export function describeArc(startAngle, endAngle, { cx = 100, cy = 100, r = 70 } = {}) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}
