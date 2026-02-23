<script setup>
import { ref, watch } from 'vue';
import axios from 'axios';
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/vue/24/solid';

const emit = defineEmits(['select']);

const query = ref("");
const results = ref([]);
const loading = ref(false);
const isFocused = ref(false);
let debounceTimeout = null;

const searchAddress = async (q) => {
  if (q.length < 3) {
    results.value = [];
    return;
  }
  
  loading.value = true;
  try {
    const res = await axios.get(`https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(q)}&limit=5`);
    results.value = res.data.features;
  } catch (err) {
    console.error("BAN API Error:", err);
    results.value = [];
  } finally {
    loading.value = false;
  }
};

watch(query, (newVal) => {
  clearTimeout(debounceTimeout);
  debounceTimeout = setTimeout(() => {
    searchAddress(newVal);
  }, 300);
});

const selectAddress = (feature) => {
  query.value = feature.properties.label;
  results.value = [];
  emit('select', {
    label: feature.properties.label,
    coordinates: feature.geometry.coordinates // [lon, lat]
  });
};
</script>

<template>
  <div class="relative w-full">
    <!-- Input Container -->
    <div class="relative">
      <!-- Search Icon -->
      <div class="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none">
        <MagnifyingGlassIcon 
          class="h-5 w-5 transition-colors duration-200"
          :class="isFocused ? 'text-sage-500' : 'text-slate-400'"
        />
      </div>
      
      <!-- Input Field -->
      <input 
        v-model="query"
        @focus="isFocused = true"
        @blur="isFocused = false" 
        type="text" 
        placeholder="Rechercher une adresse..." 
        class="w-full pl-12 pr-12 py-3.5 bg-white rounded-xl border-2 transition-all duration-200
               text-slate-800 placeholder-slate-400 font-medium
               focus:outline-none"
        :class="isFocused 
          ? 'border-sage-400 shadow-[0_0_0_4px_rgba(99,102,241,0.1)]' 
          : 'border-slate-200 hover:border-slate-300 shadow-sm'"
      />
      
      <!-- Spinner -->
      <div v-if="loading" class="absolute right-4 top-1/2 -translate-y-1/2">
        <svg class="animate-spin h-5 w-5 text-sage-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    </div>

    <!-- Results Dropdown -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <ul 
        v-if="results.length > 0" 
        class="absolute z-50 w-full mt-2 bg-white rounded-xl border border-slate-200 shadow-xl 
               max-h-72 overflow-y-auto custom-scrollbar"
      >
        <li 
          v-for="(feature, index) in results" 
          :key="index"
          @click="selectAddress(feature)"
          class="group flex items-start gap-3 px-4 py-3.5 cursor-pointer transition-colors
                 hover:bg-sage-50 border-b border-slate-100 last:border-0"
        >
          <!-- Pin Icon -->
          <div class="w-8 h-8 rounded-lg bg-slate-100 group-hover:bg-sage-100 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors">
            <MapPinIcon class="h-4 w-4 text-slate-400 group-hover:text-sage-500 transition-colors" />
          </div>
          
          <!-- Address Info -->
          <div class="flex-1 min-w-0">
            <p class="font-semibold text-slate-800 text-sm leading-tight truncate group-hover:text-sage-700 transition-colors">
              {{ feature.properties.label }}
            </p>
            <p class="text-xs text-slate-500 mt-0.5 truncate">
              {{ feature.properties.context }}
            </p>
          </div>
        </li>
      </ul>
    </Transition>
  </div>
</template>
