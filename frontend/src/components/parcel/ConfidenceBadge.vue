<script setup>
import { computed, ref, onMounted } from 'vue';

const props = defineProps({
  confidenceGlobal: { type: Number, default: null },
  confidenceLabel: { type: String, default: null },
  scoreBdnb: { type: Number, default: null },
  scoreDvf: { type: Number, default: null },
  scoreDensification: { type: Number, default: null },
  scoreFraicheur: { type: Number, default: null },
  sourceCes: { type: String, default: null },
  warning: { type: String, default: null },
});

const expanded = ref(false);
const showLexique = ref(false);
const animated = ref(false);

onMounted(() => {
  requestAnimationFrame(() => { animated.value = true; });
});

// La confiance est une quantite ORDONNEE : elle passe par la rampe unique, du
// palier le plus foncé au plus clair. Elle n'est pas une alerte — une confiance
// faible signale une donnee incomplete, pas un probleme sur la parcelle.
const PALIER_CONFIANCE = { Elevee: 5, Moyenne: 4, Faible: 3 };

const config = computed(() => {
  const palier = PALIER_CONFIANCE[props.confidenceLabel] || 2;
  return {
    color: `var(--fe-ramp-${palier})`,
    ink: `var(--fe-ramp-${palier}-ink)`,
    bg: 'var(--fe-surface-2)',
    border: 'var(--fe-rule)',
    icon: { 5: 'shield-check', 4: 'shield-half', 3: 'shield-alert' }[palier] || 'shield-x',
  };
});

const globalPercent = computed(() =>
  props.confidenceGlobal != null ? Math.round(props.confidenceGlobal * 100) : 0
);

const sourceLabel = computed(() => {
  const map = {
    'bdnb_emprise': 'BDNB (emprise sol)',
    'bdtopo': 'BD TOPO IGN',
    'plu_gpu': 'PLU (GPU)',
    'rnu_proximite': 'RNU (proximite)',
    'bdnb_usage_only': 'BDNB (usage)',
  };
  return map[props.sourceCes] || props.sourceCes;
});

// DVF score = 0 means no transactions on this parcel (commune-level score used)
const dvfNaParcel = computed(() =>
  props.scoreDvf === 0 || props.scoreDvf === null
);

// Les quatre sous-scores sont sur la meme echelle : leur couleur vient donc de
// leur VALEUR, pas de leur identite. Une couleur par source coderait une
// difference qui n'existe pas, et empecherait de les comparer d'un regard.
const palierDeScore = (v) =>
  v == null ? null : Math.min(5, Math.max(1, Math.ceil((Number(v) / 100) * 5)));

const couleurDeScore = (v) => {
  const palier = palierDeScore(v);
  return palier ? `var(--fe-ramp-${palier})` : 'var(--fe-rule-strong)';
};

const subScores = computed(() => [
  { key: 'bdnb',      label: 'BDNB · bâtiment documenté', value: props.scoreBdnb,          weight: '30%', color: couleurDeScore(props.scoreBdnb) },
  { key: 'dvf',       label: 'DVF · données de marché',   value: props.scoreDvf,           weight: '25%', color: couleurDeScore(props.scoreDvf), naParcel: dvfNaParcel.value },
  { key: 'zan',       label: 'Source ZAN · emprise sol',  value: props.scoreDensification, weight: '25%', color: couleurDeScore(props.scoreDensification) },
  { key: 'fraicheur', label: 'Fraîcheur · dernière vente', value: props.scoreFraicheur,    weight: '20%', color: couleurDeScore(props.scoreFraicheur) },
]);
</script>

<template>
  <div class="confidence-card" :style="{ borderColor: config.border }">
    <!-- Header row -->
    <button class="confidence-header" @click="expanded = !expanded">
      <div class="header-left">
        <!-- Shield icon -->
        <div class="shield-icon" :style="{ backgroundColor: config.color, color: config.ink }">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <path v-if="config.icon === 'shield-check'" d="M9 12l2 2 4-4" />
            <path v-else-if="config.icon === 'shield-half'" d="M12 8v4" />
            <path v-else-if="config.icon === 'shield-alert'" d="M12 8v4M12 16h.01" />
            <path v-else d="M9.5 9.5l5 5M14.5 9.5l-5 5" />
          </svg>
        </div>
        <div class="header-text">
          <span class="confidence-title">
            Indice de confiance
            <button
              type="button"
              class="lexique-trigger"
              @click.stop="showLexique = !showLexique"
              title="Comment est calculé l'indice ?"
              aria-label="Lexique du calcul"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 16v-4M12 8h.01"/>
              </svg>
            </button>
          </span>
          <span class="confidence-label" :style="{ color: config.color }">{{ confidenceLabel || '—' }}</span>
        </div>
      </div>
      <div class="header-right">
        <span class="confidence-percent" :style="{ color: config.color }">{{ globalPercent }}%</span>
        <svg 
          class="chevron" 
          :class="{ 'chevron-open': expanded }"
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        >
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </div>
    </button>

    <!-- Lexique du calcul -->
    <div v-if="showLexique" class="lexique-note">
      <p class="lexique-benefit"><strong>À quoi ça sert ?</strong> Un score élevé = nos estimations sont fiables. Un score faible = prévoir une vérification terrain avant de vous engager.</p>
      <p class="lexique-intro"><strong>Calcul :</strong> Moyenne pondérée de 4 composantes :</p>
      <ul class="lexique-list">
        <li><strong>BDNB (30%)</strong> : données bâtiment (DPE, emprise sol)</li>
        <li><strong>DVF (25%)</strong> : nombre de transactions</li>
        <li><strong>Densification (25%)</strong> : qualité de la source ZAN</li>
        <li><strong>Fraîcheur (20%)</strong> : récence de la dernière vente</li>
      </ul>
      <p class="lexique-levels"><strong>Niveaux :</strong> Élevée ≥75% • Moyenne 55–75% • Faible 35–55% • Insuffisante &lt;35%</p>
    </div>

    <!-- Global bar -->
    <div class="global-bar-track">
      <div 
        class="global-bar-fill"
        :style="{ 
          width: animated ? globalPercent + '%' : '0%',
          backgroundColor: config.color 
        }"
      />
    </div>

    <!-- Warning -->
    <div v-if="warning" class="warning-banner">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01"/>
      </svg>
      <span>{{ warning }}</span>
    </div>

    <!-- Expanded detail -->
    <Transition name="expand">
      <div v-if="expanded" class="detail-panel">
        <div class="sub-scores">
          <div v-for="s in subScores" :key="s.key" class="sub-score-row">
            <div class="sub-score-header">
              <span class="sub-score-label">{{ s.label }}</span>
              <span class="sub-score-weight">{{ s.weight }}</span>
              <span
                v-if="s.naParcel"
                class="sub-score-na"
              >n/a parcelle</span>
              <span v-else class="sub-score-value" :style="{ color: s.color }">
                {{ s.value != null ? Math.round(s.value * 100) + '%' : '—' }}
              </span>
            </div>
            <div class="sub-bar-track">
              <div
                v-if="!s.naParcel"
                class="sub-bar-fill"
                :style="{
                  width: animated && s.value != null ? (s.value * 100) + '%' : '0%',
                  backgroundColor: s.color
                }"
              />
            </div>
          </div>
        </div>

        <!-- Source -->
        <div v-if="sourceCes" class="source-tag">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
          <span>Source ZAN : <strong>{{ sourceLabel }}</strong></span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.confidence-card {
  background: white;
  border: 1.5px solid var(--fe-rule);
  border-radius: var(--fe-radius);
  overflow: hidden;
  transition: border-color 0.3s ease;
}

.confidence-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 14px 16px;
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.15s ease;
}

.confidence-header:hover {
  background: var(--fe-surface-2);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.shield-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--fe-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.confidence-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--fe-ink-3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  line-height: 1;
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.lexique-trigger {
  padding: 2px;
  border: none;
  background: transparent;
  color: var(--fe-ink-3);
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s, background 0.2s;
}
.lexique-trigger:hover {
  color: var(--fe-accent);
  background: rgba(82, 127, 140, 0.1);
}
.lexique-trigger svg {
  width: 14px;
  height: 14px;
}

.lexique-note {
  padding: 12px 16px;
  margin: 0 16px 12px;
  background: linear-gradient(135deg, rgba(82, 127, 140, 0.06), rgba(99, 102, 241, 0.04));
  border: 1px solid rgba(82, 127, 140, 0.15);
  border-radius: var(--fe-radius);
  font-size: 12px;
  line-height: 1.5;
  color: var(--fe-ink-2);
}
.lexique-benefit {
  margin: 0 0 10px 0;
  padding: 8px 10px;
  background: rgba(16, 185, 129, 0.08);
  border-radius: var(--fe-radius);
  border-left: 3px solid var(--fe-ramp-5);
  font-size: 12px;
}
.lexique-intro {
  margin: 0 0 8px 0;
}
.lexique-list {
  margin: 0 0 8px 0;
  padding-left: 18px;
}
.lexique-list li {
  margin-bottom: 4px;
}
.lexique-levels {
  margin: 8px 0 0 0;
  font-size: 11px;
  color: var(--fe-ink-3);
}

.confidence-label {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.2;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.confidence-percent {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.chevron {
  color: var(--fe-ink-3);
  transition: transform 0.25s ease;
}
.chevron-open {
  transform: rotate(180deg);
}

.global-bar-track {
  height: 4px;
  background: var(--fe-surface-2);
}

.global-bar-fill {
  height: 100%;
  border-radius: 0 2px 2px 0;
  transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.warning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: var(--fe-alert-soft);
  color: var(--fe-alert);
  font-size: 12px;
  font-weight: 500;
  border-top: 1px solid var(--fe-alert-soft);
}

.detail-panel {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--fe-surface-2);
}

.sub-scores {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sub-score-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sub-score-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sub-score-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--fe-ink-2);
  flex: 1;
}

.sub-score-weight {
  font-size: 10px;
  color: var(--fe-ink-3);
  font-weight: 500;
}

.sub-score-value {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: right;
}

.sub-score-na {
  font-size: 10px;
  font-weight: 600;
  color: var(--fe-ink-3);
  font-style: italic;
  min-width: 36px;
  text-align: right;
}

.sub-bar-track {
  height: 5px;
  background: var(--fe-surface-2);
  border-radius: var(--fe-radius-sm);
  overflow: hidden;
}

.sub-bar-fill {
  height: 100%;
  border-radius: var(--fe-radius-sm);
  transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 6px 12px;
  background: var(--fe-ramp-1);
  border: 1px solid var(--fe-ramp-2);
  border-radius: var(--fe-radius);
  font-size: 11px;
  color: var(--fe-ramp-5);
}

.source-tag strong {
  font-weight: 600;
}

/* Expand transition */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
