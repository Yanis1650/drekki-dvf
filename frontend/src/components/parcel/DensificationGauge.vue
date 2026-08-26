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
  },
  sourceCes: {
    type: String,
    default: null
  },
  libelleZone: {
    type: String,
    default: null
  }
});

const sourceConfig = computed(() => {
  const map = {
    'bdnb_emprise': { label: 'BDNB', color: '#6366f1', bg: '#eef2ff' },
    'bdtopo': { label: 'BD TOPO IGN', color: '#0ea5e9', bg: '#f0f9ff' },
    'plu_gpu': { label: 'PLU (GPU)', color: '#10b981', bg: '#f0fdf4' },
    'rnu_proximite': { label: 'RNU', color: '#f59e0b', bg: '#fffbeb' },
    'bdnb_usage_only': { label: 'BDNB (usage)', color: '#8b5cf6', bg: '#f5f3ff' },
  };
  return map[props.sourceCes] || null;
});

// Calculate gauge arc (180 degree arc)
const cesPercent = computed(() => Math.round(props.cesActuel * 100));
const potentielPercent = computed(() => Math.round((props.cesPlu - props.cesActuel) * 100));
const remainingPercent = computed(() => Math.max(0, potentielPercent.value));

// Gauge is now normalized to absolute CES (0–100%), not relative to PLU.
// This makes the PLU marker appear at the correct position on the arc.
const arcEndAngle = computed(() => Math.min(props.cesActuel * 180, 180));
const pluAngle    = computed(() => Math.min(props.cesPlu    * 180, 180));

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

const currentArc    = computed(() => describeArc(0, arcEndAngle.value));
const backgroundArc = computed(() => describeArc(0, 180));

// PLU tick marker — short radial line at PLU angle
const pluTickOuter = computed(() => polarToCartesian(100, 100, 80, pluAngle.value));
const pluTickInner = computed(() => polarToCartesian(100, 100, 60, pluAngle.value));
// PLU text label — slightly outside the tick
const pluLabelPos  = computed(() => polarToCartesian(100, 100, 92, pluAngle.value));

// Detect over-capacity: CES actuel dépasse le CES PLU autorisé
const isOverCapacity = computed(() => props.cesActuel > props.cesPlu && props.cesPlu > 0);

// Color based on categorie
const gaugeColor = computed(() => {
  const colors = {
    'FORT': '#10b981',
    'MOYEN': '#eab308',
    'FAIBLE': '#f97316',
    'SATURE': '#ef4444'
  };
  return colors[props.categorie] || '#527f8c';
});

const categoryConfig = computed(() => ({
  'FORT': { icon: '🟢', color: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' },
  'MOYEN': { icon: '🟡', color: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' },
  'FAIBLE': { icon: '🟠', color: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' },
  'SATURE': { icon: '🔴', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' }
}[props.categorie] || { icon: '⚪', color: '#527f8c', bg: 'rgba(82, 127, 140, 0.1)' }));
</script>

<template>
  <div class="densification-section">
    <h3 class="section-title">🏗️ Potentiel de Densification</h3>
    
    <div class="gauge-container">
      <!-- SVG Gauge -->
      <svg viewBox="0 0 200 130" class="gauge-svg">
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
        <!-- PLU Tick — orange line at PLU position -->
        <line
          v-if="cesPlu > 0"
          :x1="pluTickOuter.x"
          :y1="pluTickOuter.y"
          :x2="pluTickInner.x"
          :y2="pluTickInner.y"
          stroke="#EF9F27"
          stroke-width="2.5"
          stroke-linecap="round"
        />
        <!-- PLU label -->
        <text
          v-if="cesPlu > 0"
          :x="pluLabelPos.x"
          :y="pluLabelPos.y"
          text-anchor="middle"
          dominant-baseline="middle"
          font-size="9"
          fill="#EF9F27"
          font-weight="600"
        >{{ Math.round(cesPlu * 100) }}%</text>
      </svg>
      
      <!-- Center Label -->
      <div class="gauge-center">
        <span class="gauge-value">{{ cesPercent }}%</span>
        <span class="gauge-label">CES Actuel</span>
      </div>
    </div>
    
    <!-- PLU Info -->
    <div class="plu-info">
      <span class="plu-label">CES actuel</span>
      <span class="plu-value">{{ Math.round(cesActuel * 100) }}%</span>
      <span class="plu-sep">·</span>
      <span class="plu-label">PLU autorisé</span>
      <span class="plu-value" style="color: #EF9F27;">{{ Math.round(cesPlu * 100) }}%</span>
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
      <span class="badge-text">{{ categorie }}<template v-if="isOverCapacity"> · droits acquis</template></span>
    </div>
    
    <!-- Source ZAN tag -->
    <div v-if="sourceConfig" class="source-row">
      <span 
        class="source-chip"
        :style="{ backgroundColor: sourceConfig.bg, color: sourceConfig.color, borderColor: sourceConfig.color + '40' }"
      >
        {{ sourceConfig.label }}
      </span>
      <span v-if="libelleZone" class="zone-label">{{ libelleZone }}</span>
    </div>

    <!-- CES dépassé — alert contextuel -->
    <div v-if="isOverCapacity" class="ces-alert">
      <div class="ces-alert-icon">⚠️</div>
      <div class="ces-alert-body">
        <p class="ces-alert-title">CES dépassé</p>
        <p class="ces-alert-text">
          L'emprise au sol actuelle ({{ cesPercent }}%) dépasse le plafond PLU autorisé
          ({{ Math.round(cesPlu * 100) }}%). La parcelle est déjà sur-occupée selon le
          règlement d'urbanisme en vigueur. Toute extension ou nouvelle construction
          nécessiterait une dérogation ou une mise en conformité préalable.
        </p>
      </div>
    </div>

    <!-- Surface Constructible -->
    <div class="surface-card" v-if="surfaceConstructible > 0 && !isOverCapacity">
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

.plu-sep {
  color: #cbd5e1;
  margin: 0 2px;
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

.source-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.source-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  border: 1px solid;
}

.zone-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.ces-alert {
  display: flex;
  gap: 12px;
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 12px;
  padding: 14px 16px;
  margin-top: 16px;
}

.ces-alert-icon {
  font-size: 20px;
  flex-shrink: 0;
  line-height: 1.4;
}

.ces-alert-body {
  flex: 1;
}

.ces-alert-title {
  font-size: 13px;
  font-weight: 700;
  color: #92400e;
  margin: 0 0 4px 0;
}

.ces-alert-text {
  font-size: 12px;
  color: #78350f;
  margin: 0;
  line-height: 1.5;
}

.surface-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
  border: 2px solid #527f8c;
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
  color: #527f8c;
}
</style>
