import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSearch, summarize, annualTrends, numberOrNull, describeError, money } from '../src/domain/market.js';
import { studyBoundary } from '../src/domain/studyGeometry.js';
import { useStudyArea } from '../src/composables/useStudyArea.js';

const mutation = (id, overrides = {}) => ({ mutation: { id_mutation: id, prix_m2: '2000',
  valeur_fonciere: '200000', longitude: -1.6, latitude: 48.1, parcelles: ['35238000AB0001'],
  date_mutation: '2025-01-01', ...overrides }, enrichment: null });
const response = (...mutations) => ({ mutations, enrichment_available: false });
test('missing and invalid numbers never become zero', () => {
  for (const v of [null, undefined, '', 'NaN', 'Infinity']) assert.equal(numberOrNull(v), null);
  assert.equal(numberOrNull('0'), 0);
  assert.equal(money(null), 'NON RELEVÉ');
});
test('API adapter deduplicates mutations and keeps parcel identifiers', () => {
  const result = normalizeSearch(response(mutation('a'), mutation('a')));
  assert.equal(result.features.length, 1);
  assert.equal(result.features[0].properties.id_parcelle, '35238000AB0001');
  assert.equal(result.features[0].properties.scores, null);
});
test('no fabricated coordinates and zero longitude remains valid', () => {
  const { features } = normalizeSearch(response(mutation('a', { longitude: null }), mutation('b', { longitude: 0 }), mutation('c', { latitude: 100 })));
  assert.equal(features[0].geometry, null);
  assert.deepEqual(features[1].geometry.coordinates, [0, 48.1]);
  assert.equal(features[2].geometry, null);
});
test('invalid API shape is an error, not an empty market', () => {
  assert.throws(() => normalizeSearch({}));
});
test('KPIs exclude outliers and missing prices while retaining mutation count', () => {
  const data = normalizeSearch(response(mutation('a'), mutation('b', { prix_m2: '4000' }), mutation('c', { prix_m2: '100000', is_outlier: true }), mutation('d', { prix_m2: null })));
  assert.deepEqual({ ...summarize(data) }, { count: 4, priced: 2, avgPrice: 3000, median: 3000, q1: 2500, q3: 3500, outliers: 1, unmapped: 0, firstDate: '2025-01-01', lastDate: '2025-01-01' });
  assert.equal(annualTrends(data)[0].avg_price_m2, 3000);
  assert.equal(annualTrends(data)[0].transaction_volume, 4);
});
test('empty data and all missing prices have no synthetic average', () => {
  assert.equal(summarize({ features: [] }).avgPrice, null);
  assert.equal(annualTrends(normalizeSearch(response(mutation('a', { prix_m2: null }))))[0].avg_price_m2, null);
});
test('availability distinguishes missing dataset and spatial failure', () => {
  assert.match(describeError({ response: { data: { error: 'data_unavailable' } } }), /NON RELEVÉ/);
  assert.match(describeError({ response: { data: { error: 'spatial_unavailable' } } }), /géographique/);
});
test('study boundary closes and follows radius', () => {
  const points = studyBoundary([0, 0], 1000).geometry.coordinates[0];
  assert.equal(points.length, 65);
  assert.ok(Math.abs(points[0][1] * Math.PI / 180 * 6371000 - 1000) < .001);
  assert.ok(Math.abs(points[0][0] - points.at(-1)[0]) < 1e-10);
});
test('latest request wins despite an uncooperative transport', async () => {
  const pending = [];
  const study = useStudyArea({ get: () => new Promise(resolve => pending.push(resolve)) });
  const first = study.refresh();
  study.center.value = [2, 48];
  const second = study.refresh();
  pending[1]({ data: response(mutation('new')) }); await second;
  pending[0]({ data: response(mutation('old')) }); await first;
  assert.equal(study.transactions.value.features[0].id, 'new');
  assert.equal(study.status.value, 'ready');
});
test('failed new search clears old data and retry recovers', async () => {
  let fail = false;
  const study = useStudyArea({ get: async () => { if (fail) throw Error('offline'); return { data: response(mutation('a')) }; } });
  await study.refresh(); fail = true; await study.refresh();
  assert.equal(study.status.value, 'error');
  assert.equal(study.stats.value.count, 0);
  fail = false; await study.refresh();
  assert.equal(study.status.value, 'ready');
});
test('radius and recent period sent to shared endpoint; cap is explicit', async () => {
  let request;
  const study = useStudyArea({ get: async (url, options) => { request = { url, ...options }; return { data: response(...Array.from({ length: 1000 }, (_, i) => mutation(String(i)))) }; } });
  study.radius.value = 5000; study.recent.value = true;
  await study.refresh();
  assert.equal(request.url, '/land/search/enriched');
  assert.equal(request.params.radius, 5000);
  assert.match(request.params.date_from, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(study.capped.value, true);
});
test('dispose prevents late state updates', async () => {
  let resolve;
  const study = useStudyArea({ get: () => new Promise(r => { resolve = r; }) });
  const pending = study.refresh(); study.dispose();
  resolve({ data: response(mutation('late')) }); await pending;
  assert.equal(study.stats.value.count, 0);
});
