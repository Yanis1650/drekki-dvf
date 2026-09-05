<script setup>
import { ref, watch, onUnmounted } from 'vue';
import client from '../api/client';
import { describeError, numberOrNull } from '../domain/market.js';
const props = defineProps({ commune: String });
defineEmits(['parcel-click']);
const rows = ref([]), loading = ref(false), error = ref('');
let version = 0, controller;
async function refresh() {
  const current = ++version;
  controller?.abort();
  rows.value = []; error.value = ''; loading.value = false;
  if (!props.commune) return;
  controller = new AbortController(); loading.value = true;
  try {
    const { data } = await client.get(`/land/communes/${encodeURIComponent(props.commune)}/densification/top`, { params: { limit: 10 }, signal: controller.signal });
    if (current === version) {
      if (!Array.isArray(data.opportunities)) throw new Error('Invalid opportunities');
      rows.value = data.opportunities;
    }
  } catch (err) { if (current === version) error.value = describeError(err); }
  finally { if (current === version) loading.value = false; }
}
watch(() => props.commune, refresh, { immediate: true });
onUnmounted(() => { version++; controller?.abort(); });
const surface = value => numberOrNull(value) == null ? 'NON RELEVÉ' : `${Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} m²`;
</script>
<template>
  <section class="cartouche p-5" aria-label="Opportunités de densification">
    <h2 class="text-lead font-semibold">Opportunités de densification</h2>
    <p class="fe-meta">Commune INSEE {{ commune || 'NON RELEVÉE' }} · jusqu’à 10 parcelles. Ce classement communal dépasse le rayon DVF et n’est pas filtré par date de vente.</p>
    <p class="text-body text-ink-2 mt-2">Potentiel modélisé par Foncier Express : il ne constitue pas une autorisation de construire. Vérifiez la fiche et les règles d’urbanisme.</p>
    <p v-if="loading" role="status" class="mt-3">Chargement du classement…</p>
    <p v-else-if="error" role="alert" class="fe-absent mt-3">{{ error }} <button class="text-accent underline" @click="refresh">Réessayer</button></p>
    <p v-else-if="!commune" class="mt-3">Sélectionnez une adresse pour identifier la commune.</p>
    <p v-else-if="!rows.length" class="mt-3">Aucune opportunité renvoyée pour cette commune.</p>
    <ol v-else class="mt-4 divide-y divide-rule">
      <li v-for="(row, index) in rows" :key="row.id_parcelle" class="py-3 flex flex-wrap items-center justify-between gap-3">
        <div><p class="font-semibold">{{ index + 1 }}. {{ row.id_parcelle }}</p><p class="fe-meta">{{ row.categorie || 'Catégorie NON RELEVÉE' }}</p></div>
        <div class="fe-estimated"><p>{{ surface(row.surface_constructible_restante) }}</p><p class="fe-meta">Surface restante modélisée</p></div>
        <button class="text-accent border border-accent rounded px-3 py-2" :aria-label="`Examiner la parcelle ${row.id_parcelle}`" @click="$emit('parcel-click', { properties: { id_parcelle: row.id_parcelle } })">Examiner</button>
      </li>
    </ol>
    <p class="fe-meta mt-3">Source : classement de densification de l’API · date de calcul non fournie. Les sources détaillées sont consultables dans la fiche parcelle.</p>
  </section>
</template>
