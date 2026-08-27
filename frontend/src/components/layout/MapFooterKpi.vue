<script setup>
import { computed } from 'vue';

const props = defineProps({
  transactions: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] }),
  },
});

const features = computed(() => props.transactions?.features ?? []);

const stats = computed(() => {
  const all = features.value;
  if (all.length === 0) return null;

  // Prix moyen hors valeurs aberrantes, comme partout ailleurs dans l'appli.
  const outliers = all.filter(f => f.properties.is_outlier).length;
  const prices = all
    .filter(f => !f.properties.is_outlier)
    .map(f => f.properties.prix_m2)
    .filter(p => p > 0);
  const avgPrice = prices.length > 0
    ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length)
    : 0;

  const dates = all
    .map(f => f.properties.date_mutation)
    .filter(Boolean)
    .sort()
    .reverse();
  const lastDate = dates[0]
    ? new Date(dates[0]).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })
    : 'N/A';

  return { avgPrice, count: all.length, outliers, lastDate };
});

const fmt = (v) =>
  new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(v);
</script>

<template>
  <div
    v-if="stats"
    class="h-16 flex-shrink-0 flex items-center px-5 gap-5
     bg-surface border-t border-rule"
  >
    <!-- Prix m² moyen -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded bg-accent-soft flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-semibold uppercase tracking-wider text-ink-3 leading-none mb-0.5">Prix m² moy.</p>
        <p class="text-body font-semibold text-ink tabular-nums leading-none">{{ fmt(stats.avgPrice) }}</p>
      </div>
    </div>

    <div class="w-px h-7 bg-surface-2"></div>

    <!-- Nb transactions -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded bg-accent-soft flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-semibold uppercase tracking-wider text-ink-3 leading-none mb-0.5">Transactions</p>
        <p class="text-body font-semibold text-ink tabular-nums leading-none">{{ stats.count }}</p>
      </div>
    </div>

    <div class="w-px h-7 bg-surface-2"></div>

    <!-- Valeurs aberrantes exclues du prix moyen -->
    <div
      class="flex items-center gap-2.5"
      title="Transactions au prix/m² aberrant, exclues du prix moyen"
    >
      <div class="w-7 h-7 rounded bg-warn-soft flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-warn" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 9v2m0 4h.01M5.07 19h13.86a2 2 0 001.74-3L13.74 4a2 2 0 00-3.48 0L3.33 16a2 2 0 001.74 3z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-semibold uppercase tracking-wider text-ink-3 leading-none mb-0.5">Aberrantes</p>
        <p class="text-body font-semibold text-ink tabular-nums leading-none">{{ stats.outliers }}</p>
      </div>
    </div>

    <div class="w-px h-7 bg-surface-2"></div>

    <!-- Dernière vente -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded bg-accent-soft flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-semibold uppercase tracking-wider text-ink-3 leading-none mb-0.5">Dernière vente</p>
        <p class="text-body font-semibold text-ink leading-none">{{ stats.lastDate }}</p>
      </div>
    </div>
  </div>
</template>
