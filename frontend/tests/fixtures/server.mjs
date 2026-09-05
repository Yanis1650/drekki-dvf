// Local UI verification only. Never imported by the application or Vite build.
import { createServer } from 'node:http';
const mutations = Array.from({ length: 12 }, (_, i) => ({ mutation: {
  id_mutation: `demo-${i}`, parcelles: [`35238000AB${String(i + 1).padStart(4, '0')}`],
  date_mutation: `${2021 + i % 6}-03-15`, nature_mutation: 'Vente',
  prix_m2: i === 0 ? null : i === 1 ? '15000' : String(2500 + i * 100),
  valeur_fonciere: String(200000 + i * 10000), type_local: i % 2 ? 'Maison' : 'Appartement',
  code_commune: '35238', longitude: -1.6778 + (i % 4 - 1.5) * .001,
  latitude: 48.1173 + (Math.floor(i / 4) - 1) * .001, is_outlier: i === 1,
}, enrichment: null }));
createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'content-type');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') { res.end(); return; }
  const url = new URL(req.url, 'http://localhost');
  let data;
  if (url.pathname.endsWith('/search/enriched')) {
    const from = url.searchParams.get('date_from') || '', to = url.searchParams.get('date_to') || '9999';
    const filtered = mutations.filter(m => m.mutation.date_mutation >= from && m.mutation.date_mutation <= to);
    data = { mutations: filtered, enrichment_available: false, mutations_count: filtered.length };
  } else if (url.pathname.endsWith('/densification/top')) {
    data = { commune: '35238', opportunities: [
      { id_parcelle: '35238000AB0001', surface_constructible_restante: 124, categorie: 'FORT' },
      { id_parcelle: '35238000AB0002', surface_constructible_restante: 80, categorie: 'MOYEN' },
    ] };
  } else if (url.pathname.endsWith('/parcelles')) {
    data = { type: 'FeatureCollection', features: [] };
  } else if (url.pathname.endsWith('/history')) {
    data = { transactions: [{ date: '2025-03-15', price_m2: 3100, price: 248000 }] };
  } else if (url.pathname.endsWith('/fiche')) {
    data = { id_parcelle: '35238000AB0001', ces_actuel: null, ces_potentiel: null };
  } else { res.statusCode = 503; data = { error: 'data_unavailable', dataset: 'demo' }; }
  res.end(JSON.stringify(data));
}).listen(8010, '127.0.0.1', () => console.log('FICTITIOUS UI fixtures: http://127.0.0.1:8010'));
