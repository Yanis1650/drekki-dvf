<script setup>
/**
 * Bandeau de disponibilité et de qualité.
 *
 * Il ne répète plus le compte des mutations ni la période — le pied de carte et
 * le rail les portent déjà. Il ne reste que ce qu'aucun autre bloc ne dit :
 * l'étude charge, l'étude a échoué, l'échantillon est plafonné, et les réserves
 * qui accompagnent les agrégats.
 */
defineProps({
  status: String,
  error: String,
  capped: Boolean,
  stats: Object,
  enrichmentAvailable: { default: null },
});
defineEmits(['retry']);
</script>

<template>
  <section
    v-if="status !== 'idle'"
    class="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 bg-ground border-b border-rule text-meta"
    aria-label="Disponibilité et qualité DVF"
    aria-live="polite"
  >
    <p v-if="status === 'loading'" role="status" class="text-ink-2">
      Chargement des mutations DVF du périmètre…
    </p>

    <p v-else-if="status === 'error'" role="alert" class="flex items-center gap-2">
      <span class="absent">NON RELEVÉ</span>
      <span class="text-ink-2">{{ error }}</span>
      <button type="button" class="btn btn--quiet" @click="$emit('retry')">Réessayer</button>
    </p>

    <template v-else-if="status === 'ready' || status === 'empty'">
      <p v-if="capped" class="text-warn">
        Limite de 1 000 résultats atteinte : échantillon potentiellement incomplet. Réduisez le
        rayon ou la période.
      </p>
      <p v-if="stats.priced < 5" class="text-warn">
        Échantillon de prix faible (moins de 5 mutations).
      </p>
      <details class="relative ml-auto text-ink-2">
        <summary class="cursor-pointer text-accent">Qualité et limites des données</summary>
        <div class="absolute right-0 z-40 mt-1 w-[min(32rem,80vw)] p-3 bg-surface border border-rule-strong rounded shadow-overlay space-y-1">
          <p>
            {{ stats.priced }} prix/m² exploitables · {{ stats.outliers }} valeurs signalées
            aberrantes, exclues des prix agrégés · {{ stats.unmapped }} mutations sans position
            cartographiable.
          </p>
          <p>
            Millésime de publication, date de mise à jour et rapport qualité d’ingestion : non
            fournis par cette API. L’absence de signalement ne certifie pas la qualité.
          </p>
          <p>
            Enrichissement de proximité :
            {{ enrichmentAvailable === true ? 'disponible' : 'NON RELEVÉ' }}. Ces scores ne
            mesurent pas la densification.
          </p>
        </div>
      </details>
    </template>
  </section>
</template>
