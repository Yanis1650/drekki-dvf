<script setup>
import { computed } from 'vue';
import VueApexCharts from 'vue3-apexcharts';
import { token } from '../../styles/tokens';

const props = defineProps({
  transactions: { type: Array, default: () => [] },
});

const sortedTransactions = computed(() =>
  [...props.transactions]
    .filter((tx) => tx.date && tx.price_m2)
    .sort((a, b) => new Date(a.date) - new Date(b.date)),
);

const series = computed(() => [{
  name: 'Prix au m²',
  data: sortedTransactions.value.map((tx) => ({
    x: new Date(tx.date).getTime(),
    y: Math.round(tx.price_m2),
  })),
}]);

const chartOptions = computed(() => ({
  chart: {
    type: 'area',
    height: 200,
    toolbar: { show: false },
    animations: { enabled: true, easing: 'easeout', speed: 300 },
    background: 'transparent',
    fontFamily: 'IBM Plex Sans, sans-serif',
  },
  colors: [token('--fe-ramp-4')],
  // Aplat léger plutôt qu'un dégradé : le dégradé ne code rien.
  fill: { type: 'solid', opacity: 0.14 },
  stroke: { curve: 'straight', width: 2 },
  dataLabels: { enabled: false },
  xaxis: {
    type: 'datetime',
    labels: { style: { colors: token('--fe-ink-3'), fontSize: '11px' } },
    axisBorder: { show: false },
    axisTicks: { show: false },
  },
  yaxis: {
    labels: {
      formatter: (val) => `${Math.round(val).toLocaleString('fr-FR')} €`,
      style: { colors: token('--fe-ink-3'), fontSize: '11px' },
    },
  },
  grid: {
    borderColor: token('--fe-rule'),
    strokeDashArray: 0,
    padding: { left: 8, right: 8 },
  },
  tooltip: {
    theme: 'light',
    x: { format: 'dd MMM yyyy' },
    y: { formatter: (val) => `${val.toLocaleString('fr-FR')} €/m²` },
  },
  markers: { size: 3, strokeWidth: 0, hover: { size: 5 } },
}));
</script>

<template>
  <section class="cartouche">
    <div class="cartouche__bar">
      <span class="fe-label">Évolution des prix</span>
      <span class="fe-meta ml-auto tabular-nums">n = {{ transactions.length }} ventes</span>
    </div>

    <div v-if="sortedTransactions.length > 0" class="cartouche__body">
      <VueApexCharts type="area" height="200" :options="chartOptions" :series="series" />
    </div>

    <div v-else class="cartouche__body flex justify-center">
      <span class="absent">NON RELEVÉ</span>
    </div>

    <div class="cartouche__source">DVF 2014-2025 · prix au m² observés sur la parcelle</div>
  </section>
</template>
