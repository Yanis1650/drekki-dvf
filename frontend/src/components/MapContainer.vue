<script setup>
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMapContainer } from '../composables/useMapContainer';

const props = defineProps({
  center: { type: Array, default: () => [-1.6778, 48.1173] },
  transactions: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  mode: { type: String, default: 'prix' },
  activeFilter: { type: String, default: null },
  selectedParcel: { type: String, default: null },
  relatedParcels: { type: Array, default: () => [] }
});

const emit = defineEmits(['map-loaded', 'transaction-click', 'parcel-click']);
const { mapContainer, isLoading } = useMapContainer(props, emit);
</script>

<template>
  <div class="relative w-full h-full">
    <div ref="mapContainer" class="w-full h-full"></div>
    <Transition
      enter-active-class="transition-opacity duration-500"
      leave-active-class="transition-opacity duration-500"
      enter-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isLoading"
        class="absolute inset-0 bg-gradient-to-br from-slate-50 via-white to-sage-50 flex items-center justify-center"
      >
        <div class="text-center">
          <div class="relative w-20 h-20 mx-auto mb-6">
            <div class="absolute inset-0 rounded-full border-4 border-slate-200"></div>
            <div class="absolute inset-0 rounded-full border-4 border-sage-500 border-t-transparent animate-spin"></div>
            <div class="absolute inset-3 rounded-full bg-gradient-to-br from-sage-500 to-sage-700 opacity-20 animate-pulse"></div>
          </div>
          <p class="text-slate-600 font-semibold text-lg">Chargement de la carte</p>
          <p class="text-slate-400 text-sm mt-1">Préparation des données foncières...</p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
.maplibregl-ctrl-top-right { top: 12px !important; }
.maplibregl-ctrl-group {
  background: rgba(255, 255, 255, 0.95) !important;
  backdrop-filter: blur(12px) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
  border: 1px solid rgba(255, 255, 255, 0.5) !important;
  overflow: hidden;
}
.maplibregl-ctrl-group button { width: 40px !important; height: 40px !important; }
.maplibregl-ctrl-group button + button { border-top: 1px solid rgba(226, 232, 240, 0.8) !important; }
.maplibregl-ctrl-group button:hover { background-color: #f8fafc !important; }
.maplibregl-popup-content {
  padding: 0 !important;
  border-radius: 16px !important;
  font-family: 'DM Sans', sans-serif !important;
  background: rgba(255, 255, 255, 0.98) !important;
  backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(63, 103, 117, 0.15) !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15) !important;
}
.maplibregl-popup-close-button { font-size: 20px !important; padding: 8px 12px !important; color: #64748b !important; }
.maplibregl-popup-close-button:hover { color: #1e293b !important; background: #f1f5f9 !important; }
</style>
