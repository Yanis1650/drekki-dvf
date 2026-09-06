<script setup>
import { ref, computed, onMounted, onUnmounted, watch, provide, defineAsyncComponent } from 'vue';
import AppTopbar          from './components/layout/AppTopbar.vue';
import AppSidebar         from './components/layout/AppSidebar.vue';
import StudyStatus from './components/StudyStatus.vue';
import { useStudyArea } from './composables/useStudyArea.js';
import { createDossierStore, DOSSIERS_KEY } from './composables/useDossiers.js';
import client             from './api/client';
import { useParcelSelection } from './composables/useParcelSelection';
import { useRoute } from 'vue-router';
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
  <div class="h-dvh flex flex-col overflow-hidden bg-ground">

    <!-- Topbar -->
    <AppTopbar
      :map-mode="mapMode"
      :loading="loading"
      @search-select="onAddressSelect"
      @update:map-mode="mapMode = $event"
    />

    <div class="flex-1 flex min-h-0">
      <AppSidebar />
      <div class="flex-1 flex flex-col min-w-0 min-h-0">
    <div class="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 bg-ground text-body">
      <strong class="text-ink">{{ label }}</strong>
      <label>Rayon <select v-model.number="radius" class="bg-surface-2 border border-rule rounded px-2 py-1"><option :value="500">500 m</option><option :value="1000">1 km</option><option :value="5000">5 km</option></select></label>
      <label><input v-model="recent" type="checkbox"> Deux dernières années</label>
      <span class="text-meta text-ink-3 hidden xl:block ml-auto">Un périmètre commun à vos analyses</span>
    </div>
    <StudyStatus :status="status" :error="error" :capped="capped" :stats="stats" :enrichment-available="enrichmentAvailable" @retry="refresh" />
      <main class="flex-1 min-h-0 min-w-0 relative overflow-hidden m-2 lg:m-3 border border-rule rounded bg-surface">
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
    <aside v-if="!hasSelection && route.path === '/'" aria-label="Commencer une analyse" class="hidden xl:flex w-80 shrink-0 flex-col border-l border-rule bg-surface p-6">
      <p class="fe-label">De la carte à la décision</p>
      <h1 class="text-title mt-3">Un lieu, plusieurs<br>façons de le regarder.</h1>
      <p class="text-body text-ink-2 mt-3">Sélectionnez une parcelle pour croiser les repères disponibles avec les critères de votre projet.</p>
      <div class="mt-6 border-y border-rule py-5 space-y-4"><div><span class="fe-label">01 · Comprendre</span><p class="text-body mt-1">Ventes, terrain et potentiel estimé.</p></div><div><span class="fe-label">02 · Mettre en perspective</span><p class="text-body mt-1">Six thèmes, vos priorités et les inconnues.</p></div><div><span class="fe-label">03 · Avancer</span><p class="text-body mt-1">Les points à vérifier et votre prochaine action.</p></div></div>
      <div class="mt-auto pt-8"><p class="text-lead">Prospecter ou préparer une visite ?</p><p class="fe-meta mt-2">Le même dossier s’adapte à votre objectif.</p><RouterLink to="/dossiers" class="btn border border-rule text-accent mt-4">Retrouver mes dossiers</RouterLink></div>
    </aside>
    </div>
  </div>
</template>

<style>
#app {
  width: 100%;
  height: 100%;
}
</style>
