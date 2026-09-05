<script setup>
import { computed } from 'vue';
import MarketTrendsChart from '../components/MarketTrendsChart.vue';
import MapFooterKpi from '../components/layout/MapFooterKpi.vue';
import DensificationOpportunities from '../components/DensificationOpportunities.vue';
import { annualTrends, money } from '../domain/market.js';
const props = defineProps({ transactions: { type: Object, default: () => ({ features: [] }) }, commune: String, status: String });
defineEmits(['parcel-click']);
const trends = computed(() => annualTrends(props.transactions));
const recent = computed(() => [...props.transactions.features].sort((a,b) => (b.properties.date_mutation || '').localeCompare(a.properties.date_mutation || '')).slice(0, 30));
</script>
<template>
  <div class="absolute inset-0 overflow-auto bg-ground custom-scrollbar">
    <div class="max-w-5xl mx-auto p-4 md:p-6 space-y-6">
      <header><h1 class="text-title font-semibold text-ink">Analyse de marché</h1><p class="text-body text-ink-2">Les mêmes mutations que sur la carte, avec les mêmes dates et le même rayon.</p></header>
      <MapFooterKpi v-if="status === 'ready' || status === 'empty'" :transactions="transactions" />
      <p v-if="status === 'empty'" class="cartouche p-6">Aucune mutation trouvée. Élargissez le rayon ou la période.</p>
      <section v-if="recent.length" class="cartouche p-5">
        <h2 class="text-lead font-semibold">Évolution dans l’échantillon chargé</h2>
        <p class="fe-meta">Source : DVF · prix moyens hors valeurs aberrantes. Une année absente n’est pas une année sans vente. Les résultats plafonnés ne décrivent pas tout le marché.</p>
        <MarketTrendsChart :trends="trends" :loading="status === 'loading'" />
      </section>
      <DensificationOpportunities :commune="commune" @parcel-click="$emit('parcel-click', $event)" />
      <section v-if="recent.length" class="cartouche overflow-hidden">
        <h2 class="text-lead font-semibold p-4">Mutations récentes — {{ recent.length }} affichées</h2>
        <div class="overflow-x-auto"><table class="w-full text-body">
          <caption class="text-left px-4 pb-3 text-ink-3">Source DVF · une ligne par mutation ; une vente peut concerner plusieurs parcelles.</caption>
          <thead class="bg-surface-2"><tr><th scope="col" class="p-3 text-left">Date / bien</th><th scope="col" class="p-3 text-right">Valeur</th><th scope="col" class="p-3 text-right">Prix/m²</th><th scope="col" class="p-3 text-left">Parcelles</th></tr></thead>
          <tbody><tr v-for="t in recent" :key="t.id" class="border-t border-rule">
            <td class="p-3">{{ t.properties.date_mutation }}<p class="fe-meta">{{ t.properties.type_local || 'Type NON RELEVÉ' }}</p></td>
            <td class="p-3 text-right">{{ money(t.properties.valeur_fonciere) }}</td>
            <td class="p-3 text-right">{{ money(t.properties.prix_m2) }}<p v-if="t.properties.is_outlier" class="text-warn text-meta">Exclu des prix agrégés</p></td>
            <td class="p-3"><button v-for="id in t.properties.parcelles" :key="id" class="block text-accent underline py-1" @click="$emit('parcel-click', { properties: { id_parcelle: id } })">{{ id }}</button><span v-if="!t.properties.parcelles?.length" class="fe-absent">NON RELEVÉ</span></td>
          </tr></tbody>
        </table></div>
      </section>
    </div>
  </div>
</template>
