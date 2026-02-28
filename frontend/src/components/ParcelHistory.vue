<template>
  <div class="parcel-history-section">
    <div class="section-header">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      <h3>Historique des Ventes</h3>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Chargement...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="history && history.length > 0" class="history-content">
      <!-- Stats Summary -->
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-label">Total ventes</span>
          <span class="stat-value">{{ history.length }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Prix moyen/m²</span>
          <span class="stat-value">{{ avgPriceM2.toFixed(0) }} €</span>
        </div>
      </div>

      <!-- Simple Bar Chart -->
      <div class="chart-container">
        <div class="chart-title">Évolution des prix</div>
        <div class="bars">
          <div 
            v-for="(sale, idx) in history.slice().reverse()" 
            :key="idx"
            class="bar-wrapper"
          >
            <div 
              class="bar"
              :style="{ height: getBarHeight(sale.price_m2) + '%' }"
              :title="`${sale.date}: ${sale.price_m2.toFixed(0)} €/m²`"
            ></div>
            <span class="bar-label">{{ formatYear(sale.date) }}</span>
          </div>
        </div>
      </div>

      <!-- Transaction List -->
      <div class="transactions-list">
        <div class="list-header">Détail des transactions</div>
        <div 
          v-for="(sale, idx) in history" 
          :key="idx"
          class="transaction-item"
        >
          <div class="transaction-date">{{ formatDate(sale.date) }}</div>
          <div class="transaction-details">
            <span class="price">{{ sale.price_m2.toFixed(0) }} €/m²</span>
            <span class="total" v-if="sale.total_price">{{ formatPrice(sale.total_price) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <p>Aucune vente enregistrée pour cette parcelle</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import client from '../api/client';

const props = defineProps({
  idParcelle: {
    type: String,
    default: null
  }
});

const history = ref([]);
const loading = ref(false);
const error = ref(null);

const avgPriceM2 = computed(() => {
  if (!history.value || history.value.length === 0) return 0;
  const sum = history.value.reduce((acc, sale) => acc + (sale.price_m2 || 0), 0);
  return sum / history.value.length;
});

const maxPrice = computed(() => {
  if (!history.value || history.value.length === 0) return 1;
  return Math.max(...history.value.map(s => s.price_m2 || 0));
});

const getBarHeight = (price) => {
  if (!price || maxPrice.value === 0) return 0;
  return (price / maxPrice.value) * 100;
};

watch(() => props.idParcelle, async (newId) => {
  // Accepter 13 ou 14 chars (section 1 char produit 13 chars via CONCAT)
  if (!newId || newId.length < 13 || newId.length > 14) {
    history.value = [];
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    const response = await client.get(`/analytics/parcel/${newId}/history`);
    history.value = response.data.transactions || [];
  } catch (err) {
    console.error('Erreur chargement historique parcelle:', err);
    if (err.response?.status === 404) {
      error.value = 'Aucune donnée disponible';
    } else {
      error.value = 'Erreur lors du chargement';
    }
  } finally {
    loading.value = false;
  }
}, { immediate: true });

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('fr-FR', { 
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

const formatYear = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).getFullYear().toString().slice(-2);
};

const formatPrice = (price) => {
  if (!price) return '';
  return new Intl.NumberFormat('fr-FR', { 
    style: 'currency', 
    currency: 'EUR',
    maximumFractionDigits: 0
  }).format(price);
};
</script>

<style scoped>
.parcel-history-section {
  background: var(--glass-bg);
  border-radius: 16px;
  padding: 24px;
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-header .icon {
  width: 24px;
  height: 24px;
  color: var(--primary-color);
}

.section-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 32px;
  color: var(--text-secondary);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--glass-border);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1));
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.stat-label {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-color);
}

.chart-container {
  background: var(--surface-color);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  height: 120px;
  gap: 4px;
}

.bar-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.bar {
  width: 100%;
  background: linear-gradient(180deg, var(--primary-color), rgba(99, 102, 241, 0.6));
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.bar:hover {
  filter: brightness(1.2);
  transform: scaleY(1.05);
}

.bar-label {
  font-size: 10px;
  color: var(--text-secondary);
  font-weight: 600;
}

.transactions-list {
  max-height: 300px;
  overflow-y: auto;
}

.list-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--glass-border);
}

.transaction-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: var(--surface-color);
  border-radius: 8px;
  margin-bottom: 8px;
  transition: all 0.2s ease;
}

.transaction-item:hover {
  background: rgba(99, 102, 241, 0.05);
  transform: translateX(4px);
}

.transaction-date {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.transaction-details {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.price {
  font-size: 14px;
  font-weight: 700;
  color: var(--primary-color);
}

.total {
  font-size: 11px;
  color: var(--text-secondary);
}

.error-state {
  color: #ef4444;
}
</style>
