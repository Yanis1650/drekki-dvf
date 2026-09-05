<script setup>
defineProps({ status: String, error: String, capped: Boolean, stats: Object, enrichmentAvailable: { default: null } });
defineEmits(['retry']);
</script>
<template>
  <section class="bg-surface border-b border-rule px-4 py-2 text-meta" aria-label="Disponibilité et qualité DVF" aria-live="polite">
    <p v-if="status === 'loading'" role="status">Chargement des mutations DVF du périmètre…</p>
    <p v-else-if="status === 'error'" role="alert" class="fe-absent">
      {{ error }} <button class="text-accent underline ml-2" @click="$emit('retry')">Réessayer</button>
    </p>
    <template v-else-if="status === 'ready' || status === 'empty'">
      <p><strong>{{ stats.count }} mutations</strong> · Source : DVF via l’API Foncier Express ·
        {{ stats.firstDate || 'Aucune vente trouvée' }}<template v-if="stats.lastDate"> → {{ stats.lastDate }}</template>
      </p>
      <p v-if="capped" class="text-warn">Limite de 1 000 résultats atteinte : échantillon potentiellement incomplet. Réduisez le rayon ou la période.</p>
      <details class="mt-1 text-ink-2">
        <summary class="cursor-pointer text-accent">Qualité et limites des données</summary>
        <p>{{ stats.priced }} prix/m² exploitables · {{ stats.outliers }} valeurs signalées aberrantes, exclues des prix agrégés · {{ stats.unmapped }} mutations sans position cartographiable.</p>
        <p v-if="stats.priced < 5" class="text-warn">Échantillon de prix faible (moins de 5 mutations).</p>
        <p>Millésime de publication, date de mise à jour et rapport qualité d’ingestion : non fournis par cette API. L’absence de signalement ne certifie pas la qualité.</p>
        <p>Enrichissement de proximité : {{ enrichmentAvailable === true ? 'disponible' : 'NON RELEVÉ' }}. Ces scores ne mesurent pas la densification.</p>
      </details>
    </template>
  </section>
</template>
