<script setup>
import { computed } from 'vue';
import { summarize, money } from '../../domain/market.js';
const props = defineProps({ transactions: Object });
const stats = computed(() => summarize(props.transactions));
</script>
<template>
  <div class="flex flex-wrap gap-5 px-5 py-3 bg-surface border-t border-rule text-body" aria-label="Indicateurs du périmètre DVF">
    <div><p class="fe-label">Mutations chargées</p><strong>{{ stats.count }}</strong></div>
    <div><p class="fe-label">Prix moyen / m²</p><strong class="fe-estimated">{{ money(stats.avgPrice) }}</strong><p class="fe-meta">n = {{ stats.priced }} · hors aberrantes</p></div>
    <div><p class="fe-label">Prix médian / m²</p><strong class="fe-estimated">{{ money(stats.median) }}</strong><p class="fe-meta">50 % des prix : {{ money(stats.q1) }} à {{ money(stats.q3) }}</p></div>
    <div><p class="fe-label">Source</p><span>DVF · mutations chargées</span><p v-if="stats.priced < 5" class="text-warn text-meta">Échantillon faible</p></div>
  </div>
</template>
