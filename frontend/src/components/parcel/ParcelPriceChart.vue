<script setup>
import { computed } from 'vue';
import VueApexCharts from 'vue3-apexcharts';

const props = defineProps({
  transactions: {
    type: Array,
    default: () => []
  }
});

const sortedTransactions = computed(() => {
  return [...props.transactions]
    .filter(tx => tx.date && tx.price_m2)
    .sort((a, b) => new Date(a.date) - new Date(b.date));
});

const series = computed(() => [{
  name: 'Prix au m²',
  data: sortedTransactions.value.map(tx => ({
    x: new Date(tx.date).getTime(),
    y: Math.round(tx.price_m2)
  }))
}]);

const chartOptions = computed(() => ({
  chart: {
    type: 'area',
    height: 200,
    toolbar: { show: false },
    animations: {
      enabled: true,
      easing: 'easeinout',
      speed: 800
    },
    fontFamily: 'DM Sans, sans-serif'
  },
  colors: ['#527f8c'],
  fill: {
    type: 'gradient',
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.7,
      opacityTo: 0.2,
      stops: [0, 90, 100]
    }
  },
  stroke: { 
    curve: 'smooth', 
    width: 3 
  },
  dataLabels: { enabled: false },
  xaxis: { 
    type: 'datetime',
    labels: {
      style: {
        colors: '#64748b',
        fontSize: '11px'
      }
    },
    axisBorder: { show: false },
    axisTicks: { show: false }
  },
  yaxis: {
    labels: {
      formatter: (val) => `${val.toFixed(0)} €`,
      style: {
        colors: '#64748b',
        fontSize: '11px'
      }
    }
  },
  grid: {
    borderColor: '#e2e8f0',
    strokeDashArray: 4,
    padding: { left: 10, right: 10 }
  },
  tooltip: {
    theme: 'dark',
    x: { format: 'dd MMM yyyy' },
    y: { formatter: (val) => `${val} €/m²` }
  },
  markers: {
    size: 4,
    colors: ['#527f8c'],
    strokeWidth: 2,
    hover: { size: 6 }
  }
}));
</script>

<template>
  <div class="chart-section">
    <h3 class="section-title">
      📈 Évolution des prix 
      <span class="count-badge">{{ transactions.length }} ventes</span>
    </h3>
    
    <div v-if="sortedTransactions.length > 0" class="chart-container">
      <VueApexCharts
        type="area"
        height="200"
        :options="chartOptions"
        :series="series"
      />
    </div>
    
    <div v-else class="empty-state">
      <p>Pas de données de prix disponibles</p>
    </div>
  </div>
</template>

<style scoped>
.chart-section {
  background: #f8fafc;
  border-radius: 16px;
  padding: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-badge {
  font-size: 11px;
  font-weight: 600;
  color: #527f8c;
  background: rgba(82, 127, 140, 0.1);
  padding: 4px 10px;
  border-radius: 12px;
}

.chart-container {
  margin: 0 -8px;
}

.empty-state {
  text-align: center;
  padding: 32px;
  color: #94a3b8;
  font-size: 14px;
}
</style>
