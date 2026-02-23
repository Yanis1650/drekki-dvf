<script setup>
import { computed } from 'vue';
import { ChartBarIcon } from '@heroicons/vue/24/solid';
import apexchart from 'vue3-apexcharts';

const props = defineProps({
  trends: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
});

// Prepare chart data
const chartData = computed(() => {
  if (!props.trends || props.trends.length === 0) {
    return { years: [], prices: [], volumes: [] };
  }

  return {
    years: props.trends.map(t => t.year),
    prices: props.trends.map(t => parseFloat(t.avg_price_m2)),
    volumes: props.trends.map(t => t.transaction_volume)
  };
});

// Line + Bar chart configuration (ApexCharts)
const chartOptions = computed(() => ({
  chart: {
    type: 'line',
    height: 350,
    toolbar: {
      show: false
    },
    animations: {
      enabled: true,
      easing: 'easeinout',
      speed: 800,
      animateGradually: {
        enabled: true,
        delay: 150
      }
    },
    background: 'transparent',
    fontFamily: 'Inter, sans-serif'
  },
  stroke: {
    width: [3, 0],
    curve: 'smooth'
  },
  colors: ['#6366f1', '#06b6d4'],
  fill: {
    type: ['gradient', 'solid'],
    gradient: {
      shade: 'dark',
      type: 'vertical',
      shadeIntensity: 0.5,
      gradientToColors: ['#8b5cf6', '#0891b2'],
      inverseColors: false,
      opacityFrom: 0.7,
      opacityTo: 0.3,
      stops: [0, 100]
    }
  },
  dataLabels: {
    enabled: false
  },
  xaxis: {
    categories: chartData.value.years,
    labels: {
      style: {
        colors: '#64748b',
        fontSize: '12px'
      }
    },
    axisBorder: {
      show: false
    },
    axisTicks: {
      show: false
    }
  },
  yaxis: [
    {
      title: {
        text: 'Prix/m² (€)',
        style: {
          color: '#6366f1',
          fontSize: '12px',
          fontWeight: 600
        }
      },
      labels: {
        style: {
          colors: '#64748b',
          fontSize: '11px'
        },
        formatter: (value) => {
          return value ? `${Math.round(value)}€` : '0€';
        }
      }
    },
    {
      opposite: true,
      title: {
        text: 'Volume de ventes',
        style: {
          color: '#06b6d4',
          fontSize: '12px',
          fontWeight: 600
        }
      },
      labels: {
        style: {
          colors: '#64748b',
          fontSize: '11px'
        }
      }
    }
  ],
  tooltip: {
    shared: true,
    intersect: false,
    theme: 'dark',
    style: {
      fontSize: '12px'
    },
    y: [
      {
        formatter: (value) => `${Math.round(value)}€/m²`
      },
      {
        formatter: (value) => `${value} ventes`
      }
    ]
  },
  legend: {
    show: true,
    position: 'top',
    horizontalAlign: 'left',
    labels: {
      colors: '#64748b'
    },
    markers: {
      width: 10,
      height: 10,
      radius: 3
    }
  },
  grid: {
    borderColor: '#e2e8f0',
    strokeDashArray: 4,
    xaxis: {
      lines: {
        show: false
      }
    },
    yaxis: {
      lines: {
        show: true
      }
    }
  }
}));

const series = computed(() => [
  {
    name: 'Prix/m²',
    type: 'area',
    data: chartData.value.prices
  },
  {
    name: 'Volume',
    type: 'column',
    data: chartData.value.volumes
  }
]);
</script>

<template>
  <div class="market-trends-chart">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center h-80">
      <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-sage-600"></div>
    </div>

    <!-- Chart -->
    <div v-else-if="trends && trends.length > 0">
      <apexchart
        type="line"
        height="350"
        :options="chartOptions"
        :series="series"
      />
    </div>

    <!-- Empty State -->
    <div v-else class="flex flex-col items-center justify-center h-80 text-slate-400">
      <ChartBarIcon class="h-16 w-16 mb-3 opacity-50" />
      <p class="text-sm">Aucune donnée historique disponible</p>
    </div>
  </div>
</template>

<style scoped>
.market-trends-chart {
  width: 100%;
  min-height: 350px;
}
</style>
