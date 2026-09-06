import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parse, compileScript } from '@vue/compiler-sfc';
import { createSSRApp } from 'vue';
import { renderToString } from '@vue/server-renderer';
import { summarize } from '../src/domain/market.js';

// Compile real Vue templates, then assert their accessible/user-visible output.
async function componentUrl(url) {
  const { descriptor } = parse(await readFile(url, 'utf8'));
  const result = compileScript(descriptor, { id: 'test-component', inlineTemplate: true });
  let code = result.content;
  for (const match of [...code.matchAll(/from (["'])([^"']+)\1/g)]) {
    const name = match[2];
    const resolved = name.endsWith('.vue') ? await componentUrl(new URL(name, url)) : name.startsWith('.') ? new URL(name, url).href : import.meta.resolve(name);
    code = code.replace(match[0], `from ${JSON.stringify(resolved)}`);
  }
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`;
}
async function render(path, props) {
  const { default: component } = await import(await componentUrl(new URL(path, import.meta.url)));
  return renderToString(createSSRApp(component, props));
}
test('status renders retry and accessible error, not success metadata', async () => {
  const html = await render('../src/components/StudyStatus.vue', { status: 'error', error: 'NON RELEVÉ', stats: summarize({ features: [] }) });
  assert.match(html, /role="alert"/);
  assert.match(html, /Réessayer/);
  assert.doesNotMatch(html, /Source : DVF/);
});

test('multicriteria starts without a fabricated score or risk finding', async () => {
  const { cleanCriteria } = await import('../src/domain/multicriteria.js');
  const html = await render('../src/components/parcel/MulticriteriaAnalysis.vue', { modelValue: cleanCriteria(), objective: 'potentiel', facts: [] });
  assert.match(html, /Analyse à compléter/);
  assert.match(html, /Données NON RELEVÉES/);
  assert.match(html, /Les critères non évalués élargissent la fourchette/);
  assert.doesNotMatch(html, /Très favorable/);
});
test('quality disclosure warns about cap, sample and unavailable provenance', async () => {
  const html = await render('../src/components/StudyStatus.vue', { status: 'ready', capped: true, stats: summarize({ features: [] }), enrichmentAvailable: false });
  assert.match(html, /potentiellement incomplet/);
  assert.match(html, /Échantillon de prix faible/);
  assert.match(html, /non fournis par cette API/);
});
test('KPI component presents missing prices without a zero euro estimate', async () => {
  const html = await render('../src/components/layout/MapFooterKpi.vue', { transactions: { features: [] } });
  assert.match(html, /NON RELEVÉ/);
  assert.doesNotMatch(html, /0\s*€/);
});
test('parcel never substitutes sector price for unavailable parcel price', async () => {
  const html = await render('../src/components/parcel/ParcelStats.vue', { transactionCount: 0, avgPriceM2: null, sectorAvgPriceM2: 3000, lastSaleDate: 'NON RELEVÉ', historyAvailable: false });
  assert.match(html, /Prix moyen parcelle \/ m²<\/dt><dd class="fe-estimated">NON RELEVÉ/);
  assert.match(html, /Prix moyen secteur/);
});
test('shared dossier presents objectives, traceable questions and local storage limits', async () => {
  const html = await render('../src/components/parcel/DecisionDossier.vue', { parcelId: '35238000AB0001', transactions: [], historyAvailable: false });
  assert.match(html, /Étudier le potentiel/);
  assert.match(html, /Préparer une visite/);
  assert.match(html, /Pourquoi cette question/);
  assert.match(html, /sans compte ni synchronisation/);
  assert.match(html, /ne permettent pas de conclure/);
});
