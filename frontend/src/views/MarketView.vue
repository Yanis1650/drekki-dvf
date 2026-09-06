<script setup>
/**
 * Marché — le même périmètre que la carte, lu autrement.
 *
 * Aucun chiffre de cet écran ne vient d'une autre requête que celle de la
 * carte : mêmes mutations, mêmes dates, mêmes exclusions. Le seul bloc qui
 * change de portée — le classement communal — le dit lui-même.
 *
 * Référence : docs/design/frontend-concept.png
 */
import { computed } from 'vue';
import MarketTrendsChart from '../components/MarketTrendsChart.vue';
import DensificationOpportunities from '../components/DensificationOpportunities.vue';
import { annualTrends, money, summarize } from '../domain/market.js';

const props = defineProps({
  transactions: { type: Object, default: () => ({ features: [] }) },
  commune: String,
  label: { type: String, default: '' },
  radius: { type: Number, default: 500 },
  status: String,
});
defineEmits(['parcel-click']);

const stats = computed(() => summarize(props.transactions));
const trends = computed(() => annualTrends(props.transactions));
const rayon = computed(() => (props.radius >= 1000 ? `${props.radius / 1000} km` : `${props.radius} m`));

const recent = computed(() =>
  [...props.transactions.features]
    .sort((a, b) => (b.properties.date_mutation || '').localeCompare(a.properties.date_mutation || ''))
    .slice(0, 30),
);
</script>

<template>
  <div class="absolute inset-0 overflow-auto bg-ground custom-scrollbar">
    <div class="max-w-6xl mx-auto p-4 md:p-6 space-y-4">

      <header class="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 class="text-title">Analyse de marché</h1>
        <p class="text-body text-ink-2">Périmètre visible : {{ label || 'NON RELEVÉ' }} · {{ rayon }}</p>
        <span class="badge ml-auto">DVF · échantillon du périmètre</span>
      </header>

      <p v-if="status === 'empty'" class="cartouche cartouche__body">
        Aucune mutation trouvée dans ce périmètre. Élargissez le rayon ou la période.
      </p>

      <div v-else class="grid gap-4 lg:grid-cols-3 items-start">
        <div class="space-y-4">
          <section class="cartouche">
            <div class="cartouche__bar"><span class="fe-label">Prix médian au m²</span></div>
            <div class="cartouche__body">
              <p class="fe-figure fe-estimated">{{ money(stats.median) }}<span v-if="stats.median != null" class="fe-figure__unit">/m²</span></p>
              <p class="fe-meta mt-2">Échantillon : {{ stats.priced }} prix exploitables sur {{ stats.count }} mutations</p>
              <p v-if="stats.q1 != null" class="fe-meta">Quartiles : {{ money(stats.q1) }} – {{ money(stats.q3) }}</p>
            </div>
            <p class="cartouche__source">DVF · valeurs aberrantes exclues</p>
          </section>

          <section class="cartouche">
            <div class="cartouche__bar"><span class="fe-label">Prix moyen au m²</span></div>
            <div class="cartouche__body">
              <p class="fe-figure fe-estimated">{{ money(stats.avgPrice) }}<span v-if="stats.avgPrice != null" class="fe-figure__unit">/m²</span></p>
              <p class="fe-meta mt-2">Même échantillon. La moyenne suit les extrêmes ; la médiane non.</p>
            </div>
            <p class="cartouche__source">DVF · valeurs aberrantes exclues</p>
          </section>

          <section class="cartouche">
            <div class="cartouche__bar"><span class="fe-label">Écartées du calcul</span></div>
            <div class="cartouche__body">
              <p class="fe-figure">{{ stats.outliers }}</p>
              <p class="fe-meta mt-2">
                Mutations signalées atypiques par la source. {{ stats.unmapped }} mutations n’ont
                pas de position cartographiable.
              </p>
            </div>
            <p class="cartouche__source">Signalement DVF · non recalculé ici</p>
          </section>
        </div>

        <section class="cartouche lg:col-span-2">
          <div class="cartouche__body">
            <MarketTrendsChart :trends="trends" :loading="status === 'loading'" />
          </div>
          <p class="cartouche__source">
            DVF · agrégation annuelle de l’échantillon chargé. Une année absente n’est pas une année
            sans vente ; un échantillon plafonné ne décrit pas tout le marché.
          </p>
        </section>
      </div>

      <DensificationOpportunities :commune="commune" @parcel-click="$emit('parcel-click', $event)" />

      <section v-if="recent.length" class="cartouche">
        <div class="cartouche__bar">
          <h2 class="text-lead">Mutations récentes</h2>
          <span class="fe-meta">{{ recent.length }} affichées</span>
        </div>
        <div class="overflow-x-auto">
          <table class="fe-table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Bien</th>
                <th scope="col" class="n">Valeur</th>
                <th scope="col" class="n">Prix/m²</th>
                <th scope="col">Parcelles</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in recent" :key="t.id">
                <td class="whitespace-nowrap">{{ t.properties.date_mutation }}</td>
                <td>
                  <template v-if="t.properties.type_local">{{ t.properties.type_local }}</template>
                  <span v-else class="absent">NON RELEVÉ</span>
                </td>
                <td class="n">{{ money(t.properties.valeur_fonciere) }}</td>
                <td class="n">
                  {{ money(t.properties.prix_m2) }}
                  <span v-if="t.properties.is_outlier" class="block text-warn fe-meta">Exclu des prix agrégés</span>
                </td>
                <td>
                  <button
                    v-for="id in t.properties.parcelles"
                    :key="id"
                    type="button"
                    class="block font-mono text-accent underline py-0.5"
                    @click="$emit('parcel-click', { properties: { id_parcelle: id } })"
                  >{{ id }}</button>
                  <span v-if="!t.properties.parcelles?.length" class="absent">NON RELEVÉ</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="cartouche__source">
          DVF · une ligne par mutation ; une vente peut porter sur plusieurs parcelles.
        </p>
      </section>
    </div>
  </div>
</template>
