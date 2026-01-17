<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { 
  ArrowTrendingUpIcon, 
  ArrowTrendingDownIcon,
  MinusIcon 
} from '@heroicons/vue/24/solid';

const props = defineProps({
  gain: {
    type: [Number, String],
    required: true
  }
});

// Convert to numeric value
const numericGain = computed(() => {
  const val = typeof props.gain === 'string' ? parseFloat(props.gain) : props.gain;
  return isNaN(val) ? 0 : val;
});

// Animated counter
const displayValue = ref(0);

// Color and icon based on gain
const gainColor = computed(() => {
  const val = numericGain.value;
  if (val > 5) return 'from-emerald-500 to-green-400';
  if (val > 0) return 'from-amber-500 to-yellow-400';
  return 'from-red-500 to-rose-400';
});

const textColor = computed(() => {
  const val = numericGain.value;
  if (val > 5) return 'text-emerald-600';
  if (val > 0) return 'text-amber-600';
  return 'text-red-600';
});

const icon = computed(() => {
  const val = numericGain.value;
  if (val > 2) return ArrowTrendingUpIcon;
  if (val < -2) return ArrowTrendingDownIcon;
  return MinusIcon;
});

const directionLabel = computed(() => {
  const val = numericGain.value;
  if (val > 2) return 'Marché haussier';
  if (val < -2) return 'Marché baissier';
  return 'Marché stable';
});

// Animate counter on mount and when gain changes
const animateCounter = () => {
  const target = numericGain.value;
  const duration = 1000; // 1 second
  const steps = 60;
  const increment = target / steps;
  let current = 0;
  let step = 0;

  const timer = setInterval(() => {
    current += increment;
    step++;
    
    if (step >= steps) {
      displayValue.value = target;
      clearInterval(timer);
    } else {
      displayValue.value = current;
    }
  }, duration / steps);
};

onMounted(() => {
  setTimeout(() => animateCounter(), 100);
});

watch(() => props.gain, () => {
  animateCounter();
});
</script>

<template>
  <div class="potential-gain-indicator mb-6">
    <!-- Main Card -->
    <div class="relative overflow-hidden rounded-2xl p-6 bg-gradient-to-br" :class="gainColor">
      <!-- Background Pattern -->
      <div class="absolute inset-0 opacity-10">
        <div class="absolute inset-0" style="background-image: radial-gradient(circle, white 1px, transparent 1px); background-size: 20px 20px;"></div>
      </div>

      <!-- Content -->
      <div class="relative z-10">
        <div class="flex items-center justify-between mb-2">
          <span class="text-white/90 text-sm font-semibold uppercase tracking-wider">
            Plus-value potentielle
          </span>
          <component :is="icon" class="h-6 w-6 text-white" />
        </div>

        <!-- Animated Value -->
        <div class="flex items-baseline gap-2 mb-1">
          <span class="text-5xl font-bold text-white">
            {{ displayValue >= 0 ? '+' : '' }}{{ displayValue.toFixed(1) }}
          </span>
          <span class="text-2xl font-semibold text-white/80">%</span>
          <span class="text-sm text-white/70 ml-2">/an</span>
        </div>

        <!-- Direction Label -->
        <p class="text-white/80 text-sm font-medium">
          {{ directionLabel }}
        </p>
      </div>
    </div>

    <!-- Subtext -->
    <p class="text-xs text-slate-500 mt-2 text-center">
      Basé sur la tendance historique 2014-2025
    </p>
  </div>
</template>

<style scoped>
.potential-gain-indicator {
  animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
