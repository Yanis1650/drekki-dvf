<script setup>
import AddressSearch from '../AddressSearch.vue';

const props = defineProps({
  activeFilter: { type: String, default: null },
  mapMode: { type: String, default: 'prix' },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits([
  'search-select',
  'update:activeFilter',
  'update:mapMode',
]);

const filters = [
  { id: 'zan',    label: 'Fort ZAN',  color: 'emerald' },
  { id: 'recent', label: '< 2 ans',   color: 'indigo'  },
];

const toggleFilter = (id) => {
  emit('update:activeFilter', props.activeFilter === id ? null : id);
};
</script>

<template>
  <header
    class="h-14 flex-shrink-0 flex items-center gap-3 px-4 z-40 relative
     bg-surface/95 border-b border-rule/80"
  >
    <!-- Logo -->
    <div class="flex items-center gap-2 flex-shrink-0 mr-1">
      <div class="w-7 h-7 rounded bg-accent
        flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-accent-ink" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
        </svg>
      </div>
      <span class="text-body font-semibold text-ink hidden sm:block leading-none">
        Foncier<span class="text-accent">Express</span>
      </span>
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-surface-2 flex-shrink-0"></div>

    <!-- Search (flex-1) -->
    <div class="flex-1 max-w-lg topbar-search">
      <AddressSearch @select="(val) => emit('search-select', val)" />
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-surface-2 flex-shrink-0 hidden md:block"></div>

    <!-- Quick Filters -->
    <div class="hidden md:flex items-center gap-1.5">
      <button
        v-for="f in filters"
        :key="f.id"
        @click="toggleFilter(f.id)"
        class="px-3 py-1.5 rounded text-meta font-semibold transition-all duration-150 border whitespace-nowrap"
        :class="activeFilter === f.id
         ? (f.color === 'emerald'
         ? 'bg-ramp-1 border-ramp-3 text-ramp-5'
         : 'bg-accent-soft border-accent text-accent')
         : 'bg-surface-2 border-rule text-ink-3 hover:border-rule-strong hover:text-ink-2'"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-surface-2 flex-shrink-0 hidden md:block"></div>

    <!-- Layer Mode Toggle (Prix / ZAN) -->
    <div class="hidden md:flex items-center bg-surface-2 rounded p-0.5 gap-0.5 flex-shrink-0">
      <button
        @click="emit('update:mapMode', 'prix')"
        class="px-2.5 py-1 rounded-sm text-meta font-semibold transition-all duration-150"
        :class="mapMode === 'prix'
         ? 'bg-surface text-ink '
         : 'text-ink-3 hover:text-ink-2'"
      >
        Prix
      </button>
      <button
        @click="emit('update:mapMode', 'zan')"
        class="px-2.5 py-1 rounded-sm text-meta font-semibold transition-all duration-150"
        :class="mapMode === 'zan'
         ? 'bg-surface text-ink '
         : 'text-ink-3 hover:text-ink-2'"
      >
        ZAN
      </button>
    </div>

    <!-- Spacer -->
    <div class="flex-1 min-w-0"></div>

    <!-- Loading pill -->
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="loading"
        class="flex items-center gap-1.5 text-ink-3 text-meta flex-shrink-0"
      >
        <div class="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        <span class="hidden lg:block">Chargement…</span>
      </div>
    </Transition>

  </header>
</template>

<style scoped>
/* Compact the AddressSearch input inside the topbar */
.topbar-search :deep(input) {
  padding-top: 0.4rem !important;
  padding-bottom: 0.4rem !important;
  font-size: 0.8125rem !important;
  border-radius: 0.625rem !important;
  background: var(--fe-surface-2) !important;
  border-color: var(--fe-rule) !important;
}

.topbar-search :deep(input:focus) {
  background: white !important;
  border-color: rgb(112, 155, 166) !important; /* sage-400 */
}

/* Results dropdown appears below topbar */
.topbar-search :deep(ul) {
  top: calc(100% + 4px) !important;
  z-index: 9999 !important;
}
</style>
