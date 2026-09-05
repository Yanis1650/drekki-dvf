<script setup>
import AddressSearch from '../AddressSearch.vue';
defineProps({ mapMode: String, loading: Boolean });
defineEmits(['search-select', 'update:mapMode']);
</script>
<template>
  <header class="flex flex-wrap items-center gap-3 p-3 bg-surface border-b border-rule z-40">
    <span class="font-semibold text-body text-ink">Foncier<span class="text-accent">Express</span></span>
    <div class="order-3 w-full sm:order-none sm:flex-1 sm:w-auto min-w-0"><AddressSearch @select="$emit('search-select', $event)" /></div>
    <label class="text-meta text-ink-2">Fond parcellaire
      <select :value="mapMode" @change="$emit('update:mapMode', $event.target.value)" class="border border-rule bg-surface-2 rounded p-2">
        <option value="prix">Prix</option><option value="zan">Densification</option><option value="urbanisme">Urbanisme</option>
      </select>
    </label>
    <span v-if="loading" class="text-meta text-ink-3" role="status">Chargement…</span>
  </header>
</template>
