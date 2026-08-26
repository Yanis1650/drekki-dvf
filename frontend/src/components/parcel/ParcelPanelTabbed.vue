<script setup>
import { ref, computed, watch } from 'vue';
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
  const arr = transactions.value;
  if (!arr.length) return 0;
  return arr.reduce((s, t) => s + (t.price_m2 || 0), 0) / arr.length;
});

const lastSaleDate = computed(() => {
  if (!transactions.value.length) return 'N/A';
  const d = transactions.value[0]?.date;
  return d
    ? new Date(d).toLocaleDateString('fr-FR', { year: 'numeric', month: 'short', day: 'numeric' })
    : 'N/A';
});

const potentialGain = computed(() => {
  if (!densification.value || avgPriceM2.value === 0) return 0;
  return densification.value.surface_constructible_restante * avgPriceM2.value;
});

const qualityScores = computed(() => {
  const e = fiche.value?.enrichment || {};
  return [
    { id: 'transport', label: 'Transports & Mobilité',  score: e.transport || 0, icon: TruckIcon,       gradient: 'from-blue-500 to-cyan-400'    },
    { id: 'education', label: 'Éducation & Services',   score: e.education || 0, icon: AcademicCapIcon, gradient: 'from-sage-500 to-sage-400'    },
    { id: 'commerce',  label: 'Commerces & Vie locale', score: e.commerce  || 0, icon: ShoppingBagIcon, gradient: 'from-pink-500 to-rose-400'    },
    { id: 'calme',     label: 'Calme & Environnement',  score: e.calme     || 0, icon: HeartIcon,       gradient: 'from-emerald-500 to-teal-400' },
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

// ─── Data fetch ──────────────────────────────────────────────────────────────
watch(
  () => props.parcelId,
  async (id) => {
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
        densification.value = {
          ces_actuel:                    f.ces_actuel ?? 0,
          ces_potentiel:                 f.ces_potentiel ?? 0,
          categorie:                     f.categorie_densification ?? 'INCONNU',
          surface_constructible_restante: f.surface_constructible_restante ?? 0,
        };
      }
    } catch (err) {
      error.value = 'Erreur lors du chargement des données.';
    } finally {
      loading.value = false;
      setTimeout(() => (showScores.value = true), 200);
    }
  },
  { immediate: true }
);
</script>

<template>
  <div
    class="fixed top-14 right-0 bottom-0 z-50 flex"
    :style="{ width: panelWidth + 'px' }"
  >
    <!-- Resize handle (left edge) -->
    <div
      class="w-3 flex-shrink-0 flex items-center justify-center cursor-col-resize
             hover:bg-sage-50 transition-colors group"
      @mousedown="startResize"
    >
      <div
        class="w-0.5 h-10 bg-slate-200 rounded-full
               group-hover:bg-sage-400 transition-colors"
      ></div>
    </div>

    <!-- Panel body -->
    <div
      class="flex-1 min-w-0 flex flex-col bg-white overflow-hidden
             shadow-[-8px_0_40px_rgba(0,0,0,0.08),_-1px_0_0_rgba(226,232,240,0.6)]"
    >
      <!-- ── Header ── -->
      <div class="flex-shrink-0 px-5 pt-4 border-b border-slate-100">
        <div class="flex items-start justify-between gap-3 mb-3">
          <ParcelHeader
            :parcel-id="parcelId"
            :coordinates="parcelCoords"
            @close="$emit('close')"
          />
          <button
            @click="$emit('close')"
            class="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 flex-shrink-0
                   flex items-center justify-center transition-colors mt-0.5"
          >
            <svg class="w-3.5 h-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
            class="flex-shrink-0 px-4 py-2.5 text-xs font-semibold
                   whitespace-nowrap transition-colors border-b-2"
            :class="activeTab === tab.id
              ? 'border-sage-500 text-sage-700'
              : 'border-transparent text-slate-400 hover:text-slate-600 hover:border-slate-200'"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <!-- ── Tab content ── -->
      <div class="flex-1 overflow-y-auto custom-scrollbar">

        <!-- Loading -->
        <div v-if="loading" class="flex flex-col items-center justify-center h-52 gap-3">
          <div class="w-9 h-9 border-[3px] border-slate-100 border-t-sage-500 rounded-full animate-spin"></div>
          <p class="text-sm text-slate-400">Chargement…</p>
        </div>

        <!-- Error -->
        <div v-else-if="error" class="flex items-center justify-center h-52 px-6 text-center">
          <p class="text-sm text-red-500">{{ error }}</p>
        </div>

        <!-- ── Résumé ── -->
        <div v-else-if="activeTab === 'resume'" class="p-5 space-y-4 animate-fade-in">

          <!-- Potentiel brut -->
          <div
            v-if="densification && avgPriceM2 > 0"
            class="rounded-2xl p-4 bg-gradient-to-br from-amber-50 to-yellow-100
                   border border-amber-200/80"
          >
            <p class="text-[10px] font-black uppercase tracking-widest text-amber-700 mb-1">
              Potentiel brut estimé
            </p>
            <p class="text-3xl font-black text-amber-900 tabular-nums">{{ fmt(potentialGain) }}</p>
            <p class="text-[11px] text-amber-700 mt-1.5 font-mono">
              {{ densification.surface_constructible_restante.toFixed(0) }} m²
              × {{ avgPriceM2.toFixed(0) }} €/m²
            </p>
          </div>

          <!-- Confidence -->
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

          <!-- Stats -->
          <ParcelStats
            :transaction-count="transactions.length"
            :avg-price-m2="avgPriceM2"
            :last-sale-date="lastSaleDate"
            :sector-avg-price-m2="sectorAvgPriceM2"
          />

          <!-- Fiche unavailable -->
          <div
            v-if="!fiche && !loading"
            class="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-700"
          >
            ℹ️ Données d'expertise non disponibles pour cette parcelle.
          </div>
        </div>

        <!-- ── Marché ── -->
        <div v-else-if="activeTab === 'marche'" class="p-5 space-y-5 animate-fade-in">
          <ParcelPriceChart
            v-if="sortedTx.length > 0"
            :transactions="sortedTx"
          />
          <div
            v-else
            class="flex items-center justify-center h-32 text-slate-400 text-sm"
          >
            Aucune transaction disponible
          </div>

          <!-- Quality scores -->
          <div v-if="fiche" class="space-y-3">
            <p class="text-[10px] font-bold uppercase tracking-wider text-slate-400">Qualité de vie</p>
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
            class="flex items-center justify-center h-32 text-slate-400 text-sm"
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
            class="flex items-center justify-center h-32 text-slate-400 text-sm"
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
        class="flex-shrink-0 px-5 py-4 bg-white border-t border-slate-100"
      >
        <button
          @click="generateReport"
          :disabled="generatingReport"
          class="w-full flex items-center justify-center gap-2.5 py-3 px-5
                 bg-gradient-to-r from-sage-500 to-sage-600
                 hover:from-sage-600 hover:to-sage-700
                 disabled:from-slate-300 disabled:to-slate-300 disabled:cursor-not-allowed
                 text-white text-sm font-semibold rounded-xl
                 shadow-[0_4px_14px_rgba(82,127,140,0.35)]
                 hover:shadow-[0_6px_20px_rgba(82,127,140,0.45)]
                 hover:-translate-y-0.5 active:translate-y-0
                 disabled:shadow-none disabled:translate-y-0
                 transition-all duration-200"
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
            class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
          ></div>
          <span>{{ generatingReport ? 'Génération…' : 'Rapport Expert PDF' }}</span>
          <span class="ml-auto px-2 py-0.5 bg-white/20 rounded-lg text-xs font-bold">
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
