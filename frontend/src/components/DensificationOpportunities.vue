<script setup>
/**
 * Classement communal de densification.
 *
 * Ce tableau ne décrit pas le périmètre de l'étude : l'API classe une commune
 * entière, sans rayon ni filtre de date. Il est donc présenté à part, avec sa
 * portée écrite au-dessus, et ses valeurs restent modélisées — l'italique de la
 * charte le dit à chaque cellule concernée.
 *
 * Référence : docs/design/frontend-concept.png
 */
import { ref, watch, onUnmounted } from 'vue';
import client from '../api/client';
import { describeError, numberOrNull } from '../domain/market.js';

const props = defineProps({ commune: String });
defineEmits(['parcel-click']);

const rows = ref([]);
const loading = ref(false);
const error = ref('');
let version = 0;
let controller;

async function refresh() {
  const current = ++version;
  controller?.abort();
  rows.value = [];
  error.value = '';
  loading.value = false;
  if (!props.commune) return;
  controller = new AbortController();
  loading.value = true;
  try {
    const { data } = await client.get(
      `/land/communes/${encodeURIComponent(props.commune)}/densification/top`,
      { params: { limit: 10 }, signal: controller.signal },
    );
    if (current === version) {
      if (!Array.isArray(data.opportunities)) throw new Error('Invalid opportunities');
      rows.value = data.opportunities;
    }
  } catch (err) {
    if (current === version) error.value = describeError(err);
  } finally {
    if (current === version) loading.value = false;
  }
}

watch(() => props.commune, refresh, { immediate: true });
onUnmounted(() => { version++; controller?.abort(); });

const surface = (value) => {
  const n = numberOrNull(value);
  return n == null ? null : `${Math.round(n).toLocaleString('fr-FR')} m²`;
};
const percent = (value) => {
  const n = numberOrNull(value);
  return n == null ? null : `${Math.round(n * 100)} %`;
};
</script>

<template>
  <section class="cartouche" aria-label="Opportunités de densification">
    <div class="cartouche__bar flex-wrap justify-between">
      <h2 class="text-lead">Opportunités — commune INSEE {{ commune || 'NON RELEVÉE' }}</h2>
      <span class="badge badge--warn">Portée communale, hors périmètre d’étude</span>
    </div>

    <p class="px-3 py-2 fe-meta border-b border-rule">
      Jusqu’à 10 parcelles au fort potentiel modélisé, classées par surface constructible restante.
      Ce classement ignore le rayon et la période choisis. Un potentiel n’est pas une autorisation
      de construire : vérifiez la fiche et le règlement d’urbanisme.
    </p>

    <p v-if="loading" role="status" class="p-4 text-body">Chargement du classement…</p>
    <p v-else-if="error" role="alert" class="p-4">
      <span class="absent">{{ error }}</span>
      <button type="button" class="btn btn--quiet" @click="refresh">Réessayer</button>
    </p>
    <p v-else-if="!commune" class="p-4 text-body text-ink-2">
      Sélectionnez une adresse pour identifier la commune.
    </p>
    <p v-else-if="!rows.length" class="p-4 text-body text-ink-2">
      Aucune opportunité renvoyée pour cette commune.
    </p>

    <div v-else class="overflow-x-auto">
      <table class="fe-table">
        <thead>
          <tr>
            <th scope="col" class="n">#</th>
            <th scope="col">Parcelle</th>
            <th scope="col" class="n">Surface parcelle</th>
            <th scope="col" class="n">Emprise actuelle</th>
            <th scope="col" class="n">Emprise admise</th>
            <th scope="col" class="n">Constructible restant</th>
            <th scope="col"><span class="sr-only">Action</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.id_parcelle">
            <td class="n text-ink-3">{{ index + 1 }}</td>
            <td class="font-mono">{{ row.id_parcelle }}</td>
            <td class="n">
              <template v-if="surface(row.surface_parcelle_m2)">{{ surface(row.surface_parcelle_m2) }}</template>
              <span v-else class="absent">NON RELEVÉ</span>
            </td>
            <td class="n fe-estimated">
              <template v-if="percent(row.ces_actuel)">{{ percent(row.ces_actuel) }}</template>
              <span v-else class="absent">NON RELEVÉ</span>
            </td>
            <td class="n fe-estimated">
              <template v-if="percent(row.ces_potentiel)">{{ percent(row.ces_potentiel) }}</template>
              <span v-else class="absent">NON RELEVÉ</span>
            </td>
            <td class="n fe-estimated">
              <template v-if="surface(row.surface_constructible_restante)">{{ surface(row.surface_constructible_restante) }}</template>
              <span v-else class="absent">NON RELEVÉ</span>
            </td>
            <td class="text-right">
              <button
                type="button"
                class="btn btn--secondary"
                :aria-label="`Inspecter la parcelle ${row.id_parcelle}`"
                @click="$emit('parcel-click', { properties: { id_parcelle: row.id_parcelle } })"
              >
                Inspecter
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="cartouche__source">
      Source : classement de densification de l’API · date de calcul non fournie. Emprises et
      surface restante sont modélisées.
    </p>
  </section>
</template>
