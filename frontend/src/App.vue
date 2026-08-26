<script setup>
import { ref, computed, onMounted } from 'vue';
import AppTopbar          from './components/layout/AppTopbar.vue';
import AppSidebar         from './components/layout/AppSidebar.vue';
import ParcelPanelTabbed  from './components/parcel/ParcelPanelTabbed.vue';
import CreditModal        from './components/CreditModal.vue';
import client             from './api/client';
import { useParcelSelection } from './composables/useParcelSelection';

const { selectedParcelId, selectParcel, clearSelection, hasSelection } = useParcelSelection();

// ─── Global state ─────────────────────────────────────────────────────────────
const userBalance    = ref(0);
const showCreditModal = ref(false);
const mapCenter      = ref([-1.6778, 48.1173]); // Rennes default
const transactions   = ref({ type: 'FeatureCollection', features: [] });
const loading        = ref(false);
const mapMode        = ref('prix');
const activeFilter   = ref(null);
const relatedParcels = ref([]);
const backendOffline = ref(false);

const sectorAvgPriceM2 = computed(() => {
  const features = transactions.value?.features || [];
  const valid = features.filter(f => f.properties.prix_m2 && !f.properties.is_outlier);
  if (!valid.length) return 0;
  return valid.reduce((s, f) => s + f.properties.prix_m2, 0) / valid.length;
});

const isNetworkError = (err) =>
  err?.code === 'ERR_NETWORK' || err?.message?.includes('Network Error');

// ─── API ──────────────────────────────────────────────────────────────────────
const fetchUser = async () => {
  try {
    const res = await client.get('/users/me');
    userBalance.value    = res.data.credit_balance;
    backendOffline.value = false;
  } catch (err) {
    if (isNetworkError(err)) backendOffline.value = true;
    userBalance.value = 5; // demo balance
  }
};

const fetchTransactionsInRadius = async (lon, lat) => {
  loading.value = true;
  try {
    const res = await client.get('/land/search/enriched', {
      params: { lat, lon, radius: 500, limit: 200 },
    });
    transactions.value = {
      type: 'FeatureCollection',
      features: res.data.mutations.map((m) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [m.mutation.longitude, m.mutation.latitude],
        },
        properties: {
          ...m.mutation,
          prix_m2: parseFloat(m.mutation.prix_m2) || 0,
          valeur_fonciere: parseFloat(m.mutation.valeur_fonciere) || 0,
          scores: m.enrichment,
        },
      })),
    };
  } catch (err) {
    if (isNetworkError(err)) backendOffline.value = true;
    console.error('Search error:', err);
  } finally {
    loading.value = false;
  }
};

// ─── Event handlers ───────────────────────────────────────────────────────────
const onAddressSelect = (data) => {
  mapCenter.value = data.coordinates;
  fetchTransactionsInRadius(data.coordinates[0], data.coordinates[1]);
};

const onParcelClick = (feature) => {
  selectParcel(feature.properties.id_parcelle, feature.properties);
};

const onHighlightRelated = (parcelIds) => {
  relatedParcels.value = parcelIds || [];
};

// ─── Init ─────────────────────────────────────────────────────────────────────
onMounted(() => {
  fetchUser();
  fetchTransactionsInRadius(mapCenter.value[0], mapCenter.value[1]);
});
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden bg-slate-100">

    <!-- Offline banner -->
    <Transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 -translate-y-full"
      leave-to-class="opacity-0 -translate-y-full"
    >
      <div
        v-if="backendOffline"
        class="flex-shrink-0 bg-amber-400 text-slate-900 px-4 py-2
               text-center text-xs font-semibold z-50"
      >
        ⚠️ API backend inaccessible —
        <code class="bg-black/10 px-1.5 py-0.5 rounded text-[11px]">
          uvicorn app.main:app --reload --port 8000
        </code>
      </div>
    </Transition>

    <!-- Topbar -->
    <AppTopbar
      :balance="userBalance"
      :active-filter="activeFilter"
      :map-mode="mapMode"
      :loading="loading"
      @search-select="onAddressSelect"
      @buy-credits="showCreditModal = true"
      @update:active-filter="activeFilter = $event"
      @update:map-mode="mapMode = $event"
    />

    <!-- Content: sidebar + main -->
    <div class="flex-1 flex min-h-0">
      <AppSidebar />

      <main class="flex-1 relative overflow-hidden">
        <RouterView v-slot="{ Component }">
          <component
            :is="Component"
            :transactions="transactions"
            :center="mapCenter"
            :mode="mapMode"
            :active-filter="activeFilter"
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

    <!-- Credit modal -->
    <CreditModal
      :is-open="showCreditModal"
      @close="showCreditModal = false"
      @success="fetchUser"
    />
  </div>
</template>

<style>
#app {
  width: 100%;
  height: 100%;
}
</style>
