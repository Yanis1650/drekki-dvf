<script setup>
import AddressSearch from '../AddressSearch.vue';
defineProps({ mapMode: String, loading: Boolean });
defineEmits(['search-select', 'update:mapMode']);
</script>
<template>
  <header class="flex flex-wrap items-center gap-4 px-4 py-3 bg-surface border-b border-rule z-40">
    <RouterLink to="/" aria-label="Foncier Express, accueil" class="shrink-0 lg:w-40"><span class="font-semibold text-lead text-ink">Foncier<span class="text-accent">Express</span></span><span class="hidden sm:block fe-label mt-1">Le foncier, en perspective</span></RouterLink>
    <div class="order-3 w-full sm:order-none sm:flex-1 sm:w-auto min-w-0 max-w-2xl"><AddressSearch @select="$emit('search-select', $event)" /></div>
    <label class="text-meta text-ink-2 ml-auto"><span class="sr-only sm:not-sr-only">Lecture de la carte</span>
      <select :value="mapMode" @change="$emit('update:mapMode', $event.target.value)" class="border border-rule bg-surface-2 rounded p-2">
        <option value="prix">Prix</option><option value="zan">Densification</option><option value="urbanisme">Urbanisme</option>
      </select>
    </label>
    <span v-if="loading" class="text-meta text-ink-3" role="status">Chargement…</span>
  </header>
</template>
