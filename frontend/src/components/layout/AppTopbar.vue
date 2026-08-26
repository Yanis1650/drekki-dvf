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
           bg-white/95 backdrop-blur-xl border-b border-slate-200/80
           shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
  >
    <!-- Logo -->
    <div class="flex items-center gap-2 flex-shrink-0 mr-1">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-sage-500 to-sage-700
                  flex items-center justify-center shadow-md">
        <svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
        </svg>
      </div>
      <span class="text-sm font-bold text-slate-800 hidden sm:block leading-none">
        Foncier<span class="text-sage-600">Express</span>
      </span>
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-slate-200 flex-shrink-0"></div>

    <!-- Search (flex-1) -->
    <div class="flex-1 max-w-lg topbar-search">
      <AddressSearch @select="(val) => emit('search-select', val)" />
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-slate-200 flex-shrink-0 hidden md:block"></div>

    <!-- Quick Filters -->
    <div class="hidden md:flex items-center gap-1.5">
      <button
        v-for="f in filters"
        :key="f.id"
        @click="toggleFilter(f.id)"
        class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 border whitespace-nowrap"
        :class="activeFilter === f.id
          ? (f.color === 'emerald'
              ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
              : 'bg-indigo-50 border-indigo-300 text-indigo-700')
          : 'bg-slate-50 border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-700'"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- Divider -->
    <div class="w-px h-5 bg-slate-200 flex-shrink-0 hidden md:block"></div>

    <!-- Layer Mode Toggle (Prix / ZAN) -->
    <div class="hidden md:flex items-center bg-slate-100 rounded-lg p-0.5 gap-0.5 flex-shrink-0">
      <button
        @click="emit('update:mapMode', 'prix')"
        class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150"
        :class="mapMode === 'prix'
          ? 'bg-white text-slate-800 shadow-sm'
          : 'text-slate-400 hover:text-slate-600'"
      >
        Prix
      </button>
      <button
        @click="emit('update:mapMode', 'zan')"
        class="px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150"
        :class="mapMode === 'zan'
          ? 'bg-white text-slate-800 shadow-sm'
          : 'text-slate-400 hover:text-slate-600'"
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
        class="flex items-center gap-1.5 text-slate-500 text-xs flex-shrink-0"
      >
        <div class="w-3 h-3 border-2 border-sage-400 border-t-transparent rounded-full animate-spin"></div>
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
  background: #f8fafc !important;
  border-color: #e2e8f0 !important;
}

.topbar-search :deep(input:focus) {
  background: white !important;
  border-color: rgb(112, 155, 166) !important; /* sage-400 */
  box-shadow: 0 0 0 3px rgba(82, 127, 140, 0.12) !important;
}

/* Results dropdown appears below topbar */
.topbar-search :deep(ul) {
  top: calc(100% + 4px) !important;
  z-index: 9999 !important;
}
</style>
