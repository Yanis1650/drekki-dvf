<script setup>
import { computed } from 'vue';
import apexchart from 'vue3-apexcharts';
import { token } from '../styles/tokens';

/**
 * Évolution du marché : prix médian au m² et volume de ventes.
 *
 * Les deux séries étaient superposées sur deux axes verticaux distincts. Un
 * double axe laisse choisir arbitrairement l'échelle de chacun, donc la forme
 * de leur croisement : on peut lui faire dire à peu près n'importe quoi. Elles
 * sont désormais empilées sur un axe des années commun — la comparaison reste
 * immédiate, sans que le graphique n'affirme de corrélation.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md §6.4
 */
const props = defineProps({
  trends: { type: Array, required: true },
  loading: { type: Boolean, default: false },
});

const chartData = computed(() => {
  if (!props.trends || props.trends.length === 0) {
    return { years: [], prices: [], volumes: [] };
  }
  return {
    years: props.trends.map((t) => t.year),
    prices: props.trends.map((t) => parseFloat(t.avg_price_m2)),
    volumes: props.trends.map((t) => t.transaction_volume),
  };
});

/** Effectif total : une série agrégée ne se présente jamais sans son effectif. */
const totalVentes = computed(() =>
  chartData.value.volumes.reduce((sum, v) => sum + (Number(v) || 0), 0),
);

const axeX = () => ({
  categories: chartData.value.years,
  labels: { style: { colors: token('--fe-ink-3'), fontSize: '11px' } },
  axisBorder: { show: false },
  axisTicks: { show: false },
});

const grille = () => ({
  borderColor: token('--fe-rule'),
  strokeDashArray: 0,
  xaxis: { lines: { show: false } },
  yaxis: { lines: { show: true } },
});

const prixOptions = computed(() => ({
  chart: {
    type: 'area',
    height: 220,
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeout', speed: 300 },
    background: 'transparent',
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  colors: [token('--fe-ramp-4')],
  stroke: { width: 2, curve: 'straight' },
  fill: { type: 'solid', opacity: 0.14 },
  markers: { size: 3, strokeWidth: 0, hover: { size: 5 } },
  dataLabels: { enabled: false },
  xaxis: axeX(),
  yaxis: {
    labels: {
      style: { colors: token('--fe-ink-3'), fontSize: '11px' },
      formatter: (v) => (v ? `${Math.round(v).toLocaleString('fr-FR')} €` : '—'),
    },
  },
  grid: grille(),
  tooltip: {
    theme: 'light',
    y: { formatter: (v) => `${Math.round(v).toLocaleString('fr-FR')} €/m²` },
  },
  legend: { show: false },
}));

const volumeOptions = computed(() => ({
  chart: {
    type: 'bar',
    height: 130,
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeout', speed: 300 },
    background: 'transparent',
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  colors: [token('--fe-ramp-2')],
  plotOptions: { bar: { columnWidth: '45%', borderRadius: 2, borderRadiusApplication: 'end' } },
  dataLabels: { enabled: false },
  xaxis: axeX(),
  yaxis: {
    labels: { style: { colors: token('--fe-ink-3'), fontSize: '11px' } },
    tickAmount: 3,
  },
  grid: grille(),
  tooltip: { theme: 'light', y: { formatter: (v) => `${v} ventes` } },
  legend: { show: false },
}));

const prixSeries = computed(() => [{ name: 'Prix médian/m²', data: chartData.value.prices }]);
const volumeSeries = computed(() => [{ name: 'Ventes', data: chartData.value.volumes }]);
</script>

<template>
  <div class="w-full">
    <div v-if="loading" class="flex items-center justify-center h-80">
      <div class="w-8 h-8 rounded-full border-2 border-rule border-t-accent animate-spin"></div>
    </div>

    <div v-else-if="trends && trends.length > 0" class="flex flex-col gap-4">
      <div>
        <div class="flex items-baseline justify-between mb-1">
          <span class="fe-label">Prix médian au m²</span>
          <span class="fe-meta tabular-nums">n = {{ totalVentes.toLocaleString('fr-FR') }} ventes</span>
        </div>
        <apexchart type="area" height="220" :options="prixOptions" :series="prixSeries" />
      </div>

      <div>
        <span class="fe-label">Volume de ventes</span>
        <apexchart type="bar" height="130" :options="volumeOptions" :series="volumeSeries" />
      </div>
    </div>

    <!-- Absence de donnée : nommée, jamais remplacée par un graphique à zéro. -->
    <div v-else class="flex flex-col items-center justify-center h-80 gap-2">
      <span class="absent">NON RELEVÉ</span>
      <p class="fe-meta">Aucune série historique pour ce secteur</p>
    </div>
  </div>
</template>
