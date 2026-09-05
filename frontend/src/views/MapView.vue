<script setup>
import MapLegend from '../components/MapLegend.vue';
import MapContainer from '../components/MapContainer.vue';
import MapFooterKpi from '../components/layout/MapFooterKpi.vue';

const props = defineProps({
  status: String,
  radius: { type: Number, default: 500 },
  transactions: { type: Object,  default: () => ({ type: 'FeatureCollection', features: [] }) },
  center:        { type: Array,   default: () => [-1.6778, 48.1173] },
  mode:          { type: String,  default: 'prix' },
  activeFilter:  { type: String,  default: null },
  selectedParcel:{ type: String,  default: null },
  relatedParcels:{ type: Array,   default: () => [] },
  loading:       { type: Boolean, default: false },
});

const emit = defineEmits(['parcel-click']);

const onTransactionClick = (feature) => {
  // clicking a transaction dot → select its parcel in the panel
  if (feature?.properties?.id_parcelle) {
    emit('parcel-click', feature);
  }
};
</script>

<template>
  <div class="absolute inset-0 flex flex-col">
    <!-- Map fills all space above the KPI bar -->
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
      />

      <MapLegend :mode="mode" />
      <!-- Loading overlay -->
      <Transition
        enter-active-class="transition-opacity duration-300"
        leave-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="loading"
          class="absolute inset-0 flex items-center justify-center z-20 pointer-events-none"
        >
          <div
            class="flex items-center gap-3 bg-surface rounded-full px-6 py-3 border border-rule-strong"
          >
            <div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
            <span class="text-body font-medium text-ink-2">Chargement des données…</span>
          </div>
        </div>
      </Transition>
    </div>

    <p class="bg-surface px-4 py-1 text-meta text-ink-2">Contour bleu : périmètre DVF · fonds parcellaires : contexte cadastral indépendant des dates de vente.</p>
    <!-- KPI footer bar -->
    <MapFooterKpi v-if="status === 'ready' || status === 'empty'" :transactions="transactions" />
  </div>
</template>
