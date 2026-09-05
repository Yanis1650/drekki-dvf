// Shared DVF contract: missing values remain missing, one feature per mutation.
export const emptyCollection = () => ({ type: 'FeatureCollection', features: [] });
export function numberOrNull(value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
export function normalizeSearch(data) {
  if (!Array.isArray(data?.mutations)) throw new Error('Invalid search response');
  const seen = new Set();
  return { type: 'FeatureCollection', features: data.mutations.flatMap(({ mutation: m, enrichment }) => {
    if (!m?.id_mutation) throw new Error('Missing mutation identifier');
    if (seen.has(m.id_mutation)) return [];
    seen.add(m.id_mutation);
    const lon = numberOrNull(m.longitude), lat = numberOrNull(m.latitude);
    return [{ type: 'Feature', id: m.id_mutation,
      geometry: lon != null && lat != null && Math.abs(lon) <= 180 && Math.abs(lat) <= 90
        ? { type: 'Point', coordinates: [lon, lat] } : null,
      properties: { ...m, id_parcelle: m.parcelles?.[0] ?? null,
        prix_m2: numberOrNull(m.prix_m2), valeur_fonciere: numberOrNull(m.valeur_fonciere),
        scores: enrichment ?? null } }];
  }) };
}
export function summarize(collection) {
  const all = collection?.features ?? [];
  const prices = all.filter(f => !f.properties.is_outlier).map(f => f.properties.prix_m2)
    .filter(p => Number.isFinite(p) && p > 0).sort((a, b) => a - b);
  const quantile = q => {
    if (!prices.length) return null;
    const i = (prices.length - 1) * q, lo = Math.floor(i);
    return prices[lo] + (prices[Math.ceil(i)] - prices[lo]) * (i - lo);
  };
  const dates = all.map(f => f.properties.date_mutation).filter(Boolean).sort();
  return { count: all.length, priced: prices.length,
    avgPrice: prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null,
    median: quantile(.5), q1: quantile(.25), q3: quantile(.75),
    outliers: all.filter(f => f.properties.is_outlier).length,
    unmapped: all.filter(f => !f.geometry).length,
    firstDate: dates[0], lastDate: dates.at(-1) };
}
export function annualTrends(collection) {
  const groups = new Map();
  for (const f of collection.features) {
    const year = f.properties.date_mutation?.slice(0, 4);
    if (!/^\d{4}$/.test(year ?? '')) continue;
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(f);
  }
  return [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([year, features]) => ({
    year, avg_price_m2: summarize({ features }).avgPrice, priced_count: summarize({ features }).priced, transaction_volume: features.length,
  }));
}
export function describeError(error) {
  const code = error?.response?.data?.error;
  if (code === 'data_unavailable') return 'NON RELEVÉ — jeu de données indisponible pour cette recherche.';
  if (code === 'spatial_unavailable') return 'Recherche géographique temporairement indisponible.';
  return 'Les données n’ont pas pu être chargées. Réessayez.';
}
export const money = value => value == null ? 'NON RELEVÉ' : new Intl.NumberFormat('fr-FR', {
  style: 'currency', currency: 'EUR', maximumFractionDigits: 0,
}).format(value);
