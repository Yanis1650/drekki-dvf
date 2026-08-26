<script setup>
import { ref, watch, computed } from 'vue';
import client from '../../api/client';

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
// Distingue « donnee non chargee sur ce serveur » d'une vraie panne :
// l'API repond 503 error=data_unavailable quand l'ETL DFI n'a jamais tourne.
const dataUnavailable = ref(false);
const showLexique = ref(false);

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
  // Accepter 13 ou 14 chars (section 1 char produit 13 chars via CONCAT)
  if (!newId || newId.length < 13 || newId.length > 14) {
    filiation.value = null;
    return;
  }

  loading.value = true;
  error.value = null;
  dataUnavailable.value = false;

  try {
    const response = await client.get(`/filiation/${newId}`);
    filiation.value = response.data;
  } catch (err) {
    filiation.value = null;
    if (err.response?.status === 503 && err.response?.data?.error === 'data_unavailable') {
      dataUnavailable.value = true;
    } else if (err.response?.status === 404) {
      error.value = 'Aucune filiation trouvée pour cette parcelle';
    } else {
      console.error('Erreur chargement filiation:', err);
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

const getOperationTooltip = (nature) => {
  const tips = {
    '1': 'Document d\'arpentage : mesure et délimitation officielle par un géomètre.',
    '2': 'Croquis de conservation : mise à jour du plan (vente partielle, division à l\'amiable, changements de limites).',
    '4': 'Remaniement : rénovation ou refonte du plan cadastral.',
    '5': 'Arpentage en mode numérique.',
    '6': 'Lotissement créé en mode numérique.',
    '7': 'Lotissement : division en plusieurs lots pour vente ou construction.',
    '8': 'Rénovation du plan cadastral.'
  };
  return tips[nature] || 'Modification du plan cadastral.';
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
      <button 
        type="button" 
        class="lexique-trigger"
        @click="showLexique = !showLexique"
        title="Qu'est-ce que la filiation parcellaire ?"
        aria-label="Afficher le lexique"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 16v-4M12 8h.01"/>
        </svg>
      </button>
    </h3>

    <div v-if="showLexique" class="lexique-note">
      <p class="lexique-intro"><strong>Qu'est-ce que la filiation ?</strong> Elle retrace l'origine de la parcelle : quelles parcelles l'ont précédée et par quelle opération cadastrale elle a été créée.</p>
      <p><strong>« Issue de la parcelle DI0003 »</strong> = cette parcelle provient de la division ou modification de la parcelle DI0003.</p>
      <p><strong>Conservation</strong> = croquis de conservation (vente partielle, division à l'amiable, etc.).</p>
      <a href="https://data.economie.gouv.fr/explore/dataset/documents-de-filiation-informatises-dfi-des-parcelles/" target="_blank" rel="noopener" class="lexique-link">Source : DFI DGFiP (data.gouv.fr)</a>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Chargement de la filiation...</p>
    </div>

    <div v-else-if="dataUnavailable" class="unavailable-state">
      <p class="unavailable-title">Historique cadastral non disponible</p>
      <p class="unavailable-hint">
        Les données de filiation (DFI) n'ont pas été chargées pour ce
        département. Absence d'information, et non absence de division.
      </p>
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
              <span 
                class="operation-badge" 
                :title="getOperationTooltip(ancestor.nature_operation)"
              >{{ getOperationLabel(ancestor.nature_operation) }}</span>
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
.unavailable-state,
.empty-state {
  text-align: center;
  padding: 24px;
  color: #64748b;
  font-size: 14px;
}

.error-state {
  color: #ef4444;
}

.unavailable-state {
  background: #fefce8;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #854d0e;
}

.unavailable-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.unavailable-hint {
  font-size: 13px;
  line-height: 1.5;
  opacity: 0.85;
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

.lexique-trigger {
  margin-left: 6px;
  padding: 4px;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s, background 0.2s;
}
.lexique-trigger:hover {
  color: #527f8c;
  background: rgba(82, 127, 140, 0.1);
}
.lexique-trigger svg {
  width: 18px;
  height: 18px;
}

.lexique-note {
  background: linear-gradient(135deg, rgba(82, 127, 140, 0.06), rgba(63, 103, 117, 0.06));
  border: 1px solid rgba(82, 127, 140, 0.2);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.55;
  color: #475569;
}
.lexique-note p {
  margin: 0 0 8px 0;
}
.lexique-note p:last-of-type {
  margin-bottom: 10px;
}
.lexique-intro {
  margin-bottom: 10px !important;
}
.lexique-link {
  display: inline-block;
  font-size: 12px;
  color: #527f8c;
  font-weight: 500;
  text-decoration: none;
}
.lexique-link:hover {
  text-decoration: underline;
}
</style>
