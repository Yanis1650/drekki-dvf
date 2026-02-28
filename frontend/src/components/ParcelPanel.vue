<template>
  <Transition name="slide-right">
    <div 
      v-if="isOpen" 
      class="expert-panel"
      :style="{ width: panelWidth + 'px' }"
    >
      <!-- Poignée de redimensionnement -->
      <div 
        class="resize-handle"
        @mousedown="startResize"
        title="Glisser pour redimensionner"
      >
        <div class="resize-handle-line"></div>
      </div>

      <!-- Bouton replier -->
      <button 
        @click="close" 
        class="collapse-btn" 
        title="Fermer le panneau"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
      </button>

      <!-- Header -->
      <ParcelHeader 
        :parcel-id="parcelId"
        :coordinates="parcelCoordinates"
        @close="close"
      />

      <!-- Content -->
      <div class="panel-content custom-scrollbar">
        <!-- Loading State -->
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>Chargement des données...</p>
        </div>

        <!-- Empty State (no parcel selected) -->
        <div v-else-if="!parcelId" class="empty-state">
          <div class="empty-icon">🗺️</div>
          <h3>Sélectionnez une parcelle</h3>
          <p>Cliquez sur une parcelle sur la carte pour voir ses informations détaillées.</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="error-state">
          <p>{{ error }}</p>
        </div>

        <!-- Content Sections -->
        <div v-else class="content-sections">
          <!-- Info: parcelle sans fiche enrichie -->
          <div v-if="parcelId && !fiche && !loading" class="panel-block fiche-unavailable">
            ℹ️ Données d'expertise non disponibles pour cette parcelle.
          </div>
          <!-- Potential Gain Card - priorité haute -->
          <div v-if="densification && avgPriceM2 > 0" class="panel-block gain-card gain-card-prominent">
            <div class="gain-header">
              <span class="gain-icon">💰</span>
              <span class="gain-title">Potentiel Brut Estimé</span>
            </div>
            <div class="gain-value">
              {{ formatCurrency(potentialGain) }}
            </div>
            <p class="gain-formula">
              S<sub>constructible</sub> × P<sub>m²</sub> = {{ densification.surface_constructible_restante.toFixed(0) }} × {{ avgPriceM2.toFixed(0) }}
            </p>
          </div>

          <!-- Confidence Badge -->
          <div class="panel-block">
          <ConfidenceBadge 
            v-if="fiche"
            :confidence-global="fiche.confidence_global"
            :confidence-label="fiche.confidence_label"
            :score-bdnb="fiche.score_bdnb"
            :score-dvf="fiche.score_dvf"
            :score-densification="fiche.score_densification"
            :score-fraicheur="fiche.score_fraicheur"
            :source-ces="fiche.source_ces"
            :warning="fiche.warning"
          />
          </div>

          <!-- Densification Gauge -->
          <div class="panel-block">
          <DensificationGauge 
            v-if="densification"
            :ces-actuel="densification.ces_actuel"
            :ces-plu="densification.ces_potentiel"
            :categorie="densification.categorie"
            :surface-constructible="densification.surface_constructible_restante"
            :source-ces="fiche?.source_ces"
            :libelle-zone="fiche?.libelle_zone"
          />
          </div>

          <!-- Stats Summary -->
          <div class="panel-block">
          <ParcelStats 
            :transaction-count="transactions.length"
            :avg-price-m2="avgPriceM2"
            :last-sale-date="lastSaleDate"
          />
          </div>

          <!-- Price Chart with ApexCharts -->
          <div class="panel-block">
          <ParcelPriceChart 
            v-if="transactions.length > 0"
            :transactions="sortedTransactions"
          />
          </div>

          <!-- Filiation Timeline -->
          <div class="panel-block">
          <FiliationTimeline 
            v-if="parcelId"
            :id-parcelle="parcelId"
            @highlight-parcels="$emit('highlight-related', $event)"
          />
          </div>

          <!-- Transaction History -->
          <div class="panel-block">
          <TransactionHistory 
            v-if="transactions.length > 0"
            :transactions="transactions"
          />
          </div>
        </div>
      </div>

      <!-- Export Button (Fixed Footer) -->
      <div v-if="parcelId" class="panel-footer">
        <button 
          @click="generateReport"
          :disabled="generatingReport"
          class="export-btn"
        >
          <svg v-if="!generatingReport" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div v-else class="btn-spinner"></div>
          <span>{{ generatingReport ? 'Génération...' : 'Rapport Expert PDF' }}</span>
          <span class="credit-cost">1 crédit</span>
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import client from '../api/client';

// Child components
import ParcelHeader from './parcel/ParcelHeader.vue';
import ParcelStats from './parcel/ParcelStats.vue';
import ParcelPriceChart from './parcel/ParcelPriceChart.vue';
import DensificationGauge from './parcel/DensificationGauge.vue';
import ConfidenceBadge from './parcel/ConfidenceBadge.vue';
import FiliationTimeline from './parcel/FiliationTimeline.vue';
import TransactionHistory from './parcel/TransactionHistory.vue';

const MIN_WIDTH = 320;
const MAX_WIDTH = 720;

const props = defineProps({
  isOpen: Boolean,
  parcelId: String,
  expanded: { type: Boolean, default: false }
});

const emit = defineEmits(['close', 'report-generated', 'highlight-related']);

// State
const transactions = ref([]);
const panelWidth = ref(props?.expanded ? 560 : 360);
let resizeStartX = 0;
let resizeStartW = 0;

function getDefaultWidth() {
  return props?.expanded ? 560 : 360;
}

function startResize(e) {
  e.preventDefault();
  resizeStartX = e.clientX;
  resizeStartW = panelWidth.value;
  document.addEventListener('mousemove', onResizeMove);
  document.addEventListener('mouseup', stopResize);
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
}

function onResizeMove(e) {
  const delta = resizeStartX - e.clientX; // Glisser gauche = agrandir
  let w = resizeStartW + delta;
  w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.min(w, window.innerWidth * 0.9)));
  panelWidth.value = Math.round(w);
}

function stopResize() {
  document.removeEventListener('mousemove', onResizeMove);
  document.removeEventListener('mouseup', stopResize);
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
}

const densification = ref(null);
const fiche = ref(null);
const parcelCoordinates = ref(null);
const loading = ref(false);
const error = ref(null);
const generatingReport = ref(false);

// Computed
const sortedTransactions = computed(() => {
  return [...transactions.value].sort((a, b) => new Date(a.date) - new Date(b.date));
});

const avgPriceM2 = computed(() => {
  if (transactions.value.length === 0) return 0;
  const sum = transactions.value.reduce((acc, tx) => acc + (tx.price_m2 || 0), 0);
  return sum / transactions.value.length;
});

const lastSaleDate = computed(() => {
  if (transactions.value.length === 0) return 'N/A';
  const latest = transactions.value[0];
  return formatDate(latest.date);
});

const potentialGain = computed(() => {
  if (!densification.value || avgPriceM2.value === 0) return 0;
  return densification.value.surface_constructible_restante * avgPriceM2.value;
});

// Methods
const close = () => emit('close');

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleDateString('fr-FR', { 
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

const formatCurrency = (value) => {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0
  }).format(value);
};

const generateReport = async () => {
  if (!props.parcelId || generatingReport.value) return;
  
  generatingReport.value = true;
  
  try {
    const response = await client.get(
      `/reports/parcel/${props.parcelId}/pdf`,
      { responseType: 'blob' }
    );
    
    // Download the PDF
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `rapport_parcelle_${props.parcelId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    
    emit('report-generated');
  } catch (err) {
    console.error('Error generating report:', err);
    let msg = 'Erreur lors de la génération du rapport.';
    if (err?.response?.data) {
      if (err.response.data instanceof Blob) {
        try {
          const json = JSON.parse(await err.response.data.text());
          msg = json.detail || msg;
        } catch (_) {}
      } else {
        msg = err.response.data.detail || msg;
      }
    } else if (err?.message) {
      msg = err.message;
    }
    alert(msg);
  } finally {
    generatingReport.value = false;
  }
};

// Data fetching
watch(() => props.parcelId, async (newId) => {
  if (!newId || !props.isOpen) return;

  loading.value = true;
  error.value = null;
  transactions.value = [];
  densification.value = null;
  fiche.value = null;
  parcelCoordinates.value = null;

  try {
    const [historyRes, ficheRes] = await Promise.allSettled([
      client.get(`/analytics/parcel/${newId}/history`),
      client.get(`/land/parcelles/${newId}/fiche`, {
        validateStatus: (s) => s < 500,
      }),
    ]);

    // Transaction history
    if (historyRes.status === 'fulfilled') {
      transactions.value = historyRes.value.data.transactions || [];
      if (transactions.value.length > 0 && transactions.value[0].longitude && transactions.value[0].latitude) {
        parcelCoordinates.value = [transactions.value[0].longitude, transactions.value[0].latitude];
      }
    }

    // Fiche complete (DVF + BDNB + densification + confiance)
    if (ficheRes.status === 'fulfilled' && ficheRes.value.status === 200 && ficheRes.value.data) {
      const f = ficheRes.value.data;
      fiche.value = f;
      densification.value = {
        ces_actuel: f.ces_actuel ?? 0,
        ces_potentiel: f.ces_potentiel ?? 0,
        categorie: f.categorie_densification ?? 'INCONNU',
        surface_constructible_restante: f.surface_constructible_restante ?? 0,
      };
    }
  } catch (err) {
    console.error('Error loading parcel data:', err);
    error.value = 'Erreur lors du chargement des données';
  } finally {
    loading.value = false;
  }
}, { immediate: true });

watch(() => props.expanded, () => {
  panelWidth.value = getDefaultWidth();
}, { immediate: false });
</script>

<style scoped>
/* Slide depuis la droite */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* Panneau à droite, largeur variable et redimensionnable */
.expert-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  min-width: 320px;
  max-width: 90vw;
  background: white;
  box-shadow: -8px 0 40px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  z-index: 50;
  transition: box-shadow 0.2s ease;
}

/* Poignée de redimensionnement (bord gauche du panneau) */
.resize-handle {
  position: absolute;
  left: -6px;
  top: 0;
  bottom: 0;
  width: 12px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 15;
  transition: background 0.15s;
}

.resize-handle:hover,
.resize-handle:active {
  background: rgba(82, 127, 140, 0.06);
}

.resize-handle-line {
  width: 3px;
  height: 48px;
  background: #cbd5e1;
  border-radius: 2px;
  opacity: 0.6;
}

.resize-handle:hover .resize-handle-line {
  opacity: 1;
  background: #527f8c;
}

/* Blocs de contenu cohérents : rayon uniforme, espacement */
.panel-block {
  border-radius: 12px;
  overflow: hidden;
}

.panel-block.fiche-unavailable {
  padding: 12px 16px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  color: #b45309;
  font-size: 13px;
}

.panel-block.gain-card {
  border: none;
}

.content-sections .panel-block > * {
  border-radius: 12px;
}

/* Collapse Button : à gauche de la poignée de resize */
.collapse-btn {
  position: absolute;
  top: 50%;
  left: -40px;
  transform: translateY(-50%);
  width: 32px;
  height: 64px;
  background: white;
  border: none;
  border-radius: 8px 0 0 8px;
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: all 0.2s ease;
  z-index: 10;
}

.collapse-btn:hover {
  background: #f1f5f9;
  color: #1e293b;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 32px;
  color: #64748b;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 24px;
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 12px 0;
}

.empty-state p {
  font-size: 14px;
  margin: 0;
  line-height: 1.6;
}

/* Content : padding cohérent sur tout le bandeau */
.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  padding-left: 24px;
  padding-right: 24px;
}

.content-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Gain Card - priorité visuelle haute */
.gain-card {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 2px solid #f59e0b;
  border-radius: 16px;
  padding: 20px;
}

.gain-card-prominent .gain-value {
  font-size: 36px;
}

.gain-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.gain-icon {
  font-size: 20px;
}

.gain-title {
  font-size: 13px;
  font-weight: 700;
  color: #92400e;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.gain-value {
  font-size: 32px;
  font-weight: 800;
  color: #78350f;
  margin-bottom: 8px;
}

.gain-formula {
  font-size: 12px;
  color: #a16207;
  font-family: 'JetBrains Mono', monospace;
  margin: 0;
}

/* Loading & Error States */
.loading-state,
.error-state {
  text-align: center;
  padding: 60px 24px;
  color: #64748b;
}

.error-state {
  color: #ef4444;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e2e8f0;
  border-top-color: #527f8c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer : padding cohérent avec le contenu */
.panel-footer {
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #e2e8f0;
}

.export-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 14px 24px;
  background: linear-gradient(135deg, #527f8c, #3f6775);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 14px rgba(82, 127, 140, 0.4);
}

.export-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(82, 127, 140, 0.5);
}

.export-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.credit-cost {
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
}

.btn-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Responsive */
@media (max-width: 640px) {
  .expert-panel {
    width: 100%;
    max-width: 100%;
  }
}
</style>
