<script setup>
import { ref, computed, watch, onUnmounted, onMounted } from 'vue';
import client from '../../api/client';

import ParcelHeader    from './ParcelHeader.vue';
import ParcelStats     from './ParcelStats.vue';
import ParcelPriceChart from './ParcelPriceChart.vue';
import DensificationGauge from './DensificationGauge.vue';
import ConfidenceBadge from './ConfidenceBadge.vue';
import FiliationTimeline from './FiliationTimeline.vue';
import TransactionHistory from './TransactionHistory.vue';
import ScoreBar        from '../ScoreBar.vue';
import {
  TruckIcon,
  AcademicCapIcon,
  ShoppingBagIcon,
  HeartIcon,
} from '@heroicons/vue/24/solid';

const props = defineProps({
  parcelId: { type: String, default: null },
  sectorAvgPriceM2: { type: Number, default: 0 },
});

const emit = defineEmits(['close', 'highlight-related']);
const panelRoot = ref(null);
let previousFocus;
onMounted(() => { previousFocus = document.activeElement; panelRoot.value?.focus(); });
onUnmounted(() => previousFocus?.focus?.());

// ─── Tabs ────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'resume',        label: 'Résumé'    },
  { id: 'marche',        label: 'Marché'    },
  { id: 'densification', label: 'ZAN'       },
  { id: 'historique',    label: 'Hist.'     },
  { id: 'filiation',     label: 'Filiation' },
];
const activeTab = ref('resume');

// ─── Panel resize ────────────────────────────────────────────────────────────
const panelWidth  = ref(440);
const MIN_WIDTH   = 360;
const MAX_WIDTH   = 720;
let rStartX = 0;
let rStartW = 0;

function startResize(e) {
  e.preventDefault();
  rStartX = e.clientX;
  rStartW = panelWidth.value;
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup',  onStop);
  document.body.style.cursor     = 'col-resize';
  document.body.style.userSelect = 'none';
}
function onMove(e) {
  const w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, rStartW + rStartX - e.clientX));
  panelWidth.value = Math.round(w);
}
function onStop() {
  document.removeEventListener('mousemove', onMove);
  document.removeEventListener('mouseup',  onStop);
  document.body.style.cursor     = '';
  document.body.style.userSelect = '';
}

// ─── State ───────────────────────────────────────────────────────────────────
const loading          = ref(false);
const error            = ref(null);
const transactions     = ref([]);
const fiche            = ref(null);
const densification    = ref(null);
const parcelCoords     = ref(null);
const generatingReport = ref(false);
const showScores       = ref(false);

// ─── Computed ────────────────────────────────────────────────────────────────
const sortedTx = computed(() =>
  [...transactions.value].sort((a, b) => new Date(a.date) - new Date(b.date))
);

const avgPriceM2 = computed(() => {
  const prices = transactions.value.filter(t => !t.is_outlier).map(t => Number(t.price_m2)).filter(p => Number.isFinite(p) && p > 0);
  return prices.length ? prices.reduce((a,b) => a+b, 0) / prices.length : null;
});
const lastSaleDate = computed(() => [...transactions.value].map(t => t.date).filter(Boolean).sort().at(-1) || 'NON RELEVÉ');

const qualityScores = computed(() => {
  const e = fiche.value?.enrichment || {};
  return [
    { id: 'transport', label: 'Transports & Mobilité',  score: e.transport ?? null, icon: TruckIcon       },
    { id: 'education', label: 'Éducation & Services',   score: e.education ?? null, icon: AcademicCapIcon },
    { id: 'commerce',  label: 'Commerces & Vie locale', score: e.commerce  ?? null, icon: ShoppingBagIcon },
    { id: 'calme',     label: 'Calme & Environnement',  score: e.calme     ?? null, icon: HeartIcon       },
  ];
});

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (v) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v);

// ─── Report ──────────────────────────────────────────────────────────────────
const generateReport = async () => {
  if (!props.parcelId || generatingReport.value) return;
  generatingReport.value = true;
  try {
    const res = await client.get(`/reports/parcel/${props.parcelId}/pdf`, { responseType: 'blob' });
    const url  = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `rapport_${props.parcelId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error('Report error:', err);
    let msg = 'Erreur lors de la génération du rapport.';
    if (err?.response?.data instanceof Blob) {
      try { msg = JSON.parse(await err.response.data.text())?.detail || msg; } catch {}
    }
    alert(msg);
  } finally {
    generatingReport.value = false;
  }
};

let requestVersion = 0;
onUnmounted(() => { requestVersion++; onStop(); });

// ─── Data fetch ──────────────────────────────────────────────────────────────
watch(
  () => props.parcelId,
  async (id) => {
    const request = ++requestVersion;
    if (!id) return;
    loading.value       = true;
    error.value         = null;
    transactions.value  = [];
    fiche.value         = null;
    densification.value = null;
    parcelCoords.value  = null;
    activeTab.value     = 'resume';
    showScores.value    = false;

    try {
      const [histRes, ficheRes] = await Promise.allSettled([
        client.get(`/analytics/parcel/${id}/history`),
        client.get(`/land/parcelles/${id}/fiche`, { validateStatus: s => s < 500 }),
      ]);

      if (request !== requestVersion) return;
      if (histRes.status === 'rejected') error.value = 'Historique DVF NON RELEVÉ : le service n’a pas répondu.';

      if (histRes.status === 'fulfilled') {
        transactions.value = histRes.value.data.transactions || [];
        const first = transactions.value[0];
        if (first?.longitude && first?.latitude) {
          parcelCoords.value = [first.longitude, first.latitude];
        }
      }

      if (
        ficheRes.status === 'fulfilled' &&
        ficheRes.value.status === 200 &&
        ficheRes.value.data
      ) {
        const f = ficheRes.value.data;
        fiche.value = f;
        densification.value = f.ces_actuel != null && f.ces_potentiel != null && f.surface_constructible_restante != null ? {
          ces_actuel:                    Number(f.ces_actuel),
          ces_potentiel:                 Number(f.ces_potentiel),
          categorie:                     f.categorie_densification ?? 'INCONNU',
          surface_constructible_restante: Number(f.surface_constructible_restante),
        } : null;
      }
    } catch (err) {
      if (request === requestVersion) error.value = 'Erreur lors du chargement des données.';
    } finally {
      if (request === requestVersion) { loading.value = false; showScores.value = true; }
    }
  },
  { immediate: true }
);
</script>

<template>
  <div
    class="fixed top-0 right-0 bottom-0 z-50 flex border-l border-rule"
    :style="{ width: panelWidth + 'px', maxWidth: '100vw' }"
    @keydown.esc="$emit('close')"
    ref="panelRoot" tabindex="-1" role="complementary" aria-label="Fiche parcelle"
  >
    <!-- Resize handle (left edge) -->
    <div
      class="hidden md:flex w-3 flex-shrink-0 items-center justify-center cursor-col-resize
       hover:bg-accent-soft transition-colors group"
      @mousedown="startResize"
    >
      <div
        class="w-0.5 h-10 bg-surface-2 rounded-full
         group-hover:bg-accent transition-colors"
      ></div>
    </div>

    <!-- Panel body -->
    <div
      class="flex-1 min-w-0 flex flex-col bg-surface overflow-hidden"
    >
      <!-- ── Header ── -->
      <div class="flex-shrink-0 px-5 pt-4 border-b border-rule">
        <div class="flex items-start justify-between gap-3 mb-3">
          <ParcelHeader
            :parcel-id="parcelId"
            :coordinates="parcelCoords"
          />
          <button
            aria-label="Fermer la fiche parcelle"
            @click="$emit('close')"
            class="w-7 h-7 rounded bg-surface-2 hover:bg-surface-2 flex-shrink-0
             flex items-center justify-center transition-colors mt-0.5"
          >
            <svg class="w-3.5 h-3.5 text-ink-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Tabs -->
        <div class="flex gap-0 -mb-px overflow-x-auto no-scrollbar">
          <button
            v-for="tab in TABS"
            :key="tab.id"
            @click="activeTab = tab.id"
            class="flex-shrink-0 px-4 py-2.5 text-meta font-semibold
             whitespace-nowrap transition-colors border-b-2"
            :class="activeTab === tab.id
             ? 'border-accent text-accent'
             : 'border-transparent text-ink-3 hover:text-ink-2 hover:border-rule'"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- ── Tab content ── -->
      <div class="flex-1 overflow-y-auto custom-scrollbar">

        <!-- Loading -->
        <div v-if="loading" class="flex flex-col items-center justify-center h-52 gap-3">
          <div class="w-9 h-9 border-[3px] border-rule border-t-sage-500 rounded-full animate-spin"></div>
          <p class="text-body text-ink-3">Chargement…</p>
        </div>

        <!-- Error -->
        <div v-if="error" class="flex items-center justify-center h-52 px-6 text-center">
          <p class="text-body text-alert">{{ error }}</p>
        </div>

        <!-- ── Résumé ── -->
        <div v-if="!loading && activeTab === 'resume'" class="p-5 space-y-4 animate-fade-in">

          <p class="fe-meta">Fiche parcellaire : historique complet, indépendant de la période du secteur. Source : DVF et enrichissements Foncier Express.</p>
          <p v-if="densification" class="cartouche p-3 fe-estimated">Surface restante modélisée : {{ densification.surface_constructible_restante.toLocaleString('fr-FR') }} m². À vérifier au regard des règles d’urbanisme.</p>

          <!-- Confidence -->
          <ConfidenceBadge
            v-if="fiche?.confidence_global != null"
            :confidence-global="fiche.confidence_global"
            :confidence-label="fiche.confidence_label"
            :score-bdnb="fiche.score_bdnb"
            :score-dvf="fiche.score_dvf"
            :score-densification="fiche.score_densification"
            :score-fraicheur="fiche.score_fraicheur"
            :source-ces="fiche.source_ces"
            :warning="fiche.warning"
          />

          <p v-if="fiche?.confidence_global == null" class="fe-absent p-3 text-meta">Indice de confiance : NON RELEVÉ.</p>
          <!-- Stats -->
          <ParcelStats
            :transaction-count="transactions.length"
            :history-available="!error"
            :avg-price-m2="avgPriceM2"
            :last-sale-date="lastSaleDate"
            :sector-avg-price-m2="sectorAvgPriceM2"
          />

          <!-- Fiche unavailable -->
          <div
            v-if="!fiche && !loading"
            class="p-3 rounded bg-warn-soft border border-warn text-meta text-warn"
          >
            ℹ️ Données d'expertise non disponibles pour cette parcelle.
          </div>
        </div>

        <!-- ── Marché ── -->
        <div v-else-if="!loading && activeTab === 'marche'" class="p-5 space-y-5 animate-fade-in">
          <ParcelPriceChart
            v-if="sortedTx.length > 0"
            :transactions="sortedTx"
          />
          <div
            v-else
            class="flex items-center justify-center h-32 text-ink-3 text-body"
          >
            Aucune transaction disponible
          </div>

          <!-- Quality scores -->
          <div v-if="fiche" class="space-y-3">
            <p class="text-label font-semibold uppercase tracking-wider text-ink-3">Qualité de vie</p>
            <ScoreBar
              v-for="s in qualityScores"
              :key="s.id"
              :label="s.label"
              :score="s.score"
              :icon="s.icon"
              :gradient="s.gradient"
              :animate="showScores"
            />
          </div>
        </div>

        <!-- ── Densification ── -->
        <div v-else-if="activeTab === 'densification'" class="p-5 animate-fade-in">
          <DensificationGauge
            v-if="densification"
            :ces-actuel="densification.ces_actuel"
            :ces-plu="densification.ces_potentiel"
            :categorie="densification.categorie"
            :surface-constructible="densification.surface_constructible_restante"
            :source-ces="fiche?.source_ces"
            :libelle-zone="fiche?.libelle_zone"
          />
          <div
            v-else
            class="flex items-center justify-center h-32 text-ink-3 text-body"
          >
            Score de densification non disponible
          </div>
        </div>

        <!-- ── Historique ── -->
        <div v-else-if="activeTab === 'historique'" class="p-5 animate-fade-in">
          <TransactionHistory
            v-if="transactions.length > 0"
            :transactions="transactions"
          />
          <div
            v-else
            class="flex items-center justify-center h-32 text-ink-3 text-body"
          >
            Aucun historique disponible
          </div>
        </div>

        <!-- ── Filiation ── -->
        <div v-else-if="activeTab === 'filiation'" class="p-5 animate-fade-in">
          <FiliationTimeline
            v-if="parcelId"
            :id-parcelle="parcelId"
            @highlight-parcels="$emit('highlight-related', $event)"
          />
        </div>
      </div>

      <!-- ── Footer: Report button ── -->
      <div
        v-if="parcelId"
        class="flex-shrink-0 px-5 py-4 bg-surface border-t border-rule"
      >
        <button
          @click="generateReport"
          :disabled="generatingReport"
          class="btn btn--primary w-full py-3"
        >
          <svg
            v-if="!generatingReport"
            class="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <div
            v-else
            class="w-4 h-4 border-2 border-accent-ink/30 border-t-accent-ink rounded-full animate-spin"
          ></div>
          <span>{{ generatingReport ? 'Génération…' : 'Rapport Expert PDF' }}</span>
          <span class="ml-auto px-2 py-0.5 bg-accent-ink/15 rounded text-meta font-semibold">
            Gratuit
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
