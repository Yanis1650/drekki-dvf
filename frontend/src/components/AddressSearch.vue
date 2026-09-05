<script setup>
import { ref, watch, onUnmounted } from 'vue';
import axios from 'axios';
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/vue/24/solid';

const emit = defineEmits(['select']);

const query = ref("");
const results = ref([]);
const loading = ref(false);
const isFocused = ref(false);
let debounceTimeout = null;
let version = 0, controller;
let selectedLabel = '';
const searchError = ref('');
onUnmounted(() => { version++; clearTimeout(debounceTimeout); controller?.abort(); });

const searchAddress = async (q, request) => {
  if (q.length < 3) {
    results.value = [];
    return;
  }
  
  loading.value = true;
  controller = new AbortController();
  try {
    const res = await axios.get(`https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(q)}&limit=5`, { signal: controller.signal, timeout: 10000 });
    if (request === version) results.value = res.data.features;
  } catch (err) {
    if (request === version) { results.value = []; searchError.value = 'Recherche d’adresse indisponible. Réessayez en modifiant le texte.'; }
  } finally {
    if (request === version) loading.value = false;
  }
};

watch(query, (newVal) => {
  const request = ++version;
  clearTimeout(debounceTimeout);
  controller?.abort();
  results.value = []; loading.value = false; searchError.value = '';
  if (newVal === selectedLabel || newVal.length < 3) return;
  debounceTimeout = setTimeout(() => {
    searchAddress(newVal, request);
  }, 300);
});

const selectAddress = (feature) => {
  selectedLabel = feature.properties.label;
  query.value = selectedLabel;
  results.value = [];
  emit('select', {
    label: feature.properties.label,
    citycode: feature.properties.citycode,
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
          :class="isFocused ? 'text-accent' : 'text-ink-3'"
        />
      </div>
      
      <!-- Input Field -->
      <input 
        v-model="query"
        @focus="isFocused = true"
        @blur="isFocused = false" 
        aria-label="Rechercher une adresse"
        type="text" 
        placeholder="Rechercher une adresse..." 
        class="w-full pl-12 pr-12 py-3.5 bg-surface rounded border-2 transition-all duration-200
         text-ink placeholder-ink-3 font-medium
         focus:outline-none"
        :class="isFocused
         ? 'border-accent '
         : 'border-rule hover:border-rule-strong '"
      />
      
      <!-- Spinner -->
      <div v-if="loading" class="absolute right-4 top-1/2 -translate-y-1/2">
        <svg class="animate-spin h-5 w-5 text-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    </div>

    <p v-if="searchError" role="status" class="absolute top-full bg-surface border border-rule p-2 text-meta">{{ searchError }}</p>
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
        class="absolute z-50 w-full mt-2 bg-surface rounded border border-rule
         max-h-72 overflow-y-auto custom-scrollbar"
      >
        <li 
          v-for="(feature, index) in results" 
          :key="index"
          @click="selectAddress(feature)"
          @keydown.enter="selectAddress(feature)"
          @keydown.space.prevent="selectAddress(feature)"
          tabindex="0" role="button"
          class="group flex items-start gap-3 px-4 py-3.5 cursor-pointer transition-colors
           hover:bg-accent-soft border-b border-rule last:border-0"
        >
          <!-- Pin Icon -->
          <div class="w-8 h-8 rounded bg-surface-2 group-hover:bg-accent-soft flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors">
            <MapPinIcon class="h-4 w-4 text-ink-3 group-hover:text-accent transition-colors" />
          </div>
          
          <!-- Address Info -->
          <div class="flex-1 min-w-0">
            <p class="font-semibold text-ink text-body leading-tight truncate group-hover:text-accent transition-colors">
              {{ feature.properties.label }}
            </p>
            <p class="text-meta text-ink-3 mt-0.5 truncate">
              {{ feature.properties.context }}
            </p>
          </div>
        </li>
      </ul>
    </Transition>
  </div>
</template>
