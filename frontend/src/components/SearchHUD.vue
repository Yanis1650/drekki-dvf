<script setup>
import { ref } from 'vue';
import AddressSearch from './AddressSearch.vue';
import { CurrencyEuroIcon, FunnelIcon } from '@heroicons/vue/24/solid';

const props = defineProps({
  balance: {
    type: Number,
    default: 0
  },
  modelValue: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['search-select', 'buy-credits', 'update:modelValue']);

const filters = [
  { id: 'zan', label: '🌱 Fort Potentiel ZAN', color: '#10b981' },
  { id: 'recent', label: '📅 Ventes < 2 ans', color: '#6366f1' }
];

const toggleFilter = (filterId) => {
  const next = props.modelValue === filterId ? null : filterId;
  emit('update:modelValue', next);
};
</script>

<template>
  <div class="search-hud">
    <!-- Main Search Bar -->
    <div class="search-container">
      <AddressSearch @select="(val) => emit('search-select', val)" />
    </div>
    
    <!-- Quick Filters -->
    <div class="filters-container">
      <button 
        v-for="filter in filters"
        :key="filter.id"
        @click="toggleFilter(filter.id)"
        class="filter-pill"
        :class="{ active: modelValue === filter.id }"
        :style="modelValue === filter.id ? { borderColor: filter.color, color: filter.color } : {}"
      >
        {{ filter.label }}
      </button>
    </div>
    
    <!-- Separator -->
    <div class="separator"></div>
    
    <!-- Credit Badge -->
    <div class="credit-badge" @click="emit('buy-credits')">
      <div class="credit-icon">
        <CurrencyEuroIcon class="w-4 h-4" />
      </div>
      <div class="credit-info">
        <span class="credit-value">{{ balance }}</span>
        <span class="credit-label">crédits</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-hud {
  display: flex;
  align-items: center;
  gap: 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 20px;
  padding: 12px 20px;
  box-shadow: 
    0 20px 40px rgba(0, 0, 0, 0.12),
    0 4px 12px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  max-width: 900px;
  width: 90vw;
}

.search-container {
  flex: 1;
  min-width: 280px;
}

.search-container :deep(input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent;
  padding-left: 40px;
}

.search-container :deep(input:focus) {
  box-shadow: none !important;
}

.filters-container {
  display: flex;
  gap: 8px;
}

.filter-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: #f8fafc;
  border: 2px solid transparent;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.filter-pill:hover {
  background: #f1f5f9;
  color: #475569;
}

.filter-pill.active {
  background: white;
  border-width: 2px;
}

.separator {
  width: 1px;
  height: 32px;
  background: linear-gradient(180deg, transparent, #e2e8f0, transparent);
}

.credit-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px 8px 10px;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.credit-badge:hover {
  transform: scale(1.02);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.credit-icon {
  width: 28px;
  height: 28px;
  background: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.credit-info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.credit-value {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.credit-label {
  font-size: 10px;
  color: #64748b;
  font-weight: 500;
}

/* Responsive */
@media (max-width: 768px) {
  .search-hud {
    flex-direction: column;
    padding: 16px;
    width: 95vw;
  }
  
  .search-container {
    width: 100%;
    min-width: unset;
  }
  
  .filters-container {
    width: 100%;
    overflow-x: auto;
  }
  
  .separator {
    width: 100%;
    height: 1px;
  }
}
</style>
