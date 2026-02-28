<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { 
  BuildingOfficeIcon, 
  BoltIcon, 
  HeartIcon,
  TruckIcon,
  AcademicCapIcon,
  ShoppingBagIcon,
  SpeakerXMarkIcon,
  ChartBarIcon
} from '@heroicons/vue/24/solid';
import client from '../api/client';
import ScoreBar from './ScoreBar.vue';
import PriceIndicator from './PriceIndicator.vue';
import AttributesGrid from './AttributesGrid.vue';
import MarketTrendsChart from './MarketTrendsChart.vue';
import PotentialGainIndicator from './PotentialGainIndicator.vue';
import FiliationTree from './FiliationTree.vue';
import ParcelHistory from './ParcelHistory.vue';

const props = defineProps({
  transaction: {
    type: Object,
    required: true
  },
  enrichment: {
    type: Object,
    default: () => ({})
  },
  avgPrice: {
    type: [Number, String],
    default: 4000
  }
});

const dpeScore = computed(() => {
  if (props.enrichment?.dpe) {
    return props.enrichment.dpe;
  }
  // Simulated based on price
  const val = props.transaction.valeur_fonciere || 0;
  if (val > 500000) return 'B';
  if (val > 300000) return 'C';
  if (val > 200000) return 'D';
  return 'E';
});

const anneeConstruction = computed(() => {
  return props.enrichment?.annee_construction || null;
});

const dpeColors = {
  'A': 'bg-emerald-500',
  'B': 'bg-green-500', 
  'C': 'bg-lime-500',
  'D': 'bg-yellow-500',
  'E': 'bg-orange-500',
  'F': 'bg-orange-600',
  'G': 'bg-red-600'
};

const dpeColor = computed(() => dpeColors[dpeScore.value] || 'bg-slate-400');

// Score bars config with icons
const qualityScores = computed(() => [
  {
    id: 'transport',
    label: 'Transports & Mobilité',
    score: props.enrichment?.transport || 7.2,
    icon: TruckIcon,
    gradient: 'from-blue-500 to-cyan-400'
  },
  {
    id: 'education',
    label: 'Éducation & Services',
    score: props.enrichment?.education || 8.1,
    icon: AcademicCapIcon,
    gradient: 'from-sage-500 to-sage-400'
  },
  {
    id: 'commerce',
    label: 'Commerces & Vie locale',
    score: props.enrichment?.commerce || 6.8,
    icon: ShoppingBagIcon,
    gradient: 'from-pink-500 to-rose-400'
  },
  {
    id: 'calme',
    label: 'Calme & Environnement',
    score: props.enrichment?.calme || 7.5,
    icon: HeartIcon,
    gradient: 'from-emerald-500 to-teal-400'
  }
]);

// Animation trigger
const showBars = ref(false);

// Market trends data
const marketData = ref(null);
const loadingTrends = ref(false);

// Fetch market trends
const fetchMarketTrends = async () => {
  if (!props.transaction?.latitude || !props.transaction?.longitude) {
    return;
  }

  loadingTrends.value = true;
  try {
    const response = await client.get('/analytics/trends', {
      params: {
        lat: props.transaction.latitude,
        lon: props.transaction.longitude,
        radius: 5000, // 5km radius
        years: 10
      }
    });
    marketData.value = response.data;
  } catch (error) {
    console.error('Failed to fetch market trends:', error);
    marketData.value = null;
  } finally {
    loadingTrends.value = false;
  }
};

onMounted(() => {
  setTimeout(() => showBars.value = true, 100);
  fetchMarketTrends();
});

// Refetch when transaction changes
watch(() => props.transaction?.id_mutation, () => {
  fetchMarketTrends();
});
</script>

<template>
  <div class="space-y-6">
    
    <!-- Value Analysis Card -->
    <div class="card-elevated p-5">
      <div class="flex items-center gap-2 mb-4">
        <div class="w-8 h-8 rounded-lg bg-sage-100 flex items-center justify-center">
          <BuildingOfficeIcon class="h-4 w-4 text-sage-600" />
        </div>
        <h3 class="font-bold text-slate-800">Analyse de Valeur</h3>
      </div>
      
      <PriceIndicator 
        :value="transaction.prix_m2" 
        :avg="avgPrice" 
      />
    </div>

    <!-- Performance & DPE Card -->
    <div class="card-elevated p-5">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
            <BoltIcon class="h-4 w-4 text-amber-600" />
          </div>
          <h3 class="font-bold text-slate-800">Performance & Atouts</h3>
        </div>
        
        <!-- DPE Badge -->
        <div class="dpe-badge shadow-sm">
          <span class="dpe-badge-label">DPE</span>
          <span class="dpe-badge-value" :class="dpeColor">{{ dpeScore }}</span>
        </div>
      </div>
      
      <!-- Année construction if available -->
      <div v-if="anneeConstruction" class="mb-4 p-3 bg-slate-50 rounded-lg">
        <span class="text-xs text-slate-500 uppercase tracking-wider font-semibold">Année de construction</span>
        <p class="text-lg font-bold text-slate-800 mt-0.5">{{ anneeConstruction }}</p>
      </div>
      
      <!-- Attributes -->
      <AttributesGrid :features="enrichment?.features || {}" />
    </div>

    <!-- Quality of Life Card -->
    <div class="card-elevated p-5">
      <div class="flex items-center gap-2 mb-5">
        <div class="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
          <HeartIcon class="h-4 w-4 text-emerald-600" />
        </div>
        <h3 class="font-bold text-slate-800">Qualité de Vie</h3>
      </div>
      
      <div class="space-y-4">
        <template v-for="item in qualityScores" :key="item.id">
          <ScoreBar 
            :label="item.label"
            :score="item.score"
            :icon="item.icon"
            :gradient="item.gradient"
            :animate="showBars"
          />
        </template>
      </div>
    </div>

    <!-- Market Evolution Card -->
    <div class="card-elevated p-5">
      <div class="flex items-center gap-2 mb-5">
        <div class="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
          <ChartBarIcon class="h-4 w-4 text-purple-600" />
        </div>
        <h3 class="font-bold text-slate-800">Évolution du Marché</h3>
      </div>

      <!-- Potential Gain Indicator -->
      <PotentialGainIndicator 
        v-if="marketData" 
        :gain="marketData.potential_gain_pct" 
      />

      <!-- Trends Chart -->
      <MarketTrendsChart 
        :trends="marketData?.trends || []" 
        :loading="loadingTrends" 
      />

      <!-- Confidence Score -->
      <div v-if="marketData" class="mt-4 p-3 bg-slate-50 rounded-lg">
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-500 uppercase tracking-wider font-semibold">
            Fiabilité de l'analyse
          </span>
          <span class="text-sm font-bold text-slate-800">
            {{ marketData.confidence_score }}/10
          </span>
        </div>
      </div>
    </div>

    <!-- Parcel Mutation History Card -->
    <ParcelHistory 
      v-if="transaction?.id_parcelle" 
      :id-parcelle="transaction.id_parcelle" 
    />

    <!-- Filiation History Card -->
    <FiliationTree 
      v-if="transaction?.id_parcelle" 
      :id-parcelle="transaction.id_parcelle" 
    />

  </div>
</template>
