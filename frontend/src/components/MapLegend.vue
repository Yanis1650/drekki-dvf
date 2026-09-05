<script setup>
import { computed } from 'vue';
import { legendItems } from '../composables/mapColorSchemes';
defineProps({ mode: String });
// CSS variables respond to theme changes without rebuilding the component.
const prices = computed(() => legendItems('prix').map((item, i) => ({ ...item, color: `var(--fe-ramp-${i + 1})` })));
</script>
<template>
  <details class="absolute top-3 left-3 z-10 bg-surface border border-rule rounded p-3 max-w-xs text-meta">
    <summary class="text-accent cursor-pointer">Légende et sources</summary>
    <p class="mt-2 font-semibold">Points : prix DVF par mutation</p>
    <ul><li v-for="item in prices" :key="item.libelle" class="flex items-center gap-2 mt-1"><span class="w-4 h-3 border border-rule" :style="{ background: item.color }"></span>{{ item.libelle }}</li></ul>
    <p class="mt-2">Fond parcellaire : {{ mode === 'zan' ? 'potentiel de densification modélisé' : mode === 'urbanisme' ? 'zones d’urbanisme' : 'prix moyen historique par parcelle' }}.</p>
    <p v-if="mode === 'zan'">Du plus clair au plus foncé : saturé, faible, moyen, fort.</p>
    <p v-if="mode === 'urbanisme'">U : urbanisé · A : agricole · N : naturel · AU : à urbaniser. Les hachures distinguent les zones.</p>
    <p class="fe-absent mt-2">Hachures d’absence : NON RELEVÉ.</p>
    <p class="mt-2">Sources : fond IGN, parcelles enrichies de l’API. Les fonds parcellaires ne suivent pas la période DVF sélectionnée.</p>
  </details>
</template>
