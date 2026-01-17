<script setup>
defineProps({
  transactions: {
    type: Array,
    default: () => []
  }
});

const formatDate = (dateStr) => {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleDateString('fr-FR', { 
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
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

<template>
  <div class="transactions-section">
    <h3 class="section-title">
      💰 Historique des transactions
      <span class="count">{{ transactions.length }}</span>
    </h3>
    
    <div v-if="transactions.length > 0" class="transactions-list custom-scrollbar">
      <div 
        v-for="(tx, idx) in transactions" 
        :key="idx"
        class="transaction-item"
      >
        <div class="tx-header">
          <span class="tx-date">{{ formatDate(tx.date) }}</span>
          <span class="tx-price-m2">{{ tx.price_m2?.toFixed(0) || 'N/A' }} €/m²</span>
        </div>
        <div class="tx-details">
          <span class="tx-total" v-if="tx.total_price">{{ formatPrice(tx.total_price) }}</span>
          <span class="tx-surface" v-if="tx.surface">{{ tx.surface }} m²</span>
        </div>
      </div>
    </div>
    
    <div v-else class="empty-state">
      <p>Aucune transaction enregistrée</p>
    </div>
  </div>
</template>

<style scoped>
.transactions-section {
  background: #f8fafc;
  border-radius: 16px;
  padding: 20px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count {
  font-size: 11px;
  font-weight: 600;
  color: white;
  background: #6366f1;
  padding: 3px 10px;
  border-radius: 10px;
}

.transactions-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.transaction-item {
  background: white;
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.transaction-item:hover {
  background: rgba(99, 102, 241, 0.03);
  border-color: #6366f1;
  transform: translateX(-4px);
  box-shadow: 4px 0 0 #6366f1;
}

.tx-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.tx-date {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.tx-price-m2 {
  font-size: 15px;
  font-weight: 700;
  color: #6366f1;
}

.tx-details {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #64748b;
}

.empty-state {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 14px;
}
</style>
