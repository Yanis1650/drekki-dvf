<script setup>
import { computed } from 'vue';
import VueApexCharts from 'vue3-apexcharts';

const props = defineProps({
  transaction: {
    type: Object,
    required: true
  },
  priceHistory: {
    type: Array,
    default: () => []
  }
});

// Format price
const formattedPrice = computed(() => {
  const price = props.transaction?.prix_m2 || props.transaction?.valeur_fonciere;
  if (!price) return 'N/A';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0
  }).format(price);
});

// Format date
const formattedDate = computed(() => {
  const date = props.transaction?.date_mutation;
  if (!date) return '';
  return new Date(date).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
});

// DPE color mapping
const dpeConfig = computed(() => {
  const dpe = props.transaction?.scores?.dpe || props.transaction?.dpe;
  const colors = {
    'A': { bg: '#059669', text: 'white' },
    'B': { bg: '#10b981', text: 'white' },
    'C': { bg: '#84cc16', text: 'white' },
    'D': { bg: '#eab308', text: '#1e293b' },
    'E': { bg: '#f97316', text: 'white' },
    'F': { bg: '#ea580c', text: 'white' },
    'G': { bg: '#dc2626', text: 'white' }
  };
  return { letter: dpe, ...colors[dpe] } || { letter: '-', bg: '#94a3b8', text: 'white' };
});

// Sparkline data
const sparklineData = computed(() => {
  if (props.priceHistory.length < 2) {
    // Generate fake trend for demo
    const basePrice = props.transaction?.prix_m2 || 4000;
    return [
      basePrice * 0.85,
      basePrice * 0.88,
      basePrice * 0.92,
      basePrice * 0.90,
      basePrice * 0.95,
      basePrice * 0.98,
      basePrice
    ];
  }
  return props.priceHistory.map(h => h.price_m2);
});

const sparklineOptions = {
  chart: {
    type: 'line',
    sparkline: { enabled: true },
    animations: {
      enabled: true,
      easing: 'easeout',
      speed: 500
    }
  },
  stroke: {
    width: 2,
    curve: 'smooth'
  },
  colors: ['#6366f1'],
  tooltip: { enabled: false }
};

const sparklineSeries = computed(() => [{
  data: sparklineData.value
}]);

// Price trend indicator
const priceTrend = computed(() => {
  const data = sparklineData.value;
  if (data.length < 2) return 'stable';
  const first = data[0];
  const last = data[data.length - 1];
  const change = ((last - first) / first) * 100;
  if (change > 5) return 'up';
  if (change < -5) return 'down';
  return 'stable';
});
</script>

<template>
  <div class="transaction-popup">
    <!-- Header -->
    <div class="popup-header">
      <div class="price-tag">
        <span class="price">{{ formattedPrice }}</span>
        <span class="unit">/m²</span>
      </div>
      <div 
        class="dpe-badge" 
        v-if="dpeConfig.letter"
        :style="{ backgroundColor: dpeConfig.bg, color: dpeConfig.text }"
      >
        {{ dpeConfig.letter }}
      </div>
    </div>
    
    <!-- Date -->
    <p class="date">{{ formattedDate }}</p>
    
    <!-- Sparkline -->
    <div class="sparkline-container">
      <div class="sparkline-header">
        <span class="sparkline-label">Tendance zone</span>
        <span 
          class="trend-indicator"
          :class="`trend-${priceTrend}`"
        >
          <svg v-if="priceTrend === 'up'" class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
          </svg>
          <svg v-else-if="priceTrend === 'down'" class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
          </svg>
          <span v-else>→</span>
        </span>
      </div>
      <VueApexCharts
        type="line"
        height="40"
        :options="sparklineOptions"
        :series="sparklineSeries"
      />
    </div>
    
    <!-- Details -->
    <div class="details-grid" v-if="transaction.surface_reelle_bati || transaction.type_local">
      <div class="detail" v-if="transaction.surface_reelle_bati">
        <span class="detail-label">Surface</span>
        <span class="detail-value">{{ transaction.surface_reelle_bati }} m²</span>
      </div>
      <div class="detail" v-if="transaction.type_local">
        <span class="detail-label">Type</span>
        <span class="detail-value">{{ transaction.type_local }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.transaction-popup {
  padding: 14px 16px;
  min-width: 220px;
  font-family: 'Inter', sans-serif;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}

.price-tag {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.price {
  font-size: 20px;
  font-weight: 800;
  color: #1e293b;
}

.unit {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
}

.dpe-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 800;
  min-width: 28px;
  text-align: center;
}

.date {
  font-size: 12px;
  color: #64748b;
  margin: 0 0 12px 0;
}

.sparkline-container {
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px 6px;
  margin-bottom: 12px;
}

.sparkline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.sparkline-label {
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.trend-indicator {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
}

.trend-up {
  color: #10b981;
}

.trend-down {
  color: #ef4444;
}

.trend-stable {
  color: #94a3b8;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.detail-label {
  font-size: 10px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
</style>
