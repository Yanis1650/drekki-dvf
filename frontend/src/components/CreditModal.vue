<script setup>
import { ref } from 'vue';
import { XMarkIcon, SparklesIcon, CheckIcon, CreditCardIcon } from '@heroicons/vue/24/solid';
import client from '../api/client';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close', 'success']);

const loading = ref(false);
const selectedPack = ref(null);

const creditPacks = [
  { id: 'starter', name: 'Starter', credits: 5, price: 9.99, popular: false },
  { id: 'pro', name: 'Pro', credits: 20, price: 29.99, popular: true },
  { id: 'enterprise', name: 'Enterprise', credits: 50, price: 59.99, popular: false }
];

const selectPack = (pack) => {
  selectedPack.value = pack.id;
};

const purchaseCredits = async () => {
  if (!selectedPack.value) return;
  
  const pack = creditPacks.find(p => p.id === selectedPack.value);
  if (!pack) return;
  
  loading.value = true;
  try {
    // Mock purchase - in production this would redirect to Stripe
    await client.post('/users/credits/add', { credits: pack.credits });
    emit('success');
    emit('close');
  } catch (err) {
    console.error("Purchase error:", err);
    alert("Erreur lors de l'achat. Veuillez réessayer.");
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div 
        v-if="isOpen" 
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
        
        <!-- Modal -->
        <Transition
          enter-active-class="transition-all duration-300 ease-out delay-75"
          enter-from-class="opacity-0 scale-95 translate-y-4"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div 
            v-if="isOpen" 
            class="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden"
          >
            <!-- Header -->
            <div class="relative px-6 pt-6 pb-4">
              <button 
                @click="emit('close')"
                class="absolute top-4 right-4 w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 
                       flex items-center justify-center transition-colors"
              >
                <XMarkIcon class="h-4 w-4 text-slate-500" />
              </button>
              
              <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-xl gradient-primary-accent flex items-center justify-center">
                  <SparklesIcon class="h-6 w-6 text-white" />
                </div>
                <div>
                  <h2 class="text-xl font-bold text-slate-900">Recharger mes crédits</h2>
                  <p class="text-sm text-slate-500">Choisissez votre pack</p>
                </div>
              </div>
            </div>
            
            <!-- Credit Packs -->
            <div class="px-6 pb-4 space-y-3">
              <div 
                v-for="pack in creditPacks" 
                :key="pack.id"
                @click="selectPack(pack)"
                class="relative p-4 rounded-xl border-2 cursor-pointer transition-all duration-200"
                :class="selectedPack === pack.id 
                  ? 'border-indigo-500 bg-indigo-50 shadow-md' 
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'"
              >
                <!-- Popular Badge -->
                <div 
                  v-if="pack.popular" 
                  class="absolute -top-2.5 left-4 px-2.5 py-0.5 bg-gradient-to-r from-pink-500 to-rose-500 
                         text-white text-xs font-bold rounded-full shadow-sm"
                >
                  Populaire
                </div>
                
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-4">
                    <!-- Selection indicator -->
                    <div 
                      class="w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all"
                      :class="selectedPack === pack.id 
                        ? 'border-indigo-500 bg-indigo-500' 
                        : 'border-slate-300'"
                    >
                      <CheckIcon v-if="selectedPack === pack.id" class="h-3.5 w-3.5 text-white" />
                    </div>
                    
                    <div>
                      <h3 class="font-bold text-slate-900">{{ pack.name }}</h3>
                      <p class="text-sm text-slate-500">{{ pack.credits }} crédits</p>
                    </div>
                  </div>
                  
                  <div class="text-right">
                    <span class="text-2xl font-bold text-slate-900">{{ pack.price.toFixed(2) }}€</span>
                    <p class="text-xs text-slate-400">{{ (pack.price / pack.credits).toFixed(2) }}€/crédit</p>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Footer -->
            <div class="px-6 py-4 bg-slate-50 border-t border-slate-100">
              <button 
                @click="purchaseCredits"
                :disabled="!selectedPack || loading"
                class="btn-premium w-full"
              >
                <CreditCardIcon v-if="!loading" class="h-5 w-5" />
                <svg v-else class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>{{ loading ? 'Traitement...' : 'Procéder au paiement' }}</span>
              </button>
              
              <p class="text-center text-xs text-slate-400 mt-3">
                🔒 Paiement sécurisé par Stripe
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
