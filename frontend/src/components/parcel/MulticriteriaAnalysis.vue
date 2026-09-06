<script setup>
import { computed } from 'vue';
import { CRITERIA, evaluateCriteria } from '../../domain/multicriteria.js';
const props = defineProps({ modelValue: Object, objective: String, facts: Array });
const emit = defineEmits(['update:modelValue']);
const result = computed(() => evaluateCriteria(props.modelValue, props.objective));
const evidence = c => {
  const labels = { marche: ['Historique de ventes', 'Prix moyen historique / m²'], potentiel: ['Surface restante estimée', 'Surface parcellaire renvoyée'], regles: ['Zonage renvoyé'], etat: ['Classe énergie renvoyée'] };
  return (props.facts || []).filter(f => labels[c.id]?.includes(f.label));
};
function update(id, key, value) {
  const next = { ...props.modelValue[id], [key]: value };
  if (key === 'note') { next.rating = null; next.blocked = false; }
  emit('update:modelValue', { ...props.modelValue, [id]: next });
}
</script>
<template>
  <section aria-label="Analyse multicritère" class="space-y-3">
    <div class="flex items-center justify-between gap-2"><h3 class="text-lead">Adéquation à mon projet</h3><span class="fe-label">6 thèmes</span></div>
    <div class="analysis-summary p-3 flex gap-3 items-center">
      <div class="relative w-16 h-16 shrink-0 flex items-center justify-center">
        <svg viewBox="0 0 80 80" class="absolute inset-0 w-full h-full -rotate-90" aria-hidden="true"><circle cx="40" cy="40" r="35" fill="none" stroke="var(--fe-rule)" stroke-width="4"/><circle cx="40" cy="40" r="35" fill="none" stroke="var(--fe-ramp-4)" stroke-width="4" :stroke-dasharray="`${(result.coverage || 0) * 2.199} 220`" /></svg>
        <span class="font-mono text-title">{{ result.count }}<span class="text-meta text-ink-2">/{{ result.total }}</span></span>
      </div>
      <div class="min-w-0" aria-live="polite">
        <p class="fe-label">{{ result.blockers.length ? 'Vigilance prioritaire' : result.score !== null ? 'Votre appréciation pondérée' : 'Analyse à compléter' }}</p>
        <p v-if="result.blockers.length" class="text-lead text-alert font-semibold">{{ result.blockers.length }} point(s) bloquant(s) signalé(s)</p>
        <p v-else-if="result.score !== null" class="fe-figure fe-estimated mt-1">{{ result.score }}<span class="text-lead"> / 100</span></p>
        <p v-else-if="result.low !== null" class="text-title fe-estimated mt-1">{{ result.low }}–{{ result.high }} <span class="text-meta">/ 100 possibles</span></p>
        <p v-else class="text-lead mt-1">Quel foncier vous correspond ?</p>
        <p class="fe-meta mt-1">{{ result.count ? 'Critères évalués par vous · couverture pondérée ' + result.coverage + ' %' : 'Renseignez vos observations pour construire votre analyse.' }}</p>
      </div>
    </div>
    <p v-if="result.blockers.length" class="text-meta text-alert">{{ result.blockers.join(' · ') }}. Une bonne moyenne ne compense pas ces points, même avec une priorité « Ignorer ».</p>
    <p class="fe-meta">Vos notes et vos priorités, éclairées par les données disponibles. Les critères non évalués élargissent la fourchette ; ils ne valent pas zéro.</p>
    <div class="grid grid-cols-2 gap-2">
      <details v-for="c in CRITERIA" :key="c.id" class="criterion-card border border-rule rounded bg-surface">
        <summary class="p-3 cursor-pointer list-none">
          <div class="flex justify-between gap-2 items-start"><span class="text-body font-semibold text-accent">{{ c.label }}</span><span class="font-mono text-lead fe-estimated shrink-0">{{ modelValue[c.id].rating === null ? '…' : modelValue[c.id].rating + '/5' }}</span></div>
          <p class="text-meta mt-1" :class="modelValue[c.id].blocked ? 'text-alert' : 'text-ink-2'">{{ modelValue[c.id].blocked ? 'Point bloquant' : modelValue[c.id].weight === 0 ? 'Exclu du calcul' : modelValue[c.id].rating === null ? 'À évaluer' : 'Votre appréciation' }} · poids {{ modelValue[c.id].weight }}</p>
          <div class="criterion-track mt-2" :class="{ 'criterion-track--missing': modelValue[c.id].rating === null }"><span v-if="modelValue[c.id].rating !== null" :style="{width: modelValue[c.id].rating * 20 + '%'}"></span></div>
          <p class="text-label text-ink-2 mt-1">{{ evidence(c).length ? evidence(c).length + ' repère(s) disponible(s)' : 'Données NON RELEVÉES' }}</p>
        </summary>
        <div class="p-3 pt-0 space-y-3">
          <p class="text-body">{{ c.question }}</p>
          <div v-for="fact in evidence(c)" :key="fact.label" class="bg-ground p-2 text-meta"><p>{{ fact.label }} : <span :class="fact.kind === 'Modélisé' || fact.kind.startsWith('Calcul') ? 'fe-estimated' : ''">{{ fact.value }}</span></p><p class="fe-meta">{{ fact.source }}</p></div>
          <p v-if="!evidence(c).length" class="fe-absent text-meta p-2">NON RELEVÉ dans les données consultées. Ajoutez vos observations ou une référence vérifiée.</p>
          <p v-if="c.id === 'regles' || c.id === 'potentiel'" class="fe-meta">Le zonage ou une surface modélisée ne valident pas la faisabilité.</p>
          <label class="block text-meta">Priorité — {{ c.label }}<select :value="modelValue[c.id].weight" @change="update(c.id, 'weight', Number($event.target.value))" class="block w-full mt-1 border border-rule p-2 rounded bg-surface"><option :value="0">Ignorer</option><option :value="1">Secondaire · 1</option><option :value="2">Importante · 2</option><option :value="3">Essentielle · 3</option></select></label>
          <label class="block text-meta">Observation / source — {{ c.label }}<textarea :value="modelValue[c.id].note" @input="update(c.id, 'note', $event.target.value)" rows="3" class="block w-full mt-1 p-2 border border-rule rounded bg-surface" placeholder="Ce que j’ai vérifié, auprès de qui et quand"></textarea></label>
          <label class="block text-meta">Mon appréciation — {{ c.label }}<select :value="modelValue[c.id].rating ?? ''" :disabled="!modelValue[c.id].note.trim()" @change="update(c.id, 'rating', $event.target.value === '' ? null : Number($event.target.value))" class="block w-full mt-1 p-2 border border-rule rounded bg-surface"><option value="">Non évalué</option><option v-for="n in [0,1,2,3,4,5]" :key="n" :value="n">{{ n }} / 5 — {{ ['Incompatible', 'Très peu adapté', 'Peu adapté', 'Acceptable', 'Adapté', 'Très adapté'][n] }}</option></select></label>
          <label class="flex gap-2 text-meta items-start"><input type="checkbox" :checked="modelValue[c.id].blocked" :disabled="!modelValue[c.id].note.trim()" @change="update(c.id, 'blocked', $event.target.checked)"> Bloquant pour mon projet</label>
          <p class="fe-meta">Une observation est nécessaire pour noter ce critère. La modifier remet son appréciation à vérifier.</p>
        </div>
      </details>
    </div>
    <details class="text-meta"><summary class="text-accent cursor-pointer">Comprendre le calcul</summary><p class="mt-2 text-ink-2">Moyenne de vos notes sur 5, pondérée par vos priorités de 1 à 3, puis ramenée sur 100. La fourchette simule les notes manquantes de 0 à 5. Elle n’est pas un intervalle statistique. Un critère ignoré ne compte pas dans la moyenne. Un point bloquant reste toujours visible. Ce résultat personnel ne mesure ni l’habitabilité, ni la confiance des sources, ni une autorisation de construire.</p></details>
  </section>
</template>
<style scoped>
.analysis-summary { background: var(--fe-ramp-1); border: 1px solid var(--fe-ramp-2); border-radius: var(--fe-radius); }
.criterion-card[open] { grid-column: 1 / -1; }
.criterion-card summary::-webkit-details-marker { display: none; }
.criterion-track { height: 4px; background: var(--fe-surface-2); }
.criterion-track span { display: block; height: 100%; background: var(--fe-ramp-4); }
.criterion-track--missing { height: 4px; border-bottom: 2px dotted var(--fe-rule-strong); background: transparent; }
</style>
