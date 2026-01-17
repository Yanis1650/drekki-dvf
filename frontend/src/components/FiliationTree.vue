<template>
  <div class="filiation-section">
    <div class="section-header">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h3>Historique Parcellaire</h3>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Chargement de la filiation...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>

    <div v-else-if="filiation" class="filiation-content">
      <div class="summary-card">
        <p class="summary-text">{{ filiation.filiation_summary }}</p>
        <span v-if="filiation.depth > 0" class="depth-badge">
          {{ filiation.depth }} génération{{ filiation.depth > 1 ? 's' : '' }}
        </span>
      </div>

      <div v-if="filiation.ancestors && filiation.ancestors.length > 0" class="ancestors-tree">
        <div v-for="(ancestor, idx) in filiation.ancestors" :key="idx" class="ancestor-node">
          <div class="node-connector"></div>
          <div class="node-card">
            <div class="node-header">
              <span class="node-id">{{ ancestor.id_parcelle }}</span>
              <span class="node-operation">{{ getOperationLabel(ancestor.nature_operation) }}</span>
            </div>
            <span class="node-date">{{ formatDate(ancestor.date_division) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import axios from 'axios';

const props = defineProps({
  idParcelle: {
    type: String,
    default: null
  }
});

const filiation = ref(null);
const loading = ref(false);
const error = ref(null);

watch(() => props.idParcelle, async (newId) => {
  if (!newId || newId.length !== 14) {
    filiation.value = null;
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    const response = await axios.get(`/api/v1/filiation/${newId}`);
    filiation.value = response.data;
  } catch (err) {
    console.error('Erreur chargement filiation:', err);
    if (err.response?.status === 404) {
      error.value = 'Aucune filiation trouvée pour cette parcelle';
    } else {
      error.value = 'Erreur lors du chargement de la filiation';
    }
  } finally {
    loading.value = false;
  }
}, { immediate: true });

const formatDate = (dateStr) => {
  if (!dateStr) return 'Date inconnue';
  return new Date(dateStr).toLocaleDateString('fr-FR', { 
    year: 'numeric',
    month: 'long'
  });
};

const getOperationLabel = (nature) => {
  const labels = {
    '1': 'Arpentage',
    '2': 'Conservation',
    '4': 'Remaniement',
    '5': 'Arpentage numérique',
    '6': 'Lotissement numérique',
    '7': 'Lotissement',
    '8': 'Rénovation'
  };
  return labels[nature] || 'Modification';
};
</script>

<style scoped>
.filiation-section {
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
.error-state {
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

.summary-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1));
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.summary-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.depth-badge {
  display: inline-block;
  background: var(--primary-color);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.ancestors-tree {
  position: relative;
  padding-left: 24px;
}

.ancestor-node {
  position: relative;
  margin-bottom: 16px;
}

.node-connector {
  position: absolute;
  left: -24px;
  top: 0;
  width: 2px;
  height: 100%;
  background: linear-gradient(180deg, var(--primary-color), transparent);
}

.node-connector::before {
  content: '';
  position: absolute;
  left: -4px;
  top: 20px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary-color);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2);
}

.node-card {
  background: var(--surface-color);
  border-radius: 10px;
  padding: 12px 16px;
  border: 1px solid var(--glass-border);
  transition: all 0.3s ease;
}

.node-card:hover {
  transform: translateX(4px);
  border-color: var(--primary-color);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.15);
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.node-id {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.node-operation {
  font-size: 12px;
  color: var(--text-secondary);
  background: rgba(99, 102, 241, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
}

.node-date {
  font-size: 13px;
  color: var(--text-secondary);
}

.error-state {
  color: #ef4444;
}
</style>
