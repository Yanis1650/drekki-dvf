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

  const prices = all.map(f => f.properties.prix_m2).filter(p => p > 0);
  const avgPrice = prices.length > 0
    ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length)
    : 0;

  const zanFort = all.filter(f =>
    f.properties.scores?.zan_category === 'FORT'
  ).length;
  const zanPct = Math.round((zanFort / all.length) * 100);

  const dates = all
    .map(f => f.properties.date_mutation)
    .filter(Boolean)
    .sort()
    .reverse();
  const lastDate = dates[0]
    ? new Date(dates[0]).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })
    : 'N/A';

  return { avgPrice, count: all.length, zanPct, lastDate };
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
           bg-white/92 backdrop-blur-xl border-t border-white/60
           shadow-[0_-4px_20px_rgba(0,0,0,0.06)]"
    style="background: rgba(255,255,255,0.92);"
  >
    <!-- Prix m² moyen -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-sage-50 flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-sage-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">Prix m² moy.</p>
        <p class="text-sm font-bold text-slate-800 tabular-nums leading-none">{{ fmt(stats.avgPrice) }}</p>
      </div>
    </div>

    <div class="w-px h-7 bg-slate-200"></div>

    <!-- Nb transactions -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">Transactions</p>
        <p class="text-sm font-bold text-slate-800 tabular-nums leading-none">{{ stats.count }}</p>
      </div>
    </div>

    <div class="w-px h-7 bg-slate-200"></div>

    <!-- Potentiel ZAN -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">Fort ZAN</p>
        <p class="text-sm font-bold text-slate-800 tabular-nums leading-none">{{ stats.zanPct }}%</p>
      </div>
    </div>

    <div class="w-px h-7 bg-slate-200"></div>

    <!-- Dernière vente -->
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center flex-shrink-0">
        <svg class="w-3.5 h-3.5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <div>
        <p class="text-[9px] font-bold uppercase tracking-wider text-slate-400 leading-none mb-0.5">Dernière vente</p>
        <p class="text-sm font-bold text-slate-800 leading-none">{{ stats.lastDate }}</p>
      </div>
    </div>
  </div>
</template>
