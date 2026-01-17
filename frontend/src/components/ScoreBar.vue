<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  score: {
    type: [Number, String],
    required: true
  },
  icon: {
    type: [Object, Function],
    default: null
  },
  gradient: {
    type: String,
    default: 'from-indigo-500 to-blue-400'
  },
  animate: {
    type: Boolean,
    default: true
  }
});

// Convert score to number to handle strings from API
const numericScore = computed(() => {
  const val = Number(props.score);
  return isNaN(val) ? 0 : Math.min(10, Math.max(0, val));
});

const displayWidth = ref(0);

// Animate on mount or when animate prop changes
watch(() => props.animate, (val) => {
  if (val) {
    setTimeout(() => {
      displayWidth.value = (numericScore.value / 10) * 100;
    }, 50);
  }
}, { immediate: true });

const scoreColor = computed(() => {
  if (numericScore.value >= 8) return 'text-emerald-600';
  if (numericScore.value >= 6) return 'text-amber-600';
  return 'text-rose-600';
});
</script>

<template>
  <div class="group">
    <!-- Header with label and score -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <!-- Icon -->
        <component 
          v-if="icon" 
          :is="icon" 
          class="h-4 w-4 text-slate-400 group-hover:text-slate-600 transition-colors" 
        />
        <span class="text-sm font-medium text-slate-600">{{ label }}</span>
      </div>
      <!-- Score Value -->
      <span class="text-sm font-bold tabular-nums" :class="scoreColor">
        {{ numericScore.toFixed(1) }}<span class="text-slate-400 font-normal">/10</span>
      </span>
    </div>
    
    <!-- Progress Bar -->
    <div class="score-bar-track">
      <div 
        class="score-bar-fill bg-gradient-to-r"
        :class="gradient"
        :style="{ width: `${displayWidth}%` }"
      >
        <!-- Shimmer effect -->
        <div class="w-full h-full relative overflow-hidden">
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full animate-shimmer"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-shimmer {
  animation: shimmer 2s ease-in-out infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}
</style>
