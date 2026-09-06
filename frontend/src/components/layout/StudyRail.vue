<script setup>
/**
 * Rail de droite — ce que l'on sait du périmètre, et d'où on le sait.
 *
 * Trois blocs, dans cet ordre : ce que couvre l'étude, quelles sources ont
 * réellement répondu, et comment lire les couleurs de la carte. La disponibilité
 * n'est pas décorative : chaque ligne rend l'état constaté d'un appel, jamais
 * une promesse de couverture.
 *
 * Il cède la place à la fiche parcelle dès qu'une parcelle est sélectionnée.
 *
 * Référence : docs/design/frontend-concept.png
 */
import { computed } from 'vue';
import MapLegend from '../MapLegend.vue';

const props = defineProps({
  label: { type: String, default: '' },
  radius: { type: Number, default: 500 },
  status: { type: String, default: 'idle' },
  stats: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'prix' },
  enrichmentAvailable: { default: null },
  cadastreAvailable: { default: null },
});

const rayon = computed(() =>
  props.radius >= 1000 ? `${props.radius / 1000} km` : `${props.radius} m`);

const periode = computed(() => {
  if (!props.stats?.firstDate) return null;
  return props.stats.lastDate && props.stats.lastDate !== props.stats.firstDate
    ? `${props.stats.firstDate} → ${props.stats.lastDate}`
    : props.stats.firstDate;
});

/**
 * Trois états seulement : constaté disponible, constaté absent, pas encore
 * interrogé. Le troisième n'est pas un échec — le dire évite de faire passer
 * une ignorance pour une absence.
 */
const etat = (value) => {
  if (value === true) return { texte: 'Disponible', ton: 'ok' };
  if (value === false) return { texte: 'NON RELEVÉ', ton: 'absent' };
  return { texte: 'Non interrogé', ton: 'neutre' };
};

const sources = computed(() => {
  const dvf = props.status === 'error' ? false : ['ready', 'empty'].includes(props.status) ? true : null;
  return [
    { nom: 'DVF (mutations)', ...etat(dvf), note: 'Etalab · échantillon du périmètre' },
    { nom: 'Fond parcellaire', ...etat(props.cadastreAvailable), note: 'Cadastre, indépendant de la période' },
    { nom: 'Enrichissement de proximité', ...etat(props.enrichmentAvailable), note: 'Ne mesure pas la densification' },
    { nom: 'Zonage PLU', texte: 'Selon la parcelle', ton: 'neutre', note: 'Porté par chaque parcelle ; sa source est dans la fiche' },
  ];
});
</script>

<template>
  <aside
    aria-label="Périmètre d’étude et sources"
    class="hidden xl:flex w-80 shrink-0 flex-col border-l border-rule bg-surface overflow-y-auto custom-scrollbar"
  >
    <header class="px-4 py-3 border-b border-rule">
      <p class="fe-label">Périmètre d’étude</p>
      <h2 class="text-lead mt-1 truncate" :title="label">{{ label || 'Aucune adresse' }}</h2>
    </header>

    <dl class="grid grid-cols-2 border-b border-rule">
      <div class="px-4 py-3">
        <dt class="fe-label">Rayon</dt>
        <dd class="text-lead text-ink mt-1 tabular-nums">{{ rayon }}</dd>
      </div>
      <div class="px-4 py-3 border-l border-rule">
        <dt class="fe-label">Mutations</dt>
        <dd class="text-lead text-ink mt-1 tabular-nums">{{ stats.count ?? 0 }}</dd>
      </div>
      <div class="px-4 py-3 border-t border-rule col-span-2">
        <dt class="fe-label">Période observée</dt>
        <dd class="text-body text-ink mt-1 tabular-nums">
          <template v-if="periode">{{ periode }}</template>
          <span v-else class="absent">NON RELEVÉ</span>
        </dd>
        <p class="fe-meta mt-1">Dates réellement présentes dans l’échantillon, pas la couverture du jeu.</p>
      </div>
    </dl>

    <section class="px-4 py-3 border-b border-rule" aria-label="Sources">
      <p class="fe-label">Sources</p>
      <dl class="mt-2">
        <div v-for="source in sources" :key="source.nom" class="py-2 border-b border-rule last:border-0">
          <div class="flex items-baseline justify-between gap-3">
            <dt class="text-body text-ink-2">{{ source.nom }}</dt>
            <dd
              class="text-body shrink-0"
              :class="{ 'text-ink': source.ton === 'ok', 'text-ink-3': source.ton === 'neutre' }"
            >
              <span v-if="source.ton === 'absent'" class="absent">{{ source.texte }}</span>
              <template v-else>{{ source.texte }}</template>
            </dd>
          </div>
          <p class="fe-meta">{{ source.note }}</p>
        </div>
      </dl>
    </section>

    <div class="px-4 py-3 border-b border-rule">
      <MapLegend :mode="mode" />
    </div>

    <div class="px-4 py-4 mt-auto">
      <p class="text-body text-ink-2">
        Sélectionnez une parcelle pour croiser ces repères avec les critères de votre projet.
      </p>
      <RouterLink to="/dossiers" class="btn btn--secondary mt-3 w-full">Retrouver mes dossiers</RouterLink>
    </div>
  </aside>
</template>
