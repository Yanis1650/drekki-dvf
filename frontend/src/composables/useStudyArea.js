import { computed, ref } from 'vue';
import { describeError, emptyCollection, normalizeSearch, summarize } from '../domain/market.js';

// Latest request wins, even if the transport ignores cancellation.
export function useStudyArea(client) {
  const center = ref([-1.6778, 48.1173]);
  const label = ref('Rennes');
  const commune = ref('35238');
  const radius = ref(500);
  const recent = ref(false);
  const transactions = ref(emptyCollection());
  const status = ref('idle');
  const error = ref('');
  const capped = ref(false);
  const enrichmentAvailable = ref(null);
  const limit = 1000;
  let version = 0, controller;
  async function refresh() {
    const current = ++version;
    controller?.abort();
    controller = new AbortController();
    transactions.value = emptyCollection();
    capped.value = false;
    enrichmentAvailable.value = null;
    status.value = 'loading';
    error.value = '';
    const params = { lon: center.value[0], lat: center.value[1], radius: radius.value, limit };
    if (recent.value) {
      const date = new Date();
      params.date_to = date.toISOString().slice(0, 10);
      date.setUTCFullYear(date.getUTCFullYear() - 2);
      params.date_from = date.toISOString().slice(0, 10);
    }
    try {
      const { data } = await client.get('/land/search/enriched', { params, signal: controller.signal });
      if (current !== version) return;
      transactions.value = normalizeSearch(data);
      capped.value = data.mutations.length >= limit;
      enrichmentAvailable.value = data.enrichment_available ?? null;
      status.value = transactions.value.features.length ? 'ready' : 'empty';
    } catch (err) {
      if (current !== version) return;
      error.value = describeError(err);
      status.value = 'error';
    }
  }
  function dispose() { version++; controller?.abort(); }
  return { center, label, commune, radius, recent, transactions, status, error, capped,
    enrichmentAvailable, refresh, dispose, stats: computed(() => summarize(transactions.value)) };
}
