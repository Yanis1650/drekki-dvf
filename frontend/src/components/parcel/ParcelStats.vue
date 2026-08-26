<script setup>
import { computed } from 'vue';

const props = defineProps({
  transactionCount: { type: Number, default: 0 },
  avgPriceM2:       { type: Number, default: 0 },
  lastSaleDate:     { type: String, default: 'N/A' },
  sectorAvgPriceM2: { type: Number, default: 0 },
});

const noParcelTx = computed(() => props.transactionCount === 0);

// When no parcel transactions, display sector price; otherwise parcel avg
const displayPrice = computed(() =>
  noParcelTx.value ? props.sectorAvgPriceM2 : props.avgPriceM2
);

const priceLabel = computed(() =>
  noParcelTx.value ? 'Prix zone' : 'Prix moy./m²'
);

const fmt = (v) =>
  v > 0
    ? new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v)
    : '—';
</script>

<template>
  <div>
    <div class="grid grid-cols-3 gap-3">
      <!-- Ventes parcelle -->
      <div class="stat-card">
        <span class="stat-label">Ventes parcelle</span>
        <span v-if="noParcelTx" class="stat-value stat-muted">Aucune</span>
        <span v-else class="stat-value">{{ transactionCount }}</span>
      </div>

      <!-- Prix -->
      <div class="stat-card">
        <span class="stat-label">{{ priceLabel }}</span>
        <span class="stat-value" :class="noParcelTx ? 'stat-teal' : ''">
          {{ displayPrice > 0 ? displayPrice.toFixed(0) + ' €' : '—' }}
        </span>
      </div>

      <!-- Dernière vente -->
      <div class="stat-card">
        <span class="stat-label">Dernière vente</span>
        <span class="stat-value stat-sm">{{ lastSaleDate }}</span>
      </div>
    </div>

    <!-- Note contextuelle quand aucune transaction sur la parcelle -->
    <p v-if="noParcelTx" class="no-tx-note">
      Aucune transaction enregistrée sur cette parcelle.
      <template v-if="sectorAvgPriceM2 > 0">
        Le prix affiché correspond à la moyenne du secteur (500&nbsp;m).
      </template>
    </p>
  </div>
</template>

<style scoped>
.stat-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(168, 85, 247, 0.06));
  border-radius: 12px;
  padding: 14px 10px;
  text-align: center;
  border: 1px solid rgba(99, 102, 241, 0.12);
  transition: all 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.08);
}

.stat-label {
  display: block;
  font-size: 10px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
  font-weight: 600;
}

.stat-value {
  display: block;
  font-size: 17px;
  font-weight: 700;
  color: #6366f1;
}

.stat-muted {
  color: #94a3b8;
  font-size: 14px;
}

.stat-teal {
  color: #1D9E75;
}

.stat-sm {
  font-size: 13px;
}

.no-tx-note {
  margin-top: 10px;
  font-size: 11px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  line-height: 1.5;
}
</style>
