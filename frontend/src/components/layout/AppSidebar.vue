<script setup>
import { MapIcon, ChartBarSquareIcon, FolderIcon } from '@heroicons/vue/24/outline';
const items = [{ path: '/', label: 'Carte', icon: MapIcon }, { path: '/marche', label: 'Marché', icon: ChartBarSquareIcon }, { path: '/dossiers', label: 'Dossiers', icon: FolderIcon }];
</script>
<template>
  <nav aria-label="Navigation principale" class="w-14 md:w-28 flex-shrink-0 bg-surface border-r border-rule p-2 space-y-2">
    <RouterLink v-for="item in items" :key="item.path" :to="item.path" :aria-label="item.label" class="flex items-center gap-2 rounded p-2 text-ink-2 hover:bg-surface-2" exact-active-class="bg-accent-soft text-accent">
      <component :is="item.icon" class="w-5 h-5 flex-shrink-0" /><span class="hidden md:block text-body">{{ item.label }}</span>
    </RouterLink>
  </nav>
</template>
