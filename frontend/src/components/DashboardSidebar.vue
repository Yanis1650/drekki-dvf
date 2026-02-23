<script setup>
import { computed } from 'vue';
import { CloudArrowDownIcon, CurrencyEuroIcon, HomeIcon, MagnifyingGlassIcon, SparklesIcon } from '@heroicons/vue/24/solid';
import AddressSearch from './AddressSearch.vue';
import AnalysisPanel from './AnalysisPanel.vue';

const props = defineProps({
  balance: {
    type: Number,
    required: true
  },
  selectedTransaction: {
    type: Object,
    default: null
  },
  enrichment: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  },
  avgPrice: {
    type: [Number, String],
    default: 4000
  }
});

const emit = defineEmits(['search-select', 'download-report', 'buy-credits', 'clear-selection']);

// Format balance with animation trigger
const displayBalance = computed(() => props.balance);
</script>

<template>
  <div class="h-full flex flex-col glass-sidebar z-20 w-[420px]">
    
    <!-- Header: Brand -->
    <div class="p-6 pb-4">
      <div class="flex items-center gap-3 mb-1">
        <!-- Animated Logo Icon -->
        <div class="relative">
          <div class="w-11 h-11 rounded-xl gradient-primary flex items-center justify-center shadow-lg">
            <HomeIcon class="h-6 w-6 text-white" />
          </div>
          <div class="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-br from-pink-400 to-pink-600 rounded-full flex items-center justify-center animate-pulse-slow">
            <SparklesIcon class="h-2.5 w-2.5 text-white" />
          </div>
        </div>
        
        <!-- Brand Text -->
        <div>
          <h1 class="text-2xl font-bold tracking-tight">
            <span class="text-slate-800">Foncier</span><span class="gradient-text-primary">Express</span>
          </h1>
          <p class="text-xs text-slate-400 font-medium">Analyse foncière premium</p>
        </div>
      </div>
    </div>

    <!-- Credit Balance Ticket -->
    <div class="px-6 pb-5">
      <div class="credit-ticket p-4 flex justify-between items-center">
        <div class="relative z-10">
          <p class="text-xs font-bold uppercase tracking-wider text-sage-600/80 mb-0.5">Mon Solde</p>
          <div class="flex items-baseline gap-1.5">
            <span class="text-3xl font-bold text-slate-900 tabular-nums animate-counter" :key="balance">
              {{ displayBalance }}
            </span>
            <span class="text-sm font-medium text-slate-500">crédits</span>
          </div>
        </div>
        <button 
          @click="emit('buy-credits')"
          class="relative z-10 w-11 h-11 bg-white rounded-xl shadow-md flex items-center justify-center border border-sage-100 
                 hover:shadow-lg hover:scale-105 active:scale-95 transition-all duration-200"
          title="Recharger mes crédits"
        >
          <CurrencyEuroIcon class="h-5 w-5 text-sage-600" />
        </button>
      </div>
    </div>

    <!-- Divider -->
    <div class="h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent mx-6"></div>

    <!-- Search Section -->
    <div class="p-6">
      <AddressSearch @select="(val) => emit('search-select', val)" />
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6">
      
      <!-- Loading State -->
      <div v-if="loading" class="flex flex-col items-center justify-center h-56 space-y-4">
        <div class="relative">
          <div class="w-14 h-14 rounded-full border-4 border-slate-100"></div>
          <div class="absolute inset-0 w-14 h-14 rounded-full border-4 border-sage-500 border-t-transparent animate-spin"></div>
        </div>
        <div class="text-center">
          <p class="text-slate-600 font-medium">Analyse en cours</p>
          <p class="text-slate-400 text-sm">Récupération des données du marché...</p>
        </div>
      </div>

      <!-- Analysis View -->
      <div v-else-if="selectedTransaction" class="animate-fade-in-up pb-6">
        <!-- Transaction Header -->
        <div class="flex justify-between items-start mb-5">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Mutation sélectionnée</span>
            </div>
            <h2 class="text-xl font-bold text-slate-900">
              #{{ selectedTransaction.id_mutation?.split('-')[1] || 'REF' }}
            </h2>
            <p class="text-sm text-slate-500 mt-0.5">
              {{ new Date(selectedTransaction.date_mutation).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) }}
            </p>
          </div>
          <button 
            @click="emit('clear-selection')" 
            class="w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"
          >
            <span class="text-slate-400 text-lg leading-none">&times;</span>
          </button>
        </div>

        <!-- Analysis Content -->
        <AnalysisPanel 
          :transaction="selectedTransaction"
          :enrichment="enrichment"
          :avg-price="avgPrice"
        />

        <!-- Action Button -->
        <div class="mt-8 pt-6 border-t border-slate-100">
          <button 
            @click="emit('download-report')"
            :disabled="balance < 1"
            class="btn-premium w-full"
            :class="{ 'opacity-50 cursor-not-allowed': balance < 1 }"
          >
            <CloudArrowDownIcon class="h-5 w-5" />
            <span v-if="balance > 0">Rapport Complet (1 crédit)</span>
            <span v-else>Crédit insuffisant</span>
          </button>
          
          <p v-if="balance < 1" 
             class="text-center text-xs text-rose-500 mt-3 cursor-pointer hover:underline font-medium" 
             @click="emit('buy-credits')">
            → Recharger mes crédits
          </p>
        </div>
      </div>

      <!-- Empty State -->
      <div v-else class="flex flex-col items-center justify-center h-64 text-center">
        <div class="w-20 h-20 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
          <MagnifyingGlassIcon class="h-10 w-10 text-slate-300" />
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">Prêt à analyser</h3>
        <p class="text-slate-400 text-sm max-w-[240px] leading-relaxed">
          Recherchez une adresse ou sélectionnez une transaction sur la carte pour commencer.
        </p>
      </div>

    </div>
  </div>
</template>
