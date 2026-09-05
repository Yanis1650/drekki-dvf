import test from 'node:test';
import assert from 'node:assert/strict';
import { buildDossier, dossierText } from '../src/domain/dossier.js';
import { createDossierStore, cleanDossier, STORAGE_KEY } from '../src/composables/useDossiers.js';
const id = '35238000AB0001';
const memory = (initial = null) => { let data = initial; return { getItem: () => data, setItem: (_, value) => { data = value; } }; };
test('missing sources never imply feasibility or invented area', () => {
  const dossier = buildDossier({ fiche: null, densification: null });
  assert.equal(dossier.facts.length, 0);
  assert.match(dossier.summary, /ne permettent pas de conclure/);
  assert.ok(dossier.unknowns.some(s => s.includes('servitudes')));
});
test('available model is distinguished from data and regulatory verification', () => {
  const dossier = buildDossier({ fiche: { libelle_zone: 'U' }, densification: { surface_constructible_restante: '124' }, transactions: [{ price_m2: 2000 }, { price_m2: 100000, is_outlier: true }], historyAvailable: true });
  assert.equal(dossier.facts.find(f => f.label === 'Surface restante estimée').kind, 'Modélisé');
  assert.match(dossier.facts.find(f => f.label.includes('Prix moyen')).source, /1 prix exploitable/);
  assert.match(dossier.checks.find(c => c.id === 'regles').why, /ne décrit pas toutes/);
});
test('visit objective changes practical questions, never facts', () => {
  const potential = buildDossier({ objective: 'potentiel' }), visit = buildDossier({ objective: 'visite' });
  assert.deepEqual(potential.facts, visit.facts);
  assert.equal(visit.checks[0].id, 'terrain');
  assert.match(visit.checks.find(c => c.id === 'acces').action, /Pendant la visite/);
});
test('zero modelled surface is a real zero, not missing', () => {
  const dossier = buildDossier({ densification: { surface_constructible_restante: 0 } });
  assert.equal(dossier.facts[0].value, '0 m²');
  assert.ok(!dossier.unknowns.some(s => s.includes('potentiel')));
});
test('local dossiers survive reloading and stay isolated by parcel', () => {
  const storage = memory(), store = createDossierStore(storage);
  assert.equal(store.save({ parcelId: id, objective: 'visite', notes: 'Demander le plan', checks: { acces: { note: 'Plan reçu', done: true } } }), true);
  store.save({ parcelId: '35238000AB0002', notes: 'Autre terrain' });
  const restored = createDossierStore(storage);
  assert.equal(restored.find(id).notes, 'Demander le plan');
  assert.equal(restored.find(id).checks.acces.done, true);
  assert.equal(restored.dossiers.value.length, 2);
  restored.save({ ...restored.find(id), notes: 'Plan à préciser' });
  assert.equal(restored.dossiers.value.length, 2);
});
test('a check cannot be marked complete without an observation', () => {
  const draft = cleanDossier({ parcelId: id, checks: { acces: { note: ' ', done: true } } });
  assert.equal(draft.checks.acces.done, false);
});
test('invalid records and corrupted storage are not overwritten', () => {
  for (const initial of ['{broken', '{"unknown":1}', '[{"legacy":true}]']) {
    const storage = memory(initial), store = createDossierStore(storage);
    assert.equal(store.save({ parcelId: id }), false);
    assert.equal(storage.getItem(STORAGE_KEY), initial);
    assert.ok(store.error.value);
  }
});
test('storage quota failure does not claim the dossier was saved', () => {
  const store = createDossierStore({ getItem: () => null, setItem: () => { throw new Error('Quota exceeded'); } });
  assert.equal(store.save({ parcelId: id }), false);
  assert.equal(store.dossiers.value.length, 0);
  assert.match(store.error.value, /Exportez/);
});
test('export retains provenance and clearly labels personal observations', () => {
  const content = dossierText({ parcelId: id, objective: 'visite', decision: 'visite', notes: 'Contacter le vendeur', checks: { acces: { note: 'Document demandé', done: false } }, analysis: buildDossier({ objective: 'visite' }), savedAt: '2026-09-05' });
  assert.match(content, /Décision personnelle : Visite prévue/);
  assert.match(content, /Observation \/ référence : Document demandé/);
  assert.match(content, /ne valide ni un prix ni une faisabilité/);
});
