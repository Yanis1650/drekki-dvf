<script setup>
defineProps({ parcelId: String, coordinates: Array });
</script>
<template>
  <header class="min-w-0">
    <p class="fe-label">Parcelle cadastrale</p>
    <h2 class="text-lead font-semibold font-mono break-all text-ink mt-1">{{ parcelId }}</h2>
    <p class="fe-meta mt-1">Commune INSEE {{ parcelId?.slice(0, 5) }}</p>
    <p v-if="coordinates" class="fe-meta">{{ coordinates[1]?.toFixed(5) }}, {{ coordinates[0]?.toFixed(5) }}</p>
  </header>
</template>
