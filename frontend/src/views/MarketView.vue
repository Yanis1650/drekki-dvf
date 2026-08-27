<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import MarketTrendsChart from '../components/MarketTrendsChart.vue';
import client from '../api/client';

const props = defineProps({
  transactions: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  center:        { type: Array,  default: () => [-1.6778, 48.1173] },
});

const trendData    = ref(null);
const loadingTrend = ref(false);

const features = computed(() => props.transactions?.features ?? []);

// ─── KPIs ────────────────────────────────────────────────────────────────────
const kpis = computed(() => {
  const all = features.value;
  if (all.length === 0) return null;

  const prices = all.map(f => f.properties.prix_m2).filter(p => p > 0);
  const avgPrice = prices.length > 0
    ? Math.round(prices.reduce((a, b) => a + b, 0) / prices.length)
    : 0;

  const zanFort = all.filter(f => f.properties.scores?.zan_category === 'FORT').length;
  const zanPct  = Math.round((zanFort / all.length) * 100);

  const totalVal = all.reduce((a, f) => a + (f.properties.valeur_fonciere || 0), 0);

  // type breakdown
  const byType = all.reduce((acc, f) => {
    const t = f.properties.type_local || 'Autre';
    acc[t] = (acc[t] || 0) + 1;
    return acc;
  }, {});

  return { count: all.length, avgPrice, zanPct, totalVal, byType };
});

// ─── Recent transactions ──────────────────────────────────────────────────────
const recentTransactions = computed(() =>
  [...features.value]
    .filter(f => f.properties.date_mutation)
    .sort((a, b) =>
      new Date(b.properties.date_mutation) - new Date(a.properties.date_mutation)
    )
    .slice(0, 15)
);

// ─── Trend fetch ──────────────────────────────────────────────────────────────
const fetchTrends = async () => {
  if (!props.center) return;
  loadingTrend.value = true;
  try {
    const res = await client.get('/analytics/trends', {
      params: {
        lat: props.center[1],
        lon: props.center[0],
        radius: 5000,
        years: 10,
      },
    });
    trendData.value = res.data;
  } catch {
    trendData.value = null;
  } finally {
    loadingTrend.value = false;
  }
};

onMounted(fetchTrends);
watch(() => props.center, fetchTrends, { deep: true });

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmtPrice = (v) =>
  new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(v);

const fmtNumber = (v) => new Intl.NumberFormat('fr-FR').format(v);
</script>

<template>
  <div class="absolute inset-0 overflow-auto bg-surface-2 custom-scrollbar">
    <div class="max-w-5xl mx-auto px-6 py-6 space-y-6">

      <!-- Header -->
      <div>
        <h1 class="text-title font-semibold text-ink tracking-tight">Analyse de marché</h1>
        <p class="text-body text-ink-3 mt-0.5">
          <template v-if="features.length > 0">
            {{ fmtNumber(features.length) }} transactions chargées dans la zone courante
          </template>
          <template v-else>
            Recherchez une adresse pour charger les données de la zone
          </template>
        </p>
      </div>

      <!-- KPI Cards -->
      <div v-if="kpis" class="grid grid-cols-2 xl:grid-cols-4 gap-4">

        <!-- Prix m² -->
        <div class="cartouche p-5">
          <div class="flex items-center gap-2 mb-3">
            <div class="w-7 h-7 rounded bg-accent-soft flex items-center justify-center">
              <svg class="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span class="text-meta font-semibold uppercase tracking-wider text-ink-3">Prix m² moyen</span>
          </div>
          <p class="text-title font-semibold text-ink tabular-nums">{{ fmtPrice(kpis.avgPrice) }}</p>
          <div class="mt-3 h-1 bg-surface-2 rounded-full overflow-hidden">
            <div class="h-full bg-ramp-4 rounded-full" style="width: 65%"></div>
          </div>
        </div>

        <!-- Transactions -->
        <div class="cartouche p-5">
          <div class="flex items-center gap-2 mb-3">
            <div class="w-7 h-7 rounded bg-accent-soft flex items-center justify-center">
              <svg class="w-3.5 h-3.5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <span class="text-meta font-semibold uppercase tracking-wider text-ink-3">Transactions</span>
          </div>
          <p class="text-title font-semibold text-ink tabular-nums">{{ fmtNumber(kpis.count) }}</p>
          <p class="text-meta text-ink-3 mt-3">dans la zone chargée</p>
        </div>

        <!-- ZAN -->
        <div class="cartouche p-5">
          <div class="flex items-center gap-2 mb-3">
            <div class="w-7 h-7 rounded bg-ramp-1 flex items-center justify-center">
              <svg class="w-3.5 h-3.5 text-ramp-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <span class="text-meta font-semibold uppercase tracking-wider text-ink-3">Fort potentiel ZAN</span>
          </div>
          <p class="text-title font-semibold text-ramp-5 tabular-nums">{{ kpis.zanPct }}%</p>
          <div class="mt-3 h-1 bg-surface-2 rounded-full overflow-hidden">
            <div
              class="h-full bg-ramp-4 rounded-full transition-all duration-700"
              :style="{ width: kpis.zanPct + '%' }"
            ></div>
          </div>
        </div>

        <!-- Volume total -->
        <div class="cartouche p-5">
          <div class="flex items-center gap-2 mb-3">
            <div class="w-7 h-7 rounded bg-warn-soft flex items-center justify-center">
              <svg class="w-3.5 h-3.5 text-warn" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <span class="text-meta font-semibold uppercase tracking-wider text-ink-3">Volume total</span>
          </div>
          <p class="text-title font-semibold text-ink tabular-nums leading-tight">
            {{ fmtPrice(kpis.totalVal) }}
          </p>
          <p class="text-meta text-ink-3 mt-3">toutes ventes confondues</p>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="cartouche p-16 text-center">
        <div class="w-16 h-16 rounded bg-surface-2 flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-ink-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <p class="text-lead font-semibold text-ink-2">Aucune donnée chargée</p>
        <p class="text-body text-ink-3 mt-1 max-w-xs mx-auto">
          Revenez sur la carte et recherchez une adresse pour charger les transactions de la zone.
        </p>
      </div>

      <!-- Trends Chart -->
      <div class="cartouche p-6">
        <div class="flex items-center justify-between mb-5">
          <h2 class="text-lead font-semibold text-ink">Évolution du marché sur 10 ans</h2>
          <div v-if="loadingTrend" class="flex items-center gap-1.5 text-ink-3 text-meta">
            <div class="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
            Chargement…
          </div>
        </div>
        <MarketTrendsChart
          :trends="trendData?.trends || []"
          :loading="loadingTrend"
        />
      </div>

      <!-- Type breakdown -->
      <div v-if="kpis?.byType" class="cartouche p-6">
        <h2 class="text-lead font-semibold text-ink mb-4">Répartition par type de bien</h2>
        <div class="flex flex-wrap gap-3">
          <div
            v-for="(count, type) in kpis.byType"
            :key="type"
            class="flex items-center gap-2 px-4 py-2.5 rounded bg-surface-2
             border border-rule"
          >
            <span class="text-body font-semibold text-ink-2">{{ type }}</span>
            <span class="px-2 py-0.5 bg-accent-soft text-accent text-meta font-semibold rounded tabular-nums">
              {{ fmtNumber(count) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Recent transactions table -->
      <div v-if="recentTransactions.length > 0" class="cartouche overflow-hidden">
        <div class="px-6 py-4 border-b border-rule">
          <h2 class="text-lead font-semibold text-ink">Transactions récentes</h2>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-body">
            <thead>
              <tr class="bg-surface-2/80">
                <th class="px-6 py-3 text-left text-meta font-semibold uppercase tracking-wider text-ink-3">Date</th>
                <th class="px-6 py-3 text-left text-meta font-semibold uppercase tracking-wider text-ink-3">Type</th>
                <th class="px-6 py-3 text-right text-meta font-semibold uppercase tracking-wider text-ink-3">Valeur</th>
                <th class="px-6 py-3 text-right text-meta font-semibold uppercase tracking-wider text-ink-3">Prix/m²</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-rule">
              <tr
                v-for="t in recentTransactions"
                :key="t.properties.id_mutation"
                class="hover:bg-surface-2/60 transition-colors"
              >
                <td class="px-6 py-3.5 text-ink-2 tabular-nums">
                  {{ new Date(t.properties.date_mutation).toLocaleDateString('fr-FR') }}
                </td>
                <td class="px-6 py-3.5">
                  <span class="px-2 py-0.5 rounded-sm bg-surface-2 text-ink-2 text-meta font-medium">
                    {{ t.properties.type_local || '—' }}
                  </span>
                </td>
                <td class="px-6 py-3.5 text-right font-semibold text-ink tabular-nums">
                  {{ t.properties.valeur_fonciere ? fmtPrice(t.properties.valeur_fonciere) : '—' }}
                </td>
                <td class="px-6 py-3.5 text-right text-ink-3 tabular-nums text-meta">
                  {{ t.properties.prix_m2 ? fmtPrice(t.properties.prix_m2) + '/m²' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>
