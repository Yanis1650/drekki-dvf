import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanCriteria, evaluateCriteria, criteriaText } from '../src/domain/multicriteria.js';
import { createDossierStore } from '../src/composables/useDossiers.js';

test('unknown criteria produce no score; genuine zero ratings are retained', () => {
  assert.equal(evaluateCriteria().score, null);
  assert.equal(evaluateCriteria().low, null);
  const data = cleanCriteria();
  for (const c of Object.values(data)) { c.note = 'Vérifié'; c.rating = 0; }
  assert.equal(evaluateCriteria(data).score, 0);
  assert.equal(evaluateCriteria(data).coverage, 100);
});
test('partial fit shows best/worst bounds using missing weights, not known-only optimism', () => {
  const data = cleanCriteria();
  for (const c of Object.values(data)) c.weight = 0;
  data.marche = { weight: 3, rating: 5, note: 'Comparables consultés' };
  data.risques.weight = 1;
  const result = evaluateCriteria(data);
  assert.equal(result.score, null);
  assert.equal(result.low, 75);
  assert.equal(result.high, 100);
  assert.equal(result.coverage, 75);
});
test('blocker cannot be hidden by a zero weight or otherwise perfect ratings', () => {
  const data = cleanCriteria();
  for (const c of Object.values(data)) { c.rating = 5; c.note = 'Observation'; }
  data.risques.weight = 0; data.risques.blocked = true;
  assert.equal(evaluateCriteria(data).score, 100);
  assert.deepEqual(evaluateCriteria(data).blockers, ['Risques & nuisances']);
});
test('notes are required, invalid ratings and weights cannot enter the calculation', () => {
  const data = cleanCriteria({ marche: { rating: 5, note: ' ' }, risques: { rating: 100, weight: -10, note: 'x', blocked: true } });
  assert.equal(data.marche.rating, null);
  assert.equal(data.risques.rating, null);
  assert.equal(data.risques.weight, 3);
  assert.equal(evaluateCriteria(Object.fromEntries(Object.entries(data).map(([k,v]) => [k, {...v,weight:0}]))).score, null);
});
test('private objective adapts initial priorities and legacy dossiers gain unknown criteria', () => {
  assert.equal(cleanCriteria(null, 'visite').acces.weight, 3);
  assert.equal(cleanCriteria(null, 'potentiel').potentiel.weight, 3);
  const storage = { getItem: () => JSON.stringify([{ parcelId: '35238000AB0001', objective: 'visite' }]), setItem() {} };
  assert.equal(createDossierStore(storage).dossiers.value[0].criteria.acces.rating, null);
});
test('scores, notes and priorities survive save/reload and export with attribution', () => {
  let raw = null;
  const storage = { getItem: () => raw, setItem: (_, v) => { raw = v; } };
  const criteria = cleanCriteria(); criteria.marche = { weight: 1, rating: 4, note: 'Ventes vérifiées le 6 septembre', blocked: false };
  assert.equal(createDossierStore(storage).save({ parcelId: '35238000AB0001', criteria }), true);
  const saved = createDossierStore(storage).find('35238000AB0001').criteria;
  assert.deepEqual(saved, criteria);
  assert.match(criteriaText(saved), /Ventes vérifiées le 6 septembre/);
  assert.match(criteriaText(saved), /pas un score automatique du territoire/);
});
