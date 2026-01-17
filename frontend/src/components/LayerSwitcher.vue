<script setup>
import { ref } from 'vue';
import { 
  CurrencyEuroIcon, 
  SparklesIcon,
  BuildingOffice2Icon
} from '@heroicons/vue/24/solid';

const emit = defineEmits(['change']);

const activeMode = ref('prix');

const modes = [
  { 
    id: 'prix', 
    label: 'Mode Prix', 
    icon: CurrencyEuroIcon,
    description: 'Prix au m²',
    gradient: 'from-blue-500 to-indigo-600'
  },
  { 
    id: 'zan', 
    label: 'Mode ZAN', 
    icon: SparklesIcon,
    description: 'Potentiel densification',
    gradient: 'from-emerald-500 to-teal-600'
  },
  { 
    id: 'urbanisme', 
    label: 'Urbanisme', 
    icon: BuildingOffice2Icon,
    description: 'Zonage PLU',
    gradient: 'from-amber-500 to-orange-600'
  }
];

const selectMode = (modeId) => {
  activeMode.value = modeId;
  emit('change', modeId);
};
</script>

<template>
  <div class="layer-switcher">
    <p class="section-label">Affichage</p>
    
    <div class="modes-container">
      <button 
        v-for="mode in modes" 
        :key="mode.id"
        @click="selectMode(mode.id)"
        class="mode-btn"
        :class="{ active: activeMode === mode.id }"
      >
        <div 
          class="mode-icon"
          :class="{ 
            'bg-gradient-to-br': activeMode === mode.id,
            [mode.gradient]: activeMode === mode.id
          }"
        >
          <component :is="mode.icon" class="w-4 h-4" />
        </div>
        <div class="mode-info">
          <span class="mode-label">{{ mode.label }}</span>
          <span class="mode-desc">{{ mode.description }}</span>
        </div>
        <div 
          v-if="activeMode === mode.id" 
          class="active-indicator"
        ></div>
      </button>
    </div>
    
    <!-- Legend Preview -->
    <div class="legend-preview" v-if="activeMode === 'prix'">
      <div class="legend-row">
        <div class="legend-dot" style="background: #22c55e"></div>
        <span>&lt; 3k€</span>
      </div>
      <div class="legend-row">
        <div class="legend-dot" style="background: #eab308"></div>
        <span>3-6k€</span>
      </div>
      <div class="legend-row">
        <div class="legend-dot" style="background: #ef4444"></div>
        <span>&gt; 6k€</span>
      </div>
    </div>
    
    <div class="legend-preview" v-else-if="activeMode === 'zan'">
      <div class="legend-row">
        <div class="legend-dot" style="background: #10b981"></div>
        <span>Fort potentiel</span>
      </div>
      <div class="legend-row">
        <div class="legend-dot" style="background: #eab308"></div>
        <span>Moyen</span>
      </div>
      <div class="legend-row">
        <div class="legend-dot" style="background: #ef4444"></div>
        <span>Saturé</span>
      </div>
    </div>
    
    <div class="legend-preview" v-else-if="activeMode === 'urbanisme'">
      <div class="legend-row">
        <div class="legend-square" style="background: #f59e0b"></div>
        <span>U - Urbain</span>
      </div>
      <div class="legend-row">
        <div class="legend-square" style="background: #f97316"></div>
        <span>AU - À Urbaniser</span>
      </div>
      <div class="legend-row">
        <div class="legend-square" style="background: #22c55e"></div>
        <span>N - Naturel</span>
      </div>
      <div class="legend-row">
        <div class="legend-square" style="background: #84cc16"></div>
        <span>A - Agricole</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-switcher {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  padding: 14px;
  box-shadow: 
    0 10px 30px rgba(0, 0, 0, 0.1),
    0 4px 8px rgba(0, 0, 0, 0.05);
  min-width: 180px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin: 0 0 10px 4px;
}

.modes-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  text-align: left;
}

.mode-btn:hover {
  background: #f8fafc;
}

.mode-btn.active {
  background: white;
  border-color: #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.mode-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  background: #f1f5f9;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.mode-btn.active .mode-icon {
  color: white;
}

.mode-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
}

.mode-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.mode-desc {
  font-size: 10px;
  color: #94a3b8;
}

.active-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6366f1;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.legend-preview {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-square {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
  opacity: 0.8;
}
</style>
