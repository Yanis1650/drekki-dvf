<script setup>
import { ref, computed, onMounted, onUnmounted, watch, provide, defineAsyncComponent } from 'vue';
import { useRoute } from 'vue-router';
import AppTopbar from './components/layout/AppTopbar.vue';
import AppSidebar from './components/layout/AppSidebar.vue';
import StudyRail from './components/layout/StudyRail.vue';
import StudyStatus from './components/StudyStatus.vue';
import { useStudyArea } from './composables/useStudyArea.js';
import { createDossierStore, DOSSIERS_KEY } from './composables/useDossiers.js';
import client from './api/client';
import { useParcelSelection } from './composables/useParcelSelection';

const route = useRoute();

// Le panneau ne s'affiche qu'après un clic sur une parcelle : le charger à la
// demande sort ses graphiques du bundle initial.
const ParcelPanelTabbed = defineAsyncComponent(
  () => import('./components/parcel/ParcelPanelTabbed.vue'),
);

let dossierStorage;
try { dossierStorage = window.localStorage; } catch { /* Browser privacy settings can disable storage. */ }
provide(DOSSIERS_KEY, createDossierStore(dossierStorage));

const { selectedParcelId, selectParcel, clearSelection, hasSelection } = useParcelSelection();

// ─── Global state ─────────────────────────────────────────────────────────────
const study = useStudyArea(client);
const {
  center: mapCenter, transactions, radius, recent, label, commune,
  status, error, capped, stats, enrichmentAvailable, refresh,
} = study;
const loading = computed(() => status.value === 'loading');
const mapMode = ref('prix');
const relatedParcels = ref([]);
const sectorAvgPriceM2 = computed(() => stats.value.avgPrice);
const isMap = computed(() => route.name === 'map');

// Disponibilité constatée du fond parcellaire : `null` tant que la carte n'a
// pas eu à le charger. Une ignorance n'est pas une absence. La carte émet une
// chaîne vide quand le contexte cadastral a répondu, son message d'erreur
// sinon.
const cadastreAvailable = ref(null);
const onContextError = (message) => { cadastreAvailable.value = !message; };

watch([radius, recent], refresh);
watch(selectedParcelId, () => { relatedParcels.value = []; });
onUnmounted(study.dispose);

// ─── Event handlers ───────────────────────────────────────────────────────────
const onAddressSelect = (data) => {
  mapCenter.value = data.coordinates;
  label.value = data.label;
  commune.value = data.citycode || '';
  clearSelection();
  relatedParcels.value = [];
  refresh();
};

const onParcelClick = (feature) => {
  if (feature?.properties?.id_parcelle) selectParcel(feature.properties.id_parcelle, feature.properties);
};

const onHighlightRelated = (parcelIds) => {
  relatedParcels.value = parcelIds || [];
};

onMounted(refresh);
</script>

<template>
  <div class="h-dvh flex flex-col overflow-hidden bg-ground">
    <AppTopbar
      :map-mode="mapMode"
      :radius="radius"
      :recent="recent"
      :loading="loading"
      :show-map-controls="isMap"
      :transactions="transactions"
      :label="label"
      @search-select="onAddressSelect"
      @update:map-mode="mapMode = $event"
      @update:radius="radius = $event"
      @update:recent="recent = $event"
      @refresh="refresh"
    />

    <div class="flex-1 flex min-h-0">
      <AppSidebar />

      <div class="flex-1 flex flex-col min-w-0 min-h-0">
        <StudyStatus
          :status="status"
          :error="error"
          :capped="capped"
          :stats="stats"
          :enrichment-available="enrichmentAvailable"
          @retry="refresh"
        />
        <main class="flex-1 min-h-0 min-w-0 relative overflow-hidden bg-surface">
          <RouterView v-slot="{ Component }">
            <component
              :is="Component"
              :transactions="transactions"
              :center="mapCenter"
              :radius="radius"
              :commune="commune"
              :label="label"
              :status="status"
              :mode="mapMode"
              :active-filter="null"
              :selected-parcel="selectedParcelId"
              :related-parcels="relatedParcels"
              :loading="loading"
              @parcel-click="onParcelClick"
              @context-error="onContextError"
            />
          </RouterView>
        </main>
      </div>

      <StudyRail
        v-if="!hasSelection && isMap"
        :label="label"
        :radius="radius"
        :status="status"
        :stats="stats"
        :mode="mapMode"
        :enrichment-available="enrichmentAvailable"
        :cadastre-available="cadastreAvailable"
      />

      <!-- Fiche parcelle — elle survit aux changements de route. -->
      <Transition
        enter-active-class="transition-transform duration-data ease-fe"
        leave-active-class="transition-transform duration-data ease-fe"
        enter-from-class="translate-x-full"
        leave-to-class="translate-x-full"
      >
        <ParcelPanelTabbed
          v-if="hasSelection"
          :parcel-id="selectedParcelId"
          :sector-avg-price-m2="sectorAvgPriceM2"
          @close="clearSelection"
          @highlight-related="onHighlightRelated"
        />
      </Transition>
    </div>
  </div>
</template>

<style>
#app {
  width: 100%;
  height: 100%;
}
</style>
