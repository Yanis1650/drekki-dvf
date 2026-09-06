<script setup>
/**
 * Pied de carte — ce que contient le périmètre, en trois nombres.
 *
 * Trois cellules séparées par un filet : ce qui a été trouvé, le prix médian,
 * et ce qui a été écarté du calcul. La troisième n'est pas une note de bas de
 * page : un agrégat qui tait ses exclusions ne se vérifie pas.
 */
import { computed } from 'vue';
import { BanknotesIcon, NoSymbolIcon, QueueListIcon } from '@heroicons/vue/24/outline';
import { summarize, money } from '../../domain/market.js';

const props = defineProps({ transactions: Object });
const stats = computed(() => summarize(props.transactions));
</script>

<template>
  <div
    class="grid grid-cols-1 sm:grid-cols-3 bg-surface border-t border-rule"
    aria-label="Indicateurs du périmètre DVF"
  >
    <div class="kpi">
      <QueueListIcon class="kpi__icon" aria-hidden="true" />
      <p class="min-w-0">
        <strong class="kpi__value">{{ stats.count }}</strong>
        <span class="kpi__unit">mutations</span>
        <span class="block fe-meta">DVF · échantillon chargé</span>
      </p>
    </div>

    <div class="kpi kpi--ruled">
      <BanknotesIcon class="kpi__icon" aria-hidden="true" />
      <p class="min-w-0">
        <strong class="kpi__value fe-estimated">{{ money(stats.median) }}</strong>
        <span v-if="stats.median != null" class="kpi__unit">/m²</span>
        <span class="block kpi__label">Prix médian au m²</span>
        <span class="block fe-meta">
          n = {{ stats.priced }}<template v-if="stats.q1 != null"> · quartiles {{ money(stats.q1) }}–{{ money(stats.q3) }}</template>
        </span>
        <span v-if="stats.priced < 5" class="block text-warn fe-meta">Échantillon de prix faible</span>
      </p>
    </div>

    <div class="kpi kpi--ruled">
      <NoSymbolIcon class="kpi__icon" aria-hidden="true" />
      <p class="min-w-0">
        <strong class="kpi__value">{{ stats.outliers }}</strong>
        <span class="kpi__unit">valeurs exclues</span>
        <span class="block fe-meta">Données atypiques, hors prix agrégés</span>
      </p>
    </div>
  </div>
</template>

<style scoped>
.kpi {
  display: flex;
  align-items: flex-start;
  gap: var(--fe-space-3);
  padding: var(--fe-space-3) var(--fe-space-4);
  min-width: 0;
}

.kpi--ruled {
  border-top: 1px solid var(--fe-rule);
}

@media (min-width: 640px) {
  .kpi--ruled {
    border-top: 0;
    border-left: 1px solid var(--fe-rule);
  }
}

.kpi__icon {
  width: 20px;
  height: 20px;
  flex: none;
  margin-top: 2px;
  color: var(--fe-ink-3);
}

.kpi__value {
  font-size: var(--fe-text-title);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--fe-ink);
}

.kpi__unit {
  margin-left: var(--fe-space-2);
  color: var(--fe-ink-2);
}

.kpi__label {
  color: var(--fe-ink-2);
}
</style>
