import test from 'node:test';
import assert from 'node:assert/strict';
import { csvFilename, studyToCsv } from '../src/domain/exportCsv.js';
import { normalizeSearch } from '../src/domain/market.js';

const response = (...mutations) => ({ mutations, enrichment_available: false });
const mutation = (id, extra = {}) => ({
  mutation: {
    id_mutation: id, date_mutation: '2025-01-01', type_local: 'Maison',
    valeur_fonciere: '250000', prix_m2: '3000', parcelles: ['35238000AB0001'],
    longitude: -1.6778, latitude: 48.1173, ...extra,
  },
  enrichment: null,
});

test('export carries the same exclusions as the screen and never fills a gap', () => {
  const data = normalizeSearch(response(
    mutation('a'),
    mutation('b', { prix_m2: null, is_outlier: true, type_local: null, longitude: null, latitude: null }),
  ));
  const [header, first, second] = studyToCsv(data).split('\r\n');

  assert.match(header, /^id_mutation;date_mutation;type_local/);
  assert.match(header, /exclu_des_prix_agreges/);
  assert.match(first, /^a;2025-01-01;Maison;250000;3000;non;/);

  // Une absence sort vide : ni zéro, ni valeur par défaut.
  const cells = second.split(';');
  assert.equal(cells[2], '');
  assert.equal(cells[4], '');
  assert.equal(cells[5], 'oui');
  assert.equal(cells.at(-1), '');
  assert.equal(cells.at(-2), '');
});

test('export escapes separators and quotes rather than shifting columns', () => {
  const data = normalizeSearch(response(mutation('c', { type_local: 'Local ; "mixte"' })));
  const row = studyToCsv(data).split('\r\n')[1];
  assert.match(row, /;"Local ; ""mixte""";/);
  assert.equal(row.split(';').length > 11, true);
});

test('filename records the perimeter and radius without accents or spaces', () => {
  assert.match(csvFilename('12 Rue de la Liberté, Rennes', 1000), /^foncier-express_12-rue-de-la-liberte-rennes_1000m_\d{4}-\d{2}-\d{2}\.csv$/);
  assert.match(csvFilename('', 500), /^foncier-express_perimetre_500m_/);
});
