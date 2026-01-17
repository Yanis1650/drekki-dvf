<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  data: {
    type: Array,
    required: true,
    default: () => []
  },
  dates: {
    type: Array,
    default: () => []
  },
  color: {
    type: String,
    default: '#6366f1' // Indigo
  },
  height: {
    type: Number,
    default: 40
  }
});

// ApexCharts options for sparkline
const chartOptions = computed(() => ({
  chart: {
    type: 'line',
    sparkline: {
      enabled: true // No axes, no labels, minimal chart
    },
    animations: {
      enabled: true,
      easing: 'easeinout',
      speed: 600
    }
  },
  stroke: {
    curve: 'smooth',
    width: 2
  },
  colors: [props.color],
  fill: {
    type: 'gradient',
    gradient: {
      shade: 'light',
      type: 'vertical',
      shadeIntensity: 0.3,
      gradientToColors: [props.color],
      opacityFrom: 0.4,
      opacityTo: 0.1,
      stops: [0, 100]
    }
  },
  tooltip: {
    enabled: true,
    theme: 'light',
    x: {
      show: props.dates.length > 0,
      formatter: (val, opts) => {
        if (props.dates.length > 0 && opts.dataPointIndex < props.dates.length) {
          return props.dates[opts.dataPointIndex];
        }
        return '';
      }
    },
    y: {
      formatter: (val) => {
        return val ? `${val.toFixed(0)} €/m²` : '';
      }
    },
    style: {
      fontSize: '11px',
      fontFamily: 'Inter, sans-serif'
    }
  },
  markers: {
    size: 0,
    hover: {
      size: 4,
      sizeOffset: 2
    }
  }
}));

const series = computed(() => [{
  name: 'Prix/m²',
  data: props.data
}]);
</script>

<template>
  <div class="sparkline-chart">
    <apexchart
      v-if="data.length > 0"
      type="line"
      :height="height"
      :options="chartOptions"
      :series="series"
    />
    <div v-else class="no-data">
      <span class="text-xs text-slate-400">Pas de données</span>
    </div>
  </div>
</template>

<style scoped>
.sparkline-chart {
  width: 100%;
  min-height: 40px;
}

.no-data {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
