<script setup>
import { computed } from 'vue';
import { summarize, money } from '../../domain/market.js';
const props = defineProps({ transactions: Object });
const stats = computed(() => summarize(props.transactions));
</script>
<template>
  <div class="grid grid-cols-3 gap-3 px-4 py-4 bg-surface border-t border-rule text-body" aria-label="Indicateurs du périmètre DVF">
    <div><p class="fe-label">Mutations</p><strong class="block text-title font-mono mt-2">{{ stats.count }}</strong><p class="fe-meta mt-1">DVF · échantillon chargé</p></div>
    <div class="border-l border-rule pl-3"><p class="fe-label">Moyenne / m²</p><strong class="block text-title font-mono fe-estimated mt-2">{{ money(stats.avgPrice) }}</strong><p class="fe-meta mt-1">n = {{ stats.priced }} · hors aberrantes</p></div>
    <div class="border-l border-rule pl-3"><p class="fe-label">Médiane / m²</p><strong class="block text-title font-mono fe-estimated mt-2">{{ money(stats.median) }}</strong><p class="fe-meta mt-1">Quartiles : {{ money(stats.q1) }}–{{ money(stats.q3) }}</p><p v-if="stats.priced < 5" class="text-warn text-meta">Échantillon faible</p></div>
  </div>
</template>
