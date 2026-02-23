<script setup>
import { ref, onMounted, watch } from 'vue';
import MapContainer from './components/MapContainer.vue';
import SearchHUD from './components/SearchHUD.vue';
import LayerSwitcher from './components/LayerSwitcher.vue';
import ParcelPanel from './components/ParcelPanel.vue';
import CreditModal from './components/CreditModal.vue';
import client from './api/client';
import { useParcelSelection } from './composables/useParcelSelection';

// Parcel Selection with URL Deep Linking
const { selectedParcelId, selectParcel, clearSelection, hasSelection } = useParcelSelection();

// State
const userBalance = ref(0);
const selectedTransaction = ref(null);
const showParcelPanel = ref(true);  // Panel visible by default
const relatedParcels = ref([]);  // For hover filiation highlight
const showCreditModal = ref(false);
const mapCenter = ref([-1.6778, 48.1173]); // Rennes default
const transactions = ref({ type: 'FeatureCollection', features: [] });
const loading = ref(false);
const mapMode = ref('prix'); // 'prix' or 'zan'
const activeFilter = ref(null);
const mapRef = ref(null);

// Auto-open panel when parcel selected via URL
watch(hasSelection, (selected) => {
  if (selected && !showParcelPanel.value) {
    showParcelPanel.value = true;
  }
});

// API Calls
const fetchUser = async () => {
  try {
    const res = await client.get('/users/me');
    userBalance.value = res.data.credit_balance;
  } catch (err) {
    console.error("Auth error:", err);
    userBalance.value = 5; // Demo balance
  }
};

const fetchTransactionsInRadius = async (lon, lat) => {
  loading.value = true;
  try {
    const res = await client.get(`/land/search/enriched`, {
      params: { lat, lon, radius: 500, limit: 200 }
    });
    
    const features = res.data.mutations.map(m => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [m.mutation.longitude, m.mutation.latitude]
      },
      properties: {
        ...m.mutation,
        prix_m2: parseFloat(m.mutation.prix_m2) || 0,
        valeur_fonciere: parseFloat(m.mutation.valeur_fonciere) || 0,
        scores: m.enrichment
      }
    }));
    
    transactions.value = { type: 'FeatureCollection', features };
  } catch (err) {
    console.error("Search error:", err);
  } finally {
    loading.value = false;
  }
};

const generateReport = async () => {
  if (!selectedTransaction.value) return;
  
  if (userBalance.value < 1) {
    showCreditModal.value = true;
    return;
  }

  try {
    const id = selectedTransaction.value.id_mutation;
    const res = await client.get(`/transactions/report/${id}`, {
      params: { format: 'pdf' },
      responseType: 'blob'
    });
    
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `rapport_${id}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    
    await fetchUser();
  } catch (err) {
    console.error("Report error:", err);
    alert("Erreur lors de la génération du rapport.");
  }
};

// Event Handlers
const onAddressSelect = (data) => {
  mapCenter.value = data.coordinates;
  fetchTransactionsInRadius(data.coordinates[0], data.coordinates[1]);
};

const onTransactionClick = (feature) => {
  selectedTransaction.value = feature.properties;
};

const onParcelClick = (feature) => {
  selectParcel(feature.properties.id_parcelle, feature.properties);
  showParcelPanel.value = true;
};

const onPanelClose = () => {
  showParcelPanel.value = false;
  // Don't clear selection - keep parcel highlighted even with panel closed
};

const onHighlightRelated = (parcelIds) => {
  relatedParcels.value = parcelIds || [];
};

const onMapModeChange = (mode) => {
  mapMode.value = mode;
};

const onFilterChange = (filter) => {
  activeFilter.value = filter;
};

// Lifecycle
onMounted(() => {
  fetchUser();
  fetchTransactionsInRadius(mapCenter.value[0], mapCenter.value[1]);
});
</script>

<template>
  <div class="relative w-screen h-screen overflow-hidden bg-slate-900">
    
    <!-- Full-Screen Map Background -->
    <MapContainer 
      ref="mapRef"
      :center="mapCenter"
      :transactions="transactions"
      :mode="mapMode"
      :selected-parcel="selectedParcelId"
      :related-parcels="relatedParcels"
      class="absolute inset-0"
      @transaction-click="onTransactionClick"
      @parcel-click="onParcelClick"
    />

    <!-- Floating Search HUD (Top Center) -->
    <SearchHUD 
      :balance="userBalance"
      class="absolute top-6 left-1/2 -translate-x-1/2 z-30"
      @search-select="onAddressSelect"
      @buy-credits="showCreditModal = true"
      @filter-change="onFilterChange"
    />

    <!-- Layer Switcher (Bottom Left) -->
    <LayerSwitcher 
      class="absolute bottom-6 left-6 z-30"
      @change="onMapModeChange"
    />

    <!-- Loading Indicator -->
    <Transition
      enter-active-class="transition-opacity duration-300"
      leave-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div 
        v-if="loading" 
        class="absolute top-24 left-1/2 -translate-x-1/2 z-40 
               bg-white/90 backdrop-blur-lg rounded-full px-6 py-3 
               shadow-lg flex items-center gap-3"
      >
        <div class="w-5 h-5 border-2 border-sage-500 border-t-transparent rounded-full animate-spin"></div>
        <span class="text-sm font-medium text-slate-700">Chargement des données...</span>
      </div>
    </Transition>

    <!-- Expert Panel (Right Sidebar) - Slide In -->
    <ParcelPanel 
      :is-open="showParcelPanel"
      :parcel-id="selectedParcelId"
      @close="onPanelClose"
      @highlight-related="onHighlightRelated"
    />

    <!-- Credit Modal -->
    <CreditModal 
      :is-open="showCreditModal"
      @close="showCreditModal = false"
      @success="fetchUser"
    />

    <!-- Branding Watermark -->
    <div class="absolute bottom-6 right-6 z-20 flex items-center gap-2 
                bg-white/80 backdrop-blur-md rounded-lg px-4 py-2 shadow-md">
      <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-sage-500 to-sage-700 
                  flex items-center justify-center shadow-md">
        <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
        </svg>
      </div>
      <div>
        <p class="text-sm font-bold text-slate-800">Foncier<span class="text-sage-600">Express</span></p>
        <p class="text-[10px] text-slate-400 -mt-0.5">Analyse foncière premium</p>
      </div>
    </div>
  </div>
</template>

<style>
/* Global app styles */
#app {
  width: 100%;
  height: 100%;
}
</style>
