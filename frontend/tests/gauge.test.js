import test from 'node:test';
import assert from 'node:assert/strict';
import { describeArc } from '../src/domain/gaugeGeometry.js';

/**
 * Centre du cercle que le navigateur trace pour un arc SVG circulaire sans
 * rotation, selon la conversion de la spécification SVG (annexe F.6.5).
 * C'est ce centre qui dit si l'arc tombe sur la piste, pas la chaîne du chemin.
 */
function centreTrace(path) {
  const [x1, y1, r, grandArc, sens, x2, y2] = path
    .match(/^M (\S+) (\S+) A (\S+) \S+ 0 (\d) (\d) (\S+) (\S+)$/)
    .slice(1)
    .map(Number);
  const dx = (x1 - x2) / 2;
  const dy = (y1 - y2) / 2;
  const d2 = dx * dx + dy * dy;
  const k = (grandArc !== sens ? 1 : -1) * Math.sqrt(Math.max(0, (r * r - d2) / d2));
  return { x: k * dy + (x1 + x2) / 2, y: -k * dx + (y1 + y2) / 2 };
}

test('l arc du CES reste sur le cercle de la piste, de 5 a 100 %', () => {
  for (let pct = 5; pct <= 100; pct += 5) {
    const { x, y } = centreTrace(describeArc(0, (pct / 100) * 180));
    assert.ok(
      Math.abs(x - 100) < 1e-6 && Math.abs(y - 100) < 1e-6,
      `CES ${pct} % : arc trace autour de (${x.toFixed(1)}, ${y.toFixed(1)}) au lieu de (100, 100)`,
    );
  }
});

test('la piste complete est un demi-cercle centre sur la jauge', () => {
  const { x, y } = centreTrace(describeArc(0, 180));
  assert.ok(Math.abs(x - 100) < 1e-6 && Math.abs(y - 100) < 1e-6);
});
