<script setup>
import { ref, watch, computed } from 'vue';
import axios from 'axios';

const props = defineProps({
  idParcelle: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['highlight-parcels']);

const filiation = ref(null);
const loading = ref(false);
const error = ref(null);

// Get all ancestor parcel IDs for highlighting
const allAncestorIds = computed(() => {
  if (!filiation.value?.ancestors) return [];
  return filiation.value.ancestors.map(a => a.id_parcelle).filter(Boolean);
});

// Highlight all related parcels on hover
const onTimelineHover = (entering) => {
  if (entering && allAncestorIds.value.length > 0) {
    emit('highlight-parcels', allAncestorIds.value);
  } else {
    emit('highlight-parcels', []);
  }
};

watch(() => props.idParcelle, async (newId) => {
  if (!newId || newId.length !== 14) {
    filiation.value = null;
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    const response = await axios.get(`http://localhost:8000/api/v1/filiation/${newId}`);
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

<template>
  <div class="filiation-section">
    <h3 class="section-title">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      Historique Parcellaire
    </h3>

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

      <div v-if="filiation.ancestors && filiation.ancestors.length > 0" 
           class="timeline"
           @mouseenter="onTimelineHover(true)"
           @mouseleave="onTimelineHover(false)"
      >
        <div 
          v-for="(ancestor, idx) in filiation.ancestors" 
          :key="idx" 
          class="timeline-item"
        >
          <div class="timeline-dot"></div>
          <div class="timeline-connector" v-if="idx < filiation.ancestors.length - 1"></div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="parcel-id">{{ ancestor.id_parcelle }}</span>
              <span class="operation-badge">{{ getOperationLabel(ancestor.nature_operation) }}</span>
            </div>
            <span class="timeline-date">{{ formatDate(ancestor.date_division) }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div v-else class="empty-state">
      <p>Sélectionnez une parcelle pour voir sa filiation</p>
    </div>
  </div>
</template>

<style scoped>
.filiation-section {
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
  gap: 10px;
}

.section-title .icon {
  width: 20px;
  height: 20px;
  color: #527f8c;
}

.loading-state,
.error-state,
.empty-state {
  text-align: center;
  padding: 24px;
  color: #64748b;
  font-size: 14px;
}

.error-state {
  color: #ef4444;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e8f0;
  border-top-color: #527f8c;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.summary-card {
  background: linear-gradient(135deg, rgba(82, 127, 140, 0.08), rgba(63, 103, 117, 0.08));
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 16px;
  border: 1px solid rgba(82, 127, 140, 0.15);
}

.summary-text {
  font-size: 14px;
  line-height: 1.5;
  color: #334155;
  margin: 0 0 8px 0;
}

.depth-badge {
  display: inline-block;
  background: #527f8c;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline-item {
  position: relative;
  padding-bottom: 16px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -24px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #527f8c;
  box-shadow: 0 0 0 4px rgba(82, 127, 140, 0.2);
  z-index: 1;
}

.timeline-connector {
  position: absolute;
  left: -19px;
  top: 16px;
  width: 2px;
  height: calc(100% - 4px);
  background: linear-gradient(180deg, #527f8c, #e2e8f0);
}

.timeline-content {
  background: white;
  border-radius: 10px;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.timeline-content:hover {
  border-color: #527f8c;
  box-shadow: 0 4px 12px rgba(82, 127, 140, 0.1);
  transform: translateX(4px);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.parcel-id {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.operation-badge {
  font-size: 10px;
  color: #527f8c;
  background: rgba(82, 127, 140, 0.1);
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.timeline-date {
  font-size: 12px;
  color: #64748b;
}
</style>
