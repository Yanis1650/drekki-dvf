<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { ArrowTrendingUpIcon, ArrowTrendingDownIcon, MinusIcon } from '@heroicons/vue/24/solid';

const props = defineProps({
  value: {
    type: [Number, String],
    required: true
  },
  avg: {
    type: [Number, String],
    required: true
  }
});

// Convert to numbers for safe calculations
const numericValue = computed(() => {
  const val = Number(props.value);
  return isNaN(val) ? 0 : val;
});

const numericAvg = computed(() => {
  const val = Number(props.avg);
  return isNaN(val) ? 0 : val;
});

// Calculate difference
const priceDiff = computed(() => {
  if (!numericAvg.value || numericAvg.value === 0) return 0;
  return ((numericValue.value - numericAvg.value) / numericAvg.value) * 100;
});

const isAbove = computed(() => priceDiff.value > 2);
const isBelow = computed(() => priceDiff.value < -2);
const isNeutral = computed(() => !isAbove.value && !isBelow.value);

const diffLabel = computed(() => {
  const val = Math.abs(priceDiff.value).toFixed(0);
  if (isAbove.value) return `+${val}%`;
  if (isBelow.value) return `-${val}%`;
  return '≈';
});

const diffColor = computed(() => {
  if (isBelow.value) return 'text-emerald-600 bg-emerald-50';
  if (isAbove.value) return 'text-rose-600 bg-rose-50';
  return 'text-slate-600 bg-slate-100';
});

// Animation
const animatedValue = ref(0);
const animatedAvg = ref(0);

onMounted(() => {
  // Animate counter
  const duration = 800;
  const steps = 30;
  const stepValue = numericValue.value / steps;
  const stepAvg = numericAvg.value / steps;
  let current = 0;
  
  const interval = setInterval(() => {
    current++;
    animatedValue.value = Math.round(stepValue * current);
    animatedAvg.value = Math.round(stepAvg * current);
    if (current >= steps) {
      animatedValue.value = Math.round(numericValue.value);
      animatedAvg.value = Math.round(numericAvg.value);
      clearInterval(interval);
    }
  }, duration / steps);
});

// Bar widths for visualization
const valueBarWidth = computed(() => {
  const max = Math.max(numericValue.value, numericAvg.value) * 1.2;
  if (max === 0) return 0;
  return (numericValue.value / max) * 100;
});

const avgBarWidth = computed(() => {
  const max = Math.max(numericValue.value, numericAvg.value) * 1.2;
  if (max === 0) return 0;
  return (numericAvg.value / max) * 100;
});
</script>

<template>
  <div class="space-y-4">
    <!-- Main Price Display -->
    <div class="flex items-end justify-between">
      <div>
        <span class="text-xs uppercase tracking-wider text-slate-400 font-semibold">Moyenne du quartier</span>
        <div class="flex items-baseline gap-2 mt-1">
          <span class="text-3xl font-bold text-slate-900 tabular-nums">
            {{ animatedAvg.toLocaleString('fr-FR') }}
          </span>
          <span class="text-lg text-slate-500 font-medium">€/m²</span>
        </div>
      </div>
      
      <!-- Trend Indicator -->
      <div 
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-bold"
        :class="diffColor"
      >
        <ArrowTrendingDownIcon v-if="isBelow" class="h-4 w-4" />
        <ArrowTrendingUpIcon v-else-if="isAbove" class="h-4 w-4" />
        <MinusIcon v-else class="h-4 w-4" />
        <span>{{ diffLabel }}</span>
      </div>
    </div>
    
    <!-- Comparison Bars -->
    <div class="space-y-3">
      <!-- This Transaction -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-500 font-medium">Ce bien</span>
          <span class="font-bold text-slate-700 tabular-nums">{{ Math.round(numericValue).toLocaleString('fr-FR') }} €/m²</span>
        </div>
        <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
          <div 
            class="h-full rounded-full transition-all duration-700 ease-out"
            :class="isBelow ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : isAbove ? 'bg-gradient-to-r from-rouge-500 to-terracotta-400' : 'bg-gradient-to-r from-sage-500 to-sage-400'"
            :style="{ width: `${valueBarWidth}%` }"
          ></div>
        </div>
      </div>
      
      <!-- Average -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-500 font-medium">Moyenne secteur</span>
          <span class="font-semibold text-slate-500 tabular-nums">{{ Math.round(numericAvg).toLocaleString('fr-FR') }} €/m²</span>
        </div>
        <div class="h-3 bg-slate-100 rounded-full overflow-hidden">
          <div 
            class="h-full bg-slate-300 rounded-full transition-all duration-700 ease-out"
            :style="{ width: `${avgBarWidth}%` }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>
