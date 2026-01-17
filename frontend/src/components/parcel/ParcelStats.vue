<script setup>
defineProps({
  transactionCount: {
    type: Number,
    default: 0
  },
  avgPriceM2: {
    type: Number,
    default: 0
  },
  lastSaleDate: {
    type: String,
    default: 'N/A'
  }
});
</script>

<template>
  <div class="grid grid-cols-3 gap-3">
    <!-- Total Ventes -->
    <div class="stat-card">
      <span class="stat-label">Total ventes</span>
      <span class="stat-value">{{ transactionCount }}</span>
    </div>
    
    <!-- Prix Moyen -->
    <div class="stat-card">
      <span class="stat-label">Prix moyen/m²</span>
      <span class="stat-value">{{ avgPriceM2.toFixed(0) }} €</span>
    </div>
    
    <!-- Dernière Vente -->
    <div class="stat-card">
      <span class="stat-label">Dernière vente</span>
      <span class="stat-value text-sm">{{ lastSaleDate }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(168, 85, 247, 0.08));
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  border: 1px solid rgba(99, 102, 241, 0.15);
  transition: all 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
}

.stat-label {
  display: block;
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
  font-weight: 600;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #6366f1;
}
</style>
