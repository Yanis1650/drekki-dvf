<script setup>
import { ref, computed, onMounted, onUnmounted, watch, provide, defineAsyncComponent } from 'vue';
import AppTopbar          from './components/layout/AppTopbar.vue';
import AppSidebar         from './components/layout/AppSidebar.vue';
import StudyStatus from './components/StudyStatus.vue';
import { useStudyArea } from './composables/useStudyArea.js';
import { createDossierStore, DOSSIERS_KEY } from './composables/useDossiers.js';
import client             from './api/client';
import { useParcelSelection } from './composables/useParcelSelection';

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
const { center: mapCenter, transactions, radius, recent, label, commune, status, error, capped, stats, enrichmentAvailable, refresh } = study;
const loading = computed(() => status.value === 'loading');
const mapMode = ref('prix');
const relatedParcels = ref([]);
const sectorAvgPriceM2 = computed(() => stats.value.avgPrice);
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

// ─── Init ─────────────────────────────────────────────────────────────────────
onMounted(refresh);
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden bg-surface-2">

    <!-- Topbar -->
    <AppTopbar
      :map-mode="mapMode"
      :loading="loading"
      @search-select="onAddressSelect"
      @update:map-mode="mapMode = $event"
    />

    <div class="flex flex-wrap items-center gap-3 px-4 py-2 bg-surface border-b border-rule text-body">
      <strong class="text-ink">{{ label }}</strong>
      <label>Rayon <select v-model.number="radius" class="bg-surface-2 border border-rule rounded px-2 py-1"><option :value="500">500 m</option><option :value="1000">1 km</option><option :value="5000">5 km</option></select></label>
      <label><input v-model="recent" type="checkbox"> Deux dernières années</label>
      <span class="text-meta text-ink-3">Carte, KPI et Marché : même recherche. Déplacer la carte conserve ce périmètre.</span>
    </div>
    <StudyStatus :status="status" :error="error" :capped="capped" :stats="stats" :enrichment-available="enrichmentAvailable" @retry="refresh" />
    <!-- Content: sidebar + main -->
    <div class="flex-1 flex min-h-0">
      <AppSidebar />

      <main class="flex-1 relative overflow-hidden">
        <RouterView v-slot="{ Component }">
          <component
            :is="Component"
            :transactions="transactions"
            :center="mapCenter"
            :radius="radius"
            :commune="commune"
            :status="status"
            :mode="mapMode"
            :active-filter="null"
            :selected-parcel="selectedParcelId"
            :related-parcels="relatedParcels"
            :loading="loading"
            @parcel-click="onParcelClick"
          />
        </RouterView>
      </main>
    </div>

    <!-- Parcel panel — persists across route changes -->
    <Transition
      enter-active-class="transition-all duration-[350ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
      leave-active-class="transition-all duration-[350ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
      enter-from-class="translate-x-full opacity-0"
      leave-to-class="translate-x-full opacity-0"
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
</template>

<style>
#app {
  width: 100%;
  height: 100%;
}
</style>
