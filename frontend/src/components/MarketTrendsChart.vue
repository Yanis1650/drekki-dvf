<script setup>
/**
 * Évolution du marché : prix médian au m² et volume de ventes.
 *
 * Les deux séries étaient superposées sur deux axes verticaux distincts. Un
 * double axe laisse choisir arbitrairement l'échelle de chacun, donc la forme
 * de leur croisement : on peut lui faire dire à peu près n'importe quoi. Elles
 * sont désormais empilées sur un axe des années commun — la comparaison reste
 * immédiate, sans que le graphique n'affirme de corrélation.
 *
 * Chaque point porte sa valeur écrite. Une courbe dont on doit survoler les
 * points pour les lire n'est pas lisible à l'impression, ni au clavier.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md §6.4 · docs/design/frontend-concept.png
 */
import { computed } from 'vue';
import apexchart from 'vue3-apexcharts';
import { token } from '../styles/tokens';

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
    prices: props.trends.map((t) => (t.median_price_m2 == null ? null : Number(t.median_price_m2))),
    volumes: props.trends.map((t) => t.transaction_volume),
  };
});

const totalVentes = computed(() =>
  chartData.value.volumes.reduce((sum, v) => sum + (Number(v) || 0), 0),
);
const totalPrices = computed(() =>
  props.trends.reduce((sum, t) => sum + (t.priced_count || 0), 0),
);

const euro = (v) => `${Math.round(v).toLocaleString('fr-FR')} €`;

const axeX = () => ({
  categories: chartData.value.years,
  labels: { style: { colors: token('--fe-ink-3'), fontSize: '11px' } },
  axisBorder: { show: false },
  axisTicks: { show: false },
  tooltip: { enabled: false },
});

const grille = () => ({
  borderColor: token('--fe-rule'),
  strokeDashArray: 0,
  padding: { top: 16, right: 8 },
  xaxis: { lines: { show: false } },
  yaxis: { lines: { show: true } },
});

const etiquettes = (formatter) => ({
  enabled: true,
  formatter,
  offsetY: -6,
  style: { fontSize: '11px', fontWeight: 500, colors: [token('--fe-ink-2')] },
  background: { enabled: false },
});

const prixOptions = computed(() => ({
  chart: {
    type: 'area',
    height: 240,
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeout', speed: 300 },
    background: 'transparent',
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  colors: [token('--fe-ramp-4')],
  stroke: { width: 2, curve: 'straight' },
  fill: { type: 'solid', opacity: 0.14 },
  markers: { size: 4, strokeWidth: 2, strokeColors: token('--fe-surface'), hover: { size: 6 } },
  dataLabels: etiquettes((v) => (v == null ? '' : euro(v))),
  xaxis: axeX(),
  yaxis: {
    labels: {
      style: { colors: token('--fe-ink-3'), fontSize: '11px' },
      formatter: (v) => (v ? euro(v) : '—'),
    },
  },
  grid: grille(),
  tooltip: { theme: 'light', y: { formatter: (v) => `${euro(v)}/m²` } },
  legend: { show: false },
}));

const volumeOptions = computed(() => ({
  chart: {
    type: 'bar',
    height: 150,
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeout', speed: 300 },
    background: 'transparent',
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  colors: [token('--fe-ramp-3')],
  plotOptions: { bar: { columnWidth: '42%', borderRadius: 2, borderRadiusApplication: 'end' } },
  dataLabels: etiquettes((v) => String(v)),
  xaxis: axeX(),
  yaxis: {
    labels: { style: { colors: token('--fe-ink-3'), fontSize: '11px' } },
    tickAmount: 3,
  },
  grid: grille(),
  tooltip: { theme: 'light', y: { formatter: (v) => `${v} mutations` } },
  legend: { show: false },
}));

const prixSeries = computed(() => [{ name: 'Prix médian au m²', data: chartData.value.prices }]);
const volumeSeries = computed(() => [{ name: 'Mutations', data: chartData.value.volumes }]);
</script>

<template>
  <div class="w-full">
    <div v-if="loading" class="flex items-center justify-center h-80">
      <div class="w-8 h-8 rounded-full border-2 border-rule border-t-accent animate-spin"></div>
    </div>

    <div v-else-if="trends && trends.length > 0" class="flex flex-col gap-5">
      <section>
        <div class="flex items-baseline justify-between gap-3 flex-wrap">
          <h3 class="text-lead">Évolution du prix médian au m²</h3>
          <p class="fe-meta flex items-center gap-2">
            <span class="w-3 h-[2px] rounded-sm" style="background: var(--fe-ramp-4)" aria-hidden="true"></span>
            Prix médian au m²
          </p>
        </div>
        <p class="fe-meta">{{ totalPrices.toLocaleString('fr-FR') }} prix exploitables · valeurs aberrantes exclues</p>
        <apexchart type="area" height="240" :options="prixOptions" :series="prixSeries" />
      </section>

      <section>
        <div class="flex items-baseline justify-between gap-3 flex-wrap">
          <h3 class="text-lead">Volumes de ventes (mutations)</h3>
          <p class="fe-meta flex items-center gap-2">
            <span class="w-3 h-3 rounded-sm" style="background: var(--fe-ramp-3)" aria-hidden="true"></span>
            Mutations
          </p>
        </div>
        <p class="fe-meta">{{ totalVentes.toLocaleString('fr-FR') }} mutations dans l’échantillon chargé</p>
        <apexchart type="bar" height="150" :options="volumeOptions" :series="volumeSeries" />
      </section>
    </div>

    <!-- Absence de donnée : nommée, jamais remplacée par un graphique à zéro. -->
    <div v-else class="flex flex-col items-center justify-center h-80 gap-2">
      <span class="absent">NON RELEVÉ</span>
      <p class="fe-meta">Aucune série annuelle dans l’échantillon chargé</p>
    </div>
  </div>
</template>
