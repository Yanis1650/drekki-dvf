<script setup>
import MapContainer from '../components/MapContainer.vue';
import MapFooterKpi from '../components/layout/MapFooterKpi.vue';

defineProps({
  status: String,
  radius: { type: Number, default: 500 },
  transactions: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  center: { type: Array, default: () => [-1.6778, 48.1173] },
  mode: { type: String, default: 'prix' },
  activeFilter: { type: String, default: null },
  selectedParcel: { type: String, default: null },
  relatedParcels: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(['parcel-click', 'context-error']);

// Cliquer un point de mutation revient à ouvrir la parcelle qui la porte.
const onTransactionClick = (feature) => {
  if (feature?.properties?.id_parcelle) emit('parcel-click', feature);
};
</script>

<template>
  <div class="absolute inset-0 flex flex-col">
    <div class="flex-1 relative min-h-0">
      <MapContainer
        :center="center"
        :radius="radius"
        :transactions="transactions"
        :mode="mode"
        :active-filter="activeFilter"
        :selected-parcel="selectedParcel"
        :related-parcels="relatedParcels"
        class="absolute inset-0"
        @parcel-click="$emit('parcel-click', $event)"
        @transaction-click="onTransactionClick"
        @context-error="$emit('context-error', $event)"
      />

      <Transition
        enter-active-class="transition-opacity duration-data"
        leave-active-class="transition-opacity duration-data"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
          <p class="flex items-center gap-3 bg-surface rounded px-4 py-2 border border-rule-strong shadow-overlay">
            <span class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" aria-hidden="true"></span>
            <span class="text-body text-ink-2">Chargement des mutations…</span>
          </p>
        </div>
      </Transition>
    </div>

    <MapFooterKpi v-if="status === 'ready' || status === 'empty'" :transactions="transactions" />
  </div>
</template>
