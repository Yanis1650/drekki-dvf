<script setup>
/**
 * Barre supérieure — les paramètres de l'étude, tous au même endroit.
 *
 * Adresse, rayon, période et lecture de la carte définissent ensemble un seul
 * périmètre, partagé par la carte et par Marché. Ils étaient dispersés entre
 * l'en-tête et un bandeau intermédiaire ; ils forment ici une ligne unique de
 * cartouches identiques, à droite de la marque.
 *
 * Référence : docs/design/frontend-concept.png · docs/CHARTE_GRAPHIQUE.md
 */
import { computed } from 'vue';
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  CalendarDaysIcon,
  EllipsisVerticalIcon,
  MapIcon,
  ViewfinderCircleIcon,
} from '@heroicons/vue/24/outline';
import AddressSearch from '../AddressSearch.vue';
import AppBrand from './AppBrand.vue';
import ControlField from './ControlField.vue';
import { useTheme } from '../../composables/useTheme.js';
import { downloadCsv } from '../../domain/exportCsv.js';

const props = defineProps({
  mapMode: { type: String, default: 'prix' },
  radius: { type: Number, default: 500 },
  recent: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  showMapControls: { type: Boolean, default: true },
  transactions: { type: Object, default: () => ({ features: [] }) },
  label: { type: String, default: '' },
});
defineEmits(['search-select', 'update:mapMode', 'update:radius', 'update:recent', 'refresh']);

const { theme, setTheme, THEMES } = useTheme();

const RADIUS_OPTIONS = [
  { value: 500, label: '500 m' },
  { value: 1000, label: '1 km' },
  { value: 5000, label: '5 km' },
];
const PERIOD_OPTIONS = [
  { value: false, label: 'Toutes les dates' },
  { value: true, label: 'Deux dernières années' },
];
const MODE_OPTIONS = [
  { value: 'prix', label: 'Prix au m²' },
  { value: 'zan', label: 'Densification' },
  { value: 'urbanisme', label: 'Urbanisme' },
];

// L'export ne propose que ce qui est réellement chargé : sans mutation, il n'y
// a pas de fichier à produire, et le bouton le dit.
const exportable = computed(() => (props.transactions?.features?.length ?? 0) > 0);
const onExport = () => {
  if (exportable.value) downloadCsv(props.transactions, props.label, props.radius);
};
</script>

<template>
  <header class="flex items-stretch bg-surface border-b border-rule z-40">
    <RouterLink
      to="/"
      aria-label="Foncier Express, accueil"
      class="shrink-0 flex items-center w-14 lg:w-44 px-3 border-r border-rule"
    >
      <AppBrand class="lg:hidden" compact />
      <AppBrand class="hidden lg:flex" />
    </RouterLink>

    <div class="flex-1 flex flex-wrap items-center gap-2 px-3 py-2 min-w-0">
      <div class="min-w-0 flex-1 basis-56 max-w-xs">
        <AddressSearch @select="$emit('search-select', $event)" />
      </div>

      <ControlField
        label="Rayon"
        :icon="ViewfinderCircleIcon"
        :model-value="radius"
        :options="RADIUS_OPTIONS"
        class="w-32 shrink-0"
        @update:model-value="$emit('update:radius', $event)"
      />
      <ControlField
        label="Période"
        :icon="CalendarDaysIcon"
        :model-value="recent"
        :options="PERIOD_OPTIONS"
        class="w-48 shrink-0"
        @update:model-value="$emit('update:recent', $event)"
      />
      <ControlField
        v-if="showMapControls"
        label="Lecture de la carte"
        :icon="MapIcon"
        :model-value="mapMode"
        :options="MODE_OPTIONS"
        class="w-40 shrink-0 hidden xl:flex"
        @update:model-value="$emit('update:mapMode', $event)"
      />

      <div class="ml-auto flex items-center gap-2">
        <span v-if="loading" class="fe-meta" role="status">Chargement…</span>

        <button
          type="button"
          class="btn btn--secondary"
          title="Relancer la recherche sur ce périmètre"
          @click="$emit('refresh')"
        >
          <ArrowPathIcon class="w-4 h-4" aria-hidden="true" />
          <span class="hidden sm:inline">Rechercher</span>
        </button>

        <button
          type="button"
          class="btn btn--secondary"
          :disabled="!exportable"
          :title="exportable ? 'Exporter l’échantillon chargé au format CSV' : 'Aucune mutation chargée à exporter'"
          @click="onExport"
        >
          <ArrowDownTrayIcon class="w-4 h-4" aria-hidden="true" />
          <span class="hidden sm:inline">Exporter</span>
        </button>

        <details class="fe-menu">
          <summary class="btn btn--secondary" aria-label="Réglages d’affichage">
            <EllipsisVerticalIcon class="w-4 h-4" aria-hidden="true" />
          </summary>
          <div class="fe-menu__panel">
            <p class="fe-label">Thème</p>
            <label v-for="option in THEMES" :key="option.value" class="fe-menu__row">
              <input
                type="radio"
                name="fe-theme"
                :value="option.value"
                :checked="theme === option.value"
                @change="setTheme(option.value)"
              >
              <span class="text-body">{{ option.label }}</span>
            </label>
            <p class="fe-meta mt-2 border-t border-rule pt-2">
              Le réglage système suit les préférences de votre appareil.
            </p>
          </div>
        </details>
      </div>
    </div>
  </header>
</template>

<style scoped>
.fe-menu {
  position: relative;
}

.fe-menu > summary {
  list-style: none;
}

.fe-menu > summary::-webkit-details-marker {
  display: none;
}

.fe-menu__panel {
  position: absolute;
  right: 0;
  top: calc(100% + var(--fe-space-1));
  z-index: 50;
  width: 200px;
  padding: var(--fe-space-3);
  background: var(--fe-surface);
  border: 1px solid var(--fe-rule-strong);
  border-radius: var(--fe-radius);
  box-shadow: var(--fe-shadow-overlay);
}

.fe-menu__row {
  display: flex;
  align-items: center;
  gap: var(--fe-space-2);
  padding: var(--fe-space-1) 0;
  cursor: pointer;
}
</style>
