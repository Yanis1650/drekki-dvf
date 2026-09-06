<script setup>
import { computed, inject, ref, watch } from 'vue';
import { buildDossier, dossierText, OBJECTIVES, DECISIONS } from '../../domain/dossier.js';
import { DOSSIERS_KEY } from '../../composables/useDossiers.js';
import { cleanCriteria } from '../../domain/multicriteria.js';
import MulticriteriaAnalysis from './MulticriteriaAnalysis.vue';
const props = defineProps({ parcelId: String, fiche: Object, densification: Object, transactions: Array, historyAvailable: Boolean });
const store = inject(DOSSIERS_KEY, null);
const title = ref(''), objective = ref('potentiel'), decision = ref('qualifier'), notes = ref(''), checks = ref({}), message = ref('');
const criteria = ref({}), savedDraft = ref('');
watch(() => props.parcelId, id => {
  const saved = store?.find(id);
  title.value = saved?.title || ''; objective.value = saved?.objective || 'potentiel';
  decision.value = saved?.decision || 'qualifier'; notes.value = saved?.notes || '';
  checks.value = Object.fromEntries(['regles', 'acces', 'ventes', 'terrain'].map(key => [key, { note: saved?.checks[key]?.note || '', done: saved?.checks[key]?.done || false }]));
  criteria.value = cleanCriteria(saved?.criteria, objective.value);
  savedDraft.value = JSON.stringify(draft());
  message.value = '';
}, { immediate: true });
const analysis = computed(() => buildDossier({ ...props, objective: objective.value }));
const completed = computed(() => Object.values(checks.value).filter(c => c.done && c.note.trim()).length);
watch(objective, () => {
  for (const check of Object.values(checks.value)) check.done = false;
  const defaults = cleanCriteria(null, objective.value);
  criteria.value = Object.fromEntries(Object.entries(defaults).map(([id, value]) => [id, { ...value, note: criteria.value[id]?.note || '' }]));
});
watch([title, objective, decision, notes, checks, criteria], () => { message.value = ''; }, { deep: true });
const dirty = computed(() => JSON.stringify(draft()) !== savedDraft.value);
function draft() { return { parcelId: props.parcelId, title: title.value, objective: objective.value, decision: decision.value, notes: notes.value, checks: checks.value, criteria: criteria.value }; }
function save() { if (store?.save(draft())) { savedDraft.value = JSON.stringify(draft()); message.value = 'Dossier enregistré dans ce navigateur.'; } }
function download() {
  const content = dossierText({ ...draft(), analysis: analysis.value, savedAt: new Date().toLocaleString('fr-FR') });
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = `dossier-${props.parcelId}.txt`;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
</script>
<template>
  <section aria-label="Dossier foncier" class="space-y-4">
    <label class="flex items-center gap-3 text-body">Mon objectif
      <select v-model="objective" class="flex-1 min-w-0 p-2 bg-surface border border-rule rounded"><option v-for="(label, key) in OBJECTIVES" :key="key" :value="key">{{ label }}</option></select>
    </label>
    <details class="text-meta"><summary class="text-accent cursor-pointer">Comment adapter mon analyse ?</summary><p class="fe-meta mt-1">Changer d’objectif adapte les priorités et remet vos appréciations à vérifier. Vos observations sont conservées.</p></details>
    <MulticriteriaAnalysis v-model="criteria" :objective="objective" :facts="analysis.facts" />
    <details class="space-y-3"><summary class="text-body font-semibold text-accent cursor-pointer">Les repères de la parcelle · {{ analysis.facts.length }} disponibles</summary>
      <p class="text-body">{{ analysis.summary }}</p>
      <dl v-if="analysis.facts.length" class="divide-y divide-rule border-y border-rule">
        <div v-for="fact in analysis.facts" :key="fact.label" class="py-2"><dt class="fe-label">{{ fact.label }}</dt><dd class="text-body" :class="fact.kind === 'Modélisé' || fact.kind.startsWith('Calcul') ? 'fe-estimated' : ''">{{ fact.value }}</dd><dd class="fe-meta">{{ fact.kind }} · {{ fact.source }}</dd></div>
      </dl>
      <details><summary class="text-accent text-body cursor-pointer">Ce qui reste inconnu ({{ analysis.unknowns.length }})</summary><ul class="list-disc pl-5 text-meta text-ink-2 mt-2 space-y-2"><li v-for="unknown in analysis.unknowns" :key="unknown">{{ unknown }}</li></ul></details>
    </details>
    <section class="space-y-3"><h3 class="text-lead font-semibold">Mes prochaines vérifications</h3>
      <p class="fe-meta">{{ completed }} / {{ analysis.checks.length }} renseignées par vous. Cocher un point ne certifie pas les données ni la faisabilité.</p>
      <details v-for="check in analysis.checks" :key="check.id" class="cartouche p-3">
        <summary class="text-body font-semibold cursor-pointer text-accent">{{ check.title }} <span class="text-meta font-normal text-ink-2">· {{ checks[check.id].done ? 'Renseigné' : 'À vérifier' }}</span></summary>
        <div class="space-y-2 mt-3">
        <p class="text-meta text-ink-2">{{ check.why }}</p><p class="text-body">{{ check.action }}</p>
        <details><summary class="text-meta text-accent cursor-pointer">Pourquoi cette question ?</summary><p class="fe-meta">Règle de lecture Foncier Express · {{ check.source }}. Proposition automatique à adapter à votre projet.</p></details>
        <label class="block text-meta">Observation ou référence — {{ check.title }}<textarea v-model="checks[check.id].note" rows="2" class="block mt-1 w-full p-2 border border-rule rounded bg-surface" @input="checks[check.id].done = false"></textarea></label>
        <label class="flex items-center gap-2 text-meta"><input v-model="checks[check.id].done" type="checkbox" :disabled="!checks[check.id].note.trim()"> Point renseigné par moi</label>
        </div>
      </details>
    </section>
    <section class="space-y-3"><h3 class="text-lead font-semibold">Ma décision</h3>
      <label class="block text-meta">Nom du dossier<input v-model="title" class="block w-full mt-1 p-2 bg-surface border border-rule rounded" placeholder="Ex. Terrain à visiter"></label>
      <label class="block text-meta">Mon suivi<select v-model="decision" class="block w-full mt-1 p-2 bg-surface border border-rule rounded"><option v-for="(label, key) in DECISIONS" :key="key" :value="key">{{ label }}</option></select></label>
      <label class="block text-meta">Notes et prochaine action<textarea v-model="notes" rows="3" class="block w-full mt-1 p-2 bg-surface border border-rule rounded"></textarea></label>
      <p class="fe-meta">Votre décision personnelle est indépendante du potentiel calculé.</p>
    </section>
    <div class="sticky bottom-0 bg-surface border-t border-rule py-3 space-y-2"><p v-if="dirty" role="status" class="text-meta text-warn">Modifications non enregistrées</p><div class="flex flex-wrap gap-2"><button class="btn btn--primary" :disabled="!store" @click="save">Enregistrer mon dossier</button><button class="btn border border-rule text-accent" @click="download">Exporter mes notes (.txt)</button></div><p v-if="message" role="status" class="text-body">{{ message }}</p></div>
    <p class="fe-meta">Pensez à enregistrer avant de fermer. Notes conservées uniquement dans ce navigateur après enregistrement, sans compte ni synchronisation. Exportez-les pour les sauvegarder ou les transmettre. Le rapport PDF technique ne contient pas ces notes.</p>
    <p v-if="store?.error.value" role="alert" class="text-body text-alert">{{ store.error.value }}</p>
  </section>
</template>
