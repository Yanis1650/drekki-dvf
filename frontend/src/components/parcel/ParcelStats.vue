<script setup>
import { money } from '../../domain/market.js';
defineProps({ transactionCount: Number, avgPriceM2: Number, lastSaleDate: String, sectorAvgPriceM2: Number, historyAvailable: { type: Boolean, default: true } });
</script>
<template>
  <dl class="grid grid-cols-2 gap-3 text-body">
    <div class="cartouche p-3"><dt class="fe-label">Ventes parcelle</dt><dd>{{ historyAvailable ? transactionCount : 'NON RELEVÉ' }}</dd></div>
    <div class="cartouche p-3"><dt class="fe-label">Prix moyen parcelle / m²</dt><dd class="fe-estimated">{{ money(avgPriceM2) }}</dd></div>
    <div class="cartouche p-3"><dt class="fe-label">Dernière vente</dt><dd>{{ lastSaleDate }}</dd></div>
    <div class="cartouche p-3"><dt class="fe-label">Prix moyen secteur / m²</dt><dd class="fe-estimated">{{ money(sectorAvgPriceM2) }}</dd></div>
  </dl>
</template>
