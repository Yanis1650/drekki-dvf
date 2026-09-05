<script setup>
import { computed, inject, ref } from 'vue';
import { DOSSIERS_KEY } from '../composables/useDossiers.js';
import { DECISIONS, OBJECTIVES } from '../domain/dossier.js';
const store = inject(DOSSIERS_KEY);
const filter = ref('');
const records = computed(() => store.dossiers.value.filter(d => !filter.value || d.decision === filter.value));
defineEmits(['parcel-click']);
const progress = dossier => Object.values(dossier.checks).filter(c => c.done && c.note.trim()).length;
</script>
<template>
  <div class="absolute inset-0 overflow-auto bg-ground p-4 md:p-6">
    <div class="max-w-4xl mx-auto space-y-5">
      <header><h1 class="text-title font-semibold">Mes dossiers</h1><p class="text-body text-ink-2 mt-1">Vos fonciers à étudier et vos visites à préparer, dans un même suivi.</p><p class="fe-meta mt-1">Notes locales à ce navigateur. Les données du bien sont rechargées à l’ouverture ; vos observations restent celles que vous avez enregistrées.</p></header>
      <p v-if="store.error.value" role="alert" class="text-alert">{{ store.error.value }}</p>
      <label class="block text-body">Filtrer mon suivi <select v-model="filter" class="p-2 bg-surface border border-rule rounded"><option value="">Tous les dossiers</option><option v-for="(label, key) in DECISIONS" :key="key" :value="key">{{ label }}</option></select></label>
      <section v-if="!records.length" class="cartouche p-6"><h2 class="text-lead font-semibold">{{ store.dossiers.value.length ? 'Aucun dossier pour ce filtre' : 'Votre premier dossier commence sur la carte' }}</h2><p class="text-body mt-2">Ouvrez une parcelle, choisissez votre objectif, puis enregistrez votre dossier.</p><RouterLink to="/" class="text-accent underline inline-block mt-3">Explorer la carte</RouterLink></section>
      <ul v-else class="divide-y divide-rule border-y border-rule">
        <li v-for="dossier in records" :key="dossier.parcelId" class="py-4 flex flex-wrap gap-4 items-center justify-between">
          <div class="min-w-0"><h2 class="text-lead font-semibold break-words">{{ dossier.title || dossier.parcelId }}</h2><p class="fe-meta">{{ dossier.parcelId }} · {{ OBJECTIVES[dossier.objective] }}</p><p class="text-body mt-1">{{ DECISIONS[dossier.decision] }} · {{ progress(dossier) }} / 4 vérifications renseignées</p><p class="fe-meta">Enregistré le {{ new Date(dossier.updatedAt).toLocaleDateString('fr-FR') }}</p></div>
          <button class="btn border border-accent text-accent" :aria-label="`Ouvrir le dossier ${dossier.parcelId}`" @click="$emit('parcel-click', { properties: { id_parcelle: dossier.parcelId } })">Ouvrir le dossier</button>
        </li>
      </ul>
    </div>
  </div>
</template>
