<script setup>
import { ref } from 'vue';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapContainer } from '../composables/useMapContainer';

const props = defineProps({
  radius: { type: Number, default: 500 },
  center: { type: Array, default: () => [-1.6778, 48.1173] },
  transactions: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  mode: { type: String, default: 'prix' },
  activeFilter: { type: String, default: null },
  selectedParcel: { type: String, default: null },
  relatedParcels: { type: Array, default: () => [] }
});

const emit = defineEmits(['map-loaded', 'transaction-click', 'parcel-click', 'context-error']);
const contextError = ref('');
const { mapContainer, isLoading } = useMapContainer(props, (event, value) => {
  // La disponibilité du fond parcellaire est un constat, pas une supposition :
  // elle remonte à l'application, qui la rend dans le rail des sources.
  if (event === 'context-error') contextError.value = value;
  emit(event, value);
});
</script>

<template>
  <div class="relative w-full h-full">
    <div ref="mapContainer" class="w-full h-full"></div>

    <p v-if="contextError" role="status" class="absolute bottom-4 left-4 right-4 bg-surface fe-absent p-2 text-meta">{{ contextError }}</p>
    <!-- État de chargement. L'animation porte une information — quelque chose
         est en cours — et s'arrête dès que ce n'est plus vrai. -->
    <Transition
      enter-active-class="transition-opacity duration-ui"
      leave-active-class="transition-opacity duration-ui"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isLoading"
        class="absolute inset-0 bg-ground flex items-center justify-center"
      >
        <div class="text-center">
          <div class="relative w-8 h-8 mx-auto mb-4">
            <div class="absolute inset-0 rounded-full border-2 border-rule"></div>
            <div class="absolute inset-0 rounded-full border-2 border-accent border-t-transparent animate-spin"></div>
          </div>
          <p class="text-ink font-medium text-body">Chargement de la carte</p>
          <p class="fe-meta mt-1">Fond IGN et données foncières</p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<!-- Les surcharges MapLibre vivent désormais dans src/style.css, sur les
     jetons : elles étaient dupliquées ici avec des valeurs divergentes. -->
