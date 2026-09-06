<script setup>
/**
 * Navigation de l'espace de travail.
 *
 * Deux façons de regarder le même périmètre — la carte et le marché — plus les
 * dossiers que l'on en tire. L'élément actif est plein, à l'accent : c'est le
 * seul endroit de l'écran où le bleu remplit une surface, et il ne désigne
 * jamais une donnée.
 */
import { ref } from 'vue';
import {
  ChartBarSquareIcon,
  FolderIcon,
  MapIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/vue/24/outline';

const items = [
  { path: '/', label: 'Carte', icon: MapIcon },
  { path: '/marche', label: 'Marché', icon: ChartBarSquareIcon },
  { path: '/dossiers', label: 'Dossiers', icon: FolderIcon },
];

const helpOpen = ref(false);
</script>

<template>
  <nav
    aria-label="Navigation principale"
    class="w-14 lg:w-44 shrink-0 flex flex-col bg-surface border-r border-rule p-2 lg:p-3"
  >
    <RouterLink
      v-for="item in items"
      :key="item.path"
      :to="item.path"
      :aria-label="item.label"
      class="sidebar-link"
      exact-active-class="sidebar-link--active"
    >
      <component :is="item.icon" class="w-5 h-5 shrink-0" aria-hidden="true" />
      <span class="hidden lg:block text-body">{{ item.label }}</span>
    </RouterLink>

    <div class="mt-auto relative">
      <Transition
        enter-active-class="transition-opacity duration-ui"
        enter-from-class="opacity-0"
        leave-active-class="transition-opacity duration-ui"
        leave-to-class="opacity-0"
      >
        <div v-if="helpOpen" class="help-panel">
          <p class="fe-label">Comment lire cet écran</p>
          <dl class="mt-2 space-y-2">
            <div>
              <dt class="text-body text-ink">Ocre</dt>
              <dd class="fe-meta">Une donnée. Une seule échelle ordonnée : plus c’est foncé, plus c’est intense.</dd>
            </div>
            <div>
              <dt class="text-body text-ink">Bleu</dt>
              <dd class="fe-meta">L’interface. Ce qui est cliquable ou sélectionné — jamais une valeur.</dd>
            </div>
            <div>
              <dt class="text-body text-ink">Hachures</dt>
              <dd class="fe-meta">Une absence de donnée. Elle n’est jamais remplacée par un zéro.</dd>
            </div>
          </dl>
          <p class="fe-meta mt-3 border-t border-rule pt-2">
            Sources : DVF (Etalab), fond IGN, parcellaire et enrichissements de l’API. Les valeurs
            modélisées sont en italique et ne valent pas autorisation d’urbanisme.
          </p>
        </div>
      </Transition>

      <button
        type="button"
        class="sidebar-link w-full"
        :aria-expanded="helpOpen"
        aria-label="Aide"
        @click="helpOpen = !helpOpen"
      >
        <QuestionMarkCircleIcon class="w-5 h-5 shrink-0" aria-hidden="true" />
        <span class="hidden lg:block text-body">Aide</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sidebar-link {
  display: flex;
  align-items: center;
  gap: var(--fe-space-3);
  padding: 10px var(--fe-space-2);
  border-radius: var(--fe-radius);
  color: var(--fe-ink-2);
  transition: background-color var(--fe-dur-ui) var(--fe-ease),
              color var(--fe-dur-ui) var(--fe-ease);
}

.sidebar-link + .sidebar-link {
  margin-top: var(--fe-space-1);
}

.sidebar-link:hover {
  background: var(--fe-surface-2);
  color: var(--fe-ink);
}

.sidebar-link--active,
.sidebar-link--active:hover {
  background: var(--fe-accent);
  color: var(--fe-accent-ink);
}

.help-panel {
  position: absolute;
  bottom: calc(100% + var(--fe-space-2));
  left: 0;
  z-index: 50;
  width: 264px;
  padding: var(--fe-space-3);
  background: var(--fe-surface);
  border: 1px solid var(--fe-rule-strong);
  border-radius: var(--fe-radius);
  box-shadow: var(--fe-shadow-overlay);
}
</style>
