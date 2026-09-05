<script setup>
import { computed, inject, ref, watch } from 'vue';
import { buildDossier, dossierText, OBJECTIVES, DECISIONS } from '../../domain/dossier.js';
import { DOSSIERS_KEY } from '../../composables/useDossiers.js';
const props = defineProps({ parcelId: String, fiche: Object, densification: Object, transactions: Array, historyAvailable: Boolean });
const store = inject(DOSSIERS_KEY, null);
const title = ref(''), objective = ref('potentiel'), decision = ref('qualifier'), notes = ref(''), checks = ref({}), message = ref('');
watch(() => props.parcelId, id => {
  const saved = store?.find(id);
  title.value = saved?.title || ''; objective.value = saved?.objective || 'potentiel';
  decision.value = saved?.decision || 'qualifier'; notes.value = saved?.notes || '';
  checks.value = Object.fromEntries(['regles', 'acces', 'ventes', 'terrain'].map(key => [key, { note: saved?.checks[key]?.note || '', done: saved?.checks[key]?.done || false }]));
  message.value = '';
}, { immediate: true });
const analysis = computed(() => buildDossier({ ...props, objective: objective.value }));
const completed = computed(() => Object.values(checks.value).filter(c => c.done && c.note.trim()).length);
watch(objective, () => { for (const check of Object.values(checks.value)) check.done = false; });
watch([title, objective, decision, notes, checks], () => { message.value = ''; }, { deep: true });
function draft() { return { parcelId: props.parcelId, title: title.value, objective: objective.value, decision: decision.value, notes: notes.value, checks: checks.value }; }
function save() { if (store?.save(draft())) message.value = 'Dossier enregistré dans ce navigateur.'; }
function download() {
  const content = dossierText({ ...draft(), analysis: analysis.value, savedAt: new Date().toLocaleString('fr-FR') });
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `dossier-${props.parcelId}.txt`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
</script>
<template>
  <section aria-label="Dossier foncier" class="space-y-5">
    <header><h2 class="text-lead font-semibold">Comprendre, vérifier, décider</h2><p class="fe-meta mt-1">Un dossier pour étudier un foncier ou préparer une visite. Les conclusions restent à vérifier.</p></header>
    <label class="block text-body">Mon objectif
      <select v-model="objective" class="block w-full mt-1 p-2 bg-surface border border-rule rounded"><option v-for="(label, key) in OBJECTIVES" :key="key" :value="key">{{ label }}</option></select>
    </label>
    <section class="space-y-3"><h3 class="text-body font-semibold">1. Comprendre les données disponibles</h3>
      <p class="text-body">{{ analysis.summary }}</p>
      <dl v-if="analysis.facts.length" class="divide-y divide-rule border-y border-rule">
        <div v-for="fact in analysis.facts" :key="fact.label" class="py-2"><dt class="fe-label">{{ fact.label }}</dt><dd class="text-body" :class="fact.kind === 'Modélisé' || fact.kind.startsWith('Calcul') ? 'fe-estimated' : ''">{{ fact.value }}</dd><dd class="fe-meta">{{ fact.kind }} · {{ fact.source }}</dd></div>
      </dl>
      <details><summary class="text-accent text-body cursor-pointer">Ce qui reste inconnu ({{ analysis.unknowns.length }})</summary><ul class="list-disc pl-5 text-meta text-ink-2 mt-2 space-y-2"><li v-for="unknown in analysis.unknowns" :key="unknown">{{ unknown }}</li></ul></details>
    </section>
    <section class="space-y-3"><h3 class="text-body font-semibold">2. Préparer les vérifications utiles</h3>
      <p class="fe-meta">{{ completed }} / {{ analysis.checks.length }} renseignées par vous. Cocher un point ne certifie pas les données ni la faisabilité.</p>
      <article v-for="check in analysis.checks" :key="check.id" class="cartouche p-3 space-y-2">
        <h4 class="text-body font-semibold">{{ check.title }}</h4><p class="text-meta text-ink-2">{{ check.why }}</p><p class="text-body">{{ check.action }}</p>
        <details><summary class="text-meta text-accent cursor-pointer">Pourquoi cette question ?</summary><p class="fe-meta">Règle de lecture Foncier Express · {{ check.source }}. Proposition automatique à adapter à votre projet.</p></details>
        <label class="block text-meta">Observation ou référence — {{ check.title }}<textarea v-model="checks[check.id].note" rows="2" class="block mt-1 w-full p-2 border border-rule rounded bg-surface" @input="checks[check.id].done = false"></textarea></label>
        <label class="flex items-center gap-2 text-meta"><input v-model="checks[check.id].done" type="checkbox" :disabled="!checks[check.id].note.trim()"> Point renseigné par moi</label>
      </article>
    </section>
    <section class="space-y-3"><h3 class="text-body font-semibold">3. Noter ma prochaine décision</h3>
      <label class="block text-meta">Nom du dossier<input v-model="title" class="block w-full mt-1 p-2 bg-surface border border-rule rounded" placeholder="Ex. Terrain à visiter"></label>
      <label class="block text-meta">Mon suivi<select v-model="decision" class="block w-full mt-1 p-2 bg-surface border border-rule rounded"><option v-for="(label, key) in DECISIONS" :key="key" :value="key">{{ label }}</option></select></label>
      <label class="block text-meta">Notes et prochaine action<textarea v-model="notes" rows="3" class="block w-full mt-1 p-2 bg-surface border border-rule rounded"></textarea></label>
      <p class="fe-meta">Votre décision personnelle est indépendante du potentiel calculé.</p>
    </section>
    <div class="flex flex-wrap gap-2"><button class="btn btn--primary" :disabled="!store" @click="save">Enregistrer mon dossier</button><button class="btn border border-rule text-accent" @click="download">Exporter mes notes (.txt)</button></div>
    <p class="fe-meta">Pensez à enregistrer avant de fermer. Notes conservées uniquement dans ce navigateur après enregistrement, sans compte ni synchronisation. Exportez-les pour les sauvegarder ou les transmettre. Le rapport PDF technique ne contient pas ces notes.</p>
    <p v-if="message" role="status" class="text-body">{{ message }}</p>
    <p v-if="store?.error.value" role="alert" class="text-body text-alert">{{ store.error.value }}</p>
  </section>
</template>
