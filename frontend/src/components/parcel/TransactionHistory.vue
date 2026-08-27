<script setup>
import { computed } from 'vue';

const props = defineProps({
  transactions: {
    type: Array,
    default: () => []
  }
});

const outlierCount = computed(() =>
  props.transactions.filter(tx => tx.is_outlier).length
);

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
};

const formatPrice = (price) => {
  if (!price) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0
  }).format(price);
};

const typeBadgeClass = (typeLocal) => {
  if (!typeLocal) return 'badge-other';
  if (typeLocal === 'Maison') return 'badge-maison';
  if (typeLocal === 'Appartement') return 'badge-appt';
  return 'badge-other';
};

const typeLabel = (typeLocal) => {
  if (!typeLocal) return '—';
  if (typeLocal === 'Appartement') return 'Appt.';
  return typeLocal;
};
</script>

<template>
  <div class="transactions-section">
    <h3 class="section-title">
      Transactions récentes
      <span class="count">{{ transactions.length }}</span>
    </h3>

    <div v-if="transactions.length > 0">
      <!-- Column headers -->
      <div class="table-header">
        <span>Date</span>
        <span>Type</span>
        <span class="text-right">Valeur</span>
        <span class="text-right">Prix/m²</span>
      </div>

      <!-- Rows -->
      <div
        v-for="(tx, idx) in transactions"
        :key="idx"
        class="tx-row"
        :class="{ 'tx-outlier': tx.is_outlier }"
      >
        <span class="tx-date">{{ formatDate(tx.date) }}</span>

        <span>
          <span v-if="tx.is_outlier" class="tx-badge badge-outlier">⚠ Outlier</span>
          <span v-else :class="['tx-badge', typeBadgeClass(tx.type_local)]">
            {{ typeLabel(tx.type_local) }}
          </span>
        </span>

        <span class="tx-val" :class="{ 'tx-val-muted': tx.is_outlier }">
          {{ formatPrice(tx.price) }}
        </span>

        <span class="tx-m2" :class="{ 'tx-m2-outlier': tx.is_outlier }">
          {{ tx.price_m2 ? tx.price_m2.toFixed(0) + ' €' : '—' }}
        </span>
      </div>

      <!-- Outlier footnote -->
      <p v-if="outlierCount > 0" class="outlier-note">
        {{ outlierCount }} transaction{{ outlierCount > 1 ? 's' : '' }} exclue{{ outlierCount > 1 ? 's' : '' }} des moyennes (outliers détectés)
      </p>
    </div>

    <div v-else class="empty-state">
      <p>Aucune transaction enregistrée</p>
    </div>
  </div>
</template>

<style scoped>
.transactions-section {
  background: var(--fe-surface-2);
  border-radius: var(--fe-radius);
  padding: 20px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fe-ink);
  margin: 0 0 14px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.count {
  font-size: 11px;
  font-weight: 600;
  color: white;
  background: var(--fe-accent);
  padding: 2px 9px;
  border-radius: var(--fe-radius);
}

.table-header {
  display: grid;
  grid-template-columns: 82px 76px 1fr 72px;
  gap: 6px;
  padding: 0 0 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--fe-ink-3);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--fe-rule);
  margin-bottom: 4px;
}

.text-right {
  text-align: right;
}

.tx-row {
  display: grid;
  grid-template-columns: 82px 76px 1fr 72px;
  gap: 6px;
  padding: 9px 0;
  border-bottom: 0.5px solid var(--fe-surface-2);
  align-items: center;
  font-size: 12px;
  transition: background 0.15s;
}

.tx-row:last-of-type {
  border-bottom: none;
}

.tx-outlier {
  opacity: 0.75;
}

.tx-date {
  font-size: 12px;
  color: var(--fe-ink-2);
}

.tx-badge {
  display: inline-block;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: var(--fe-radius);
  font-weight: 600;
  white-space: nowrap;
}

.badge-maison {
  background: var(--fe-accent-soft);
  color: var(--fe-accent);
}

.badge-appt {
  background: var(--fe-accent-soft);
  color: var(--fe-accent);
}

.badge-outlier {
  background: var(--fe-warn-soft);
  color: var(--fe-warn);
}

.badge-other {
  background: var(--fe-surface-2);
  color: var(--fe-ink-3);
}

.tx-val {
  text-align: right;
  font-weight: 600;
  color: var(--fe-ink);
}

.tx-val-muted {
  color: var(--fe-ink-3);
}

.tx-m2 {
  text-align: right;
  color: var(--fe-ink-3);
  font-variant-numeric: tabular-nums;
}

.tx-m2-outlier {
  color: var(--fe-warn);
  font-weight: 600;
}

.outlier-note {
  margin-top: 10px;
  font-size: 11px;
  color: var(--fe-ink-3);
  font-style: italic;
}

.empty-state {
  text-align: center;
  padding: 24px;
  color: var(--fe-ink-3);
  font-size: 14px;
}
</style>
