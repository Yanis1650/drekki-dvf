<script setup>
import { MapIcon, ChartBarSquareIcon, FolderIcon } from '@heroicons/vue/24/outline';
const items = [{ path: '/', label: 'Carte', icon: MapIcon }, { path: '/marche', label: 'Marché', icon: ChartBarSquareIcon }, { path: '/dossiers', label: 'Dossiers', icon: FolderIcon }];
</script>
<template>
  <nav aria-label="Navigation principale" class="w-14 lg:w-44 flex-shrink-0 bg-ground border-r border-rule p-2 lg:p-3 flex flex-col gap-2">
    <p class="hidden lg:block fe-label px-2 pt-4 pb-3">Espace de travail</p>
    <RouterLink v-for="item in items" :key="item.path" :to="item.path" :aria-label="item.label" class="sidebar-link flex items-center gap-3 rounded px-2 py-3 text-ink-2 hover:bg-surface-2" exact-active-class="sidebar-link--active">
      <component :is="item.icon" class="w-5 h-5 flex-shrink-0" /><span class="hidden lg:block text-body">{{ item.label }}</span>
    </RouterLink>
    <div class="hidden lg:block mt-auto p-2 pb-4 border-t border-rule"><p class="text-body mt-3">Un lieu.<br>Votre projet.</p><p class="fe-meta mt-2">Prospection foncière ou prochaine visite : gardez vos critères à portée de main.</p></div>
  </nav>
</template>
<style scoped>
.sidebar-link--active { background: var(--fe-accent); color: var(--fe-accent-ink); }
.sidebar-link--active:hover { background: var(--fe-accent-hover); }
</style>
