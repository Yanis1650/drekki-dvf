/**
 * Accès aux jetons de la charte depuis JavaScript.
 *
 * MapLibre et ApexCharts n'acceptent pas `var(--fe-…)` : il leur faut des
 * couleurs littérales. Elles sont donc lues sur `:root` au moment de l'usage,
 * ce qui les garde alignées sur le thème actif.
 *
 * Les valeurs de repli reproduisent le thème clair de tokens.css. Elles ne
 * servent qu'aux contextes sans DOM (tests, rendu hors navigateur) : en
 * fonctionnement normal, c'est toujours la feuille de style qui fait foi.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md
 */

const FALLBACK = {
  '--fe-ground': '#F7F6F3',
  '--fe-surface': '#FFFFFF',
  '--fe-surface-2': '#EEEDE9',
  '--fe-rule': '#DFDDD7',
  '--fe-rule-strong': '#BAB7AF',
  '--fe-ink': '#1B1D1E',
  '--fe-ink-2': '#5A5E60',
  '--fe-ink-3': '#66696B',
  '--fe-accent': '#1F5C8B',
  '--fe-accent-hover': '#17486D',
  '--fe-accent-soft': '#E9F0F5',
  '--fe-accent-ink': '#FFFFFF',
  '--fe-alert': '#A32B0A',
  '--fe-warn': '#8A5A00',
  '--fe-ramp-1': '#F3E9D9',
  '--fe-ramp-2': '#DFC194',
  '--fe-ramp-3': '#C29A55',
  '--fe-ramp-4': '#96702F',
  '--fe-ramp-5': '#5E421A',
  '--fe-ramp-1-ink': '#1B1D1E',
  '--fe-ramp-2-ink': '#1B1D1E',
  '--fe-ramp-3-ink': '#1B1D1E',
  '--fe-ramp-4-ink': '#FFFFFF',
  '--fe-ramp-5-ink': '#FFFFFF',
  '--fe-plu-u': '#B4552F',
  '--fe-plu-a': '#B4AE20',
  '--fe-plu-n': '#2E7D4F',
  '--fe-plu-au': '#E0A11C',
  '--fe-absent-ink': '#9A9D9F',
};

/** Valeur d'un jeton, lue sur :root. */
export function token(name) {
  if (typeof document === 'undefined') return FALLBACK[name] || '';
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || FALLBACK[name] || '';
}

/** Les cinq paliers de la rampe séquentielle, du plus clair au plus foncé. */
export function ramp() {
  return [1, 2, 3, 4, 5].map((i) => token(`--fe-ramp-${i}`));
}

/** L'encre à poser sur chaque palier de la rampe. */
export function rampInk() {
  return [1, 2, 3, 4, 5].map((i) => token(`--fe-ramp-${i}-ink`));
}

/** Les quatre zones PLU, dans l'ordre de légende de la charte. */
export function pluColors() {
  return {
    U: token('--fe-plu-u'),
    A: token('--fe-plu-a'),
    N: token('--fe-plu-n'),
    AU: token('--fe-plu-au'),
  };
}

/**
 * Motif de hachure, en image prête pour `map.addImage`.
 *
 * La charte interdit qu'une information repose sur la seule couleur. Sur la
 * carte, l'orientation de la hachure est le second support : les quatre zones
 * PLU restent distinctes en niveaux de gris comme à l'impression.
 *
 * L'absence de donnée emploie le même mécanisme. Une parcelle non couverte
 * n'est jamais coloriée d'un gris neutre — un gris se lit comme une valeur
 * basse — mais hachurée, ce qui ne peut être confondu avec aucune mesure.
 *
 * @param {object}  options
 * @param {number}  options.angle   orientation en degrés : 45, 90, 135, ou 'x'
 *                                  pour une hachure croisée
 * @param {string}  options.color   couleur du trait
 * @param {number}  options.size    côté de la tuile, en points CSS
 */
export function createHatchImage({ angle = 45, color, size = 8, lineWidth = 1.2 } = {}) {
  const dpr = typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 2) : 1;
  const px = Math.round(size * dpr);
  const canvas = document.createElement('canvas');
  canvas.width = px;
  canvas.height = px;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, px, px);
  ctx.strokeStyle = color || token('--fe-absent-ink');
  ctx.lineWidth = lineWidth * dpr;
  ctx.lineCap = 'square';

  const angles = angle === 'x' ? [45, 135] : [angle];
  ctx.beginPath();
  for (const a of angles) {
    if (a === 90) {
      // Trait vertical : deux passes pour que la tuile se raccorde.
      ctx.moveTo(px / 4, -1);
      ctx.lineTo(px / 4, px + 1);
      ctx.moveTo((px * 3) / 4, -1);
      ctx.lineTo((px * 3) / 4, px + 1);
    } else if (a === 135) {
      // Diagonale descendante, répétée hors tuile pour un raccord bord à bord.
      for (let k = -1; k <= 1; k += 1) {
        ctx.moveTo(k * px, 0);
        ctx.lineTo(k * px + px, px);
      }
    } else {
      // Diagonale montante.
      for (let k = -1; k <= 1; k += 1) {
        ctx.moveTo(k * px, px);
        ctx.lineTo(k * px + px, 0);
      }
    }
  }
  ctx.stroke();

  return {
    width: px,
    height: px,
    data: new Uint8Array(ctx.getImageData(0, 0, px, px).data.buffer),
    pixelRatio: dpr,
  };
}
