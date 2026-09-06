<script setup>
import { ref, watch, onUnmounted } from 'vue';
import axios from 'axios';
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/vue/24/outline';

// Un identifiant par instance : l'étiquette doit désigner ce champ-ci.
const fieldId = `adresse-${Math.random().toString(36).slice(2, 8)}`;

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
    <!-- Le champ reprend le cartouche de la barre de contrôles : même hauteur,
         même filet, même étiquette. Il n'a pas de chevron — ce n'est pas une
         liste fermée, c'est une recherche. -->
    <div
      class="relative flex items-center gap-2 px-3 py-[5px] bg-surface border rounded transition-colors duration-ui"
      :class="isFocused ? 'border-accent' : 'border-rule-strong hover:border-ink-3'"
    >
      <MapPinIcon class="w-4 h-4 shrink-0" :class="isFocused ? 'text-accent' : 'text-ink-3'" aria-hidden="true" />
      <span class="min-w-0 flex-1">
        <label :for="fieldId" class="block fe-label">Adresse</label>
        <input
          :id="fieldId"
          v-model="query"
          type="text"
          autocomplete="off"
          placeholder="Commune, rue, numéro…"
          class="w-full bg-transparent border-0 p-0 text-body text-ink leading-tight placeholder-ink-3 focus:outline-none"
          @focus="isFocused = true"
          @blur="isFocused = false"
        >
      </span>
      <MagnifyingGlassIcon v-if="!loading" class="w-4 h-4 shrink-0 text-ink-3" aria-hidden="true" />
      <svg v-else class="w-4 h-4 shrink-0 text-accent animate-spin" viewBox="0 0 24 24" fill="none" role="status" aria-label="Recherche en cours">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
    </div>

    <p v-if="searchError" role="status" class="absolute z-50 top-full left-0 right-0 mt-1 bg-surface border border-rule rounded p-2 fe-meta shadow-overlay">{{ searchError }}</p>

    <Transition
      enter-active-class="transition-opacity duration-ui"
      enter-from-class="opacity-0"
      leave-active-class="transition-opacity duration-ui"
      leave-to-class="opacity-0"
    >
      <ul
        v-if="results.length > 0"
        class="absolute z-50 left-0 right-0 mt-1 bg-surface rounded border border-rule-strong shadow-overlay max-h-72 overflow-y-auto custom-scrollbar"
      >
        <li
          v-for="(feature, index) in results"
          :key="index"
          tabindex="0"
          role="button"
          class="flex items-start gap-2 px-3 py-2 cursor-pointer border-b border-rule last:border-0 hover:bg-accent-soft"
          @click="selectAddress(feature)"
          @keydown.enter="selectAddress(feature)"
          @keydown.space.prevent="selectAddress(feature)"
        >
          <MapPinIcon class="w-4 h-4 mt-0.5 shrink-0 text-ink-3" aria-hidden="true" />
          <span class="min-w-0">
            <span class="block text-body text-ink truncate">{{ feature.properties.label }}</span>
            <span class="block fe-meta truncate">{{ feature.properties.context }}</span>
          </span>
        </li>
      </ul>
    </Transition>
  </div>
</template>
