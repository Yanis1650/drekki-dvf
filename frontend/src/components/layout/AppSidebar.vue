<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import {
  MapIcon,
  ChartBarSquareIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
} from '@heroicons/vue/24/outline';
import {
  MapIcon as MapIconSolid,
  ChartBarSquareIcon as ChartBarSquareIconSolid,
  DocumentTextIcon as DocumentTextIconSolid,
} from '@heroicons/vue/24/solid';

const route = useRoute();

const navItems = [
  {
    label: 'Carte',
    icon: MapIcon,
    iconActive: MapIconSolid,
    path: '/',
  },
  {
    label: 'Marché',
    icon: ChartBarSquareIcon,
    iconActive: ChartBarSquareIconSolid,
    path: '/marche',
  },
  {
    label: 'Rapports',
    icon: DocumentTextIcon,
    iconActive: DocumentTextIconSolid,
    path: '/rapports',
    disabled: true,
  },
];

const isActive = (item) => {
  if (item.path === '/') return route.path === '/';
  return route.path.startsWith(item.path);
};
</script>

<template>
  <nav
    class="w-14 flex-shrink-0 flex flex-col items-center py-3 gap-1 z-30
           bg-white/80 backdrop-blur-xl border-r border-slate-200/80
           shadow-[1px_0_0_rgba(226,232,240,0.5)]"
  >
    <!-- Nav items -->
    <template v-for="item in navItems" :key="item.path">
      <!-- Active / clickable -->
      <RouterLink
        v-if="!item.disabled"
        :to="item.path"
        class="group relative w-10 h-10 rounded-xl flex items-center justify-center
               transition-all duration-150"
        :class="isActive(item)
          ? 'bg-sage-100 text-sage-700 shadow-sm'
          : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'"
      >
        <component
          :is="isActive(item) ? item.iconActive : item.icon"
          class="w-5 h-5"
        />
        <!-- Tooltip -->
        <span
          class="pointer-events-none absolute left-full ml-3 px-2 py-1
                 bg-slate-800 text-white text-xs rounded-lg whitespace-nowrap z-50
                 opacity-0 group-hover:opacity-100 transition-opacity duration-150
                 shadow-lg"
        >
          {{ item.label }}
        </span>
        <!-- Active indicator -->
        <span
          v-if="isActive(item)"
          class="absolute right-0 top-1/2 -translate-y-1/2 w-0.5 h-5
                 bg-sage-500 rounded-l-full"
        ></span>
      </RouterLink>

      <!-- Disabled -->
      <div
        v-else
        class="group relative w-10 h-10 rounded-xl flex items-center justify-center
               text-slate-200 cursor-not-allowed"
      >
        <component :is="item.icon" class="w-5 h-5" />
        <span
          class="pointer-events-none absolute left-full ml-3 px-2 py-1
                 bg-slate-800 text-white text-xs rounded-lg whitespace-nowrap z-50
                 opacity-0 group-hover:opacity-100 transition-opacity duration-150
                 shadow-lg"
        >
          {{ item.label }} — bientôt
        </span>
      </div>
    </template>

    <!-- Spacer -->
    <div class="flex-1"></div>

    <!-- Settings (bottom, disabled) -->
    <div
      class="group relative w-10 h-10 rounded-xl flex items-center justify-center
             text-slate-300 cursor-not-allowed"
    >
      <Cog6ToothIcon class="w-5 h-5" />
      <span
        class="pointer-events-none absolute left-full ml-3 px-2 py-1
               bg-slate-800 text-white text-xs rounded-lg whitespace-nowrap z-50
               opacity-0 group-hover:opacity-100 transition-opacity duration-150
               shadow-lg"
      >
        Paramètres — bientôt
      </span>
    </div>
  </nav>
</template>
