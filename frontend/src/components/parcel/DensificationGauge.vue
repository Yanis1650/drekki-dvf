<script setup>
import { computed } from 'vue';

const props = defineProps({
  cesActuel: {
    type: Number,
    default: 0
  },
  cesPlu: {
    type: Number,
    default: 0.5
  },
  categorie: {
    type: String,
    default: 'MOYEN'
  },
  surfaceConstructible: {
    type: Number,
    default: 0
  }
});

// Calculate gauge arc (180 degree arc)
const cesPercent = computed(() => Math.round(props.cesActuel * 100));
const potentielPercent = computed(() => Math.round((props.cesPlu - props.cesActuel) * 100));
const remainingPercent = computed(() => Math.max(0, potentielPercent.value));

// Arc calculation for SVG
const arcEndAngle = computed(() => {
  const angle = (props.cesActuel / props.cesPlu) * 180;
  return Math.min(angle, 180);
});

// Convert angle to arc path
const describeArc = (startAngle, endAngle) => {
  const cx = 100, cy = 100, r = 70;
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 90 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`;
};

const polarToCartesian = (cx, cy, r, angle) => {
  const rad = (angle - 180) * Math.PI / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad)
  };
};

const currentArc = computed(() => describeArc(0, arcEndAngle.value));
const backgroundArc = computed(() => describeArc(0, 180));

// PLU marker position
const pluMarkerPos = computed(() => {
  const angle = 180; // PLU is at the end (100%)
  return polarToCartesian(100, 100, 70, angle);
});

// Color based on categorie
const gaugeColor = computed(() => {
  const colors = {
    'FORT': '#10b981',
    'MOYEN': '#eab308',
    'FAIBLE': '#f97316',
    'SATURE': '#ef4444'
  };
  return colors[props.categorie] || '#6366f1';
});

const categoryConfig = computed(() => ({
  'FORT': { icon: '🟢', color: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' },
  'MOYEN': { icon: '🟡', color: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' },
  'FAIBLE': { icon: '🟠', color: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' },
  'SATURE': { icon: '🔴', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' }
}[props.categorie] || { icon: '⚪', color: '#6366f1', bg: 'rgba(99, 102, 241, 0.1)' }));
</script>

<template>
  <div class="densification-section">
    <h3 class="section-title">🏗️ Potentiel de Densification</h3>
    
    <div class="gauge-container">
      <!-- SVG Gauge -->
      <svg viewBox="0 0 200 120" class="gauge-svg">
        <!-- Background Arc -->
        <path 
          :d="backgroundArc" 
          fill="none" 
          stroke="#e2e8f0" 
          stroke-width="14"
          stroke-linecap="round"
        />
        <!-- Current CES Arc -->
        <path 
          :d="currentArc" 
          fill="none" 
          :stroke="gaugeColor"
          stroke-width="14"
          stroke-linecap="round"
          class="gauge-arc-animated"
        />
        <!-- PLU Marker -->
        <circle 
          :cx="pluMarkerPos.x" 
          :cy="pluMarkerPos.y" 
          r="6" 
          fill="#0f172a"
          stroke="white"
          stroke-width="2"
        />
      </svg>
      
      <!-- Center Label -->
      <div class="gauge-center">
        <span class="gauge-value">{{ cesPercent }}%</span>
        <span class="gauge-label">CES Actuel</span>
      </div>
    </div>
    
    <!-- PLU Info -->
    <div class="plu-info">
      <span class="plu-label">PLU autorise</span>
      <span class="plu-value">{{ Math.round(cesPlu * 100) }}%</span>
    </div>
    
    <!-- Category Badge -->
    <div 
      class="category-badge"
      :style="{ 
        backgroundColor: categoryConfig.bg,
        borderColor: categoryConfig.color,
        color: categoryConfig.color
      }"
    >
      <span class="badge-icon">{{ categoryConfig.icon }}</span>
      <span class="badge-text">{{ categorie }}</span>
    </div>
    
    <!-- Surface Constructible -->
    <div class="surface-card" v-if="surfaceConstructible > 0">
      <span class="surface-label">Surface constructible restante</span>
      <span class="surface-value">{{ surfaceConstructible.toFixed(0) }} m²</span>
    </div>
  </div>
</template>

<style scoped>
.densification-section {
  background: #f8fafc;
  border-radius: 16px;
  padding: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 20px 0;
}

.gauge-container {
  position: relative;
  width: 100%;
  max-width: 200px;
  margin: 0 auto;
}

.gauge-svg {
  width: 100%;
  height: auto;
}

.gauge-arc-animated {
  animation: drawArc 1s ease-out forwards;
  stroke-dasharray: 220;
  stroke-dashoffset: 220;
}

@keyframes drawArc {
  to {
    stroke-dashoffset: 0;
  }
}

.gauge-center {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
}

.gauge-value {
  display: block;
  font-size: 28px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1;
}

.gauge-label {
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.plu-info {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 13px;
}

.plu-label {
  color: #64748b;
}

.plu-value {
  font-weight: 700;
  color: #1e293b;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 2px solid;
  margin-top: 16px;
}

.badge-icon {
  font-size: 16px;
}

.surface-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
  border: 2px solid #6366f1;
  text-align: center;
}

.surface-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.surface-value {
  font-size: 24px;
  font-weight: 800;
  color: #6366f1;
}
</style>
