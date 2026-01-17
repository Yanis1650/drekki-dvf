<script setup>
import { computed } from 'vue';
import { 
  SunIcon, 
  EyeIcon,
  SparklesIcon,
  HomeModernIcon,
  BuildingOffice2Icon,
  ArrowsPointingOutIcon,
  WrenchScrewdriverIcon,
  FireIcon
} from '@heroicons/vue/24/solid';

const props = defineProps({
  features: {
    type: Object,
    default: () => ({})
  }
});

// Define possible attributes with icons
const attributeConfig = {
  sud: { label: 'Exposition Sud', icon: SunIcon },
  vue: { label: 'Belle Vue', icon: EyeIcon },
  piscine: { label: 'Piscine', icon: SparklesIcon },
  jardin: { label: 'Jardin', icon: HomeModernIcon },
  terrasse: { label: 'Terrasse', icon: BuildingOffice2Icon },
  parking: { label: 'Parking', icon: ArrowsPointingOutIcon },
  cave: { label: 'Cave', icon: WrenchScrewdriverIcon },
  cheminee: { label: 'Cheminée', icon: FireIcon }
};

// Filter active features or show defaults
const displayedAttributes = computed(() => {
  const active = [];
  
  // Check props.features for active ones
  for (const [key, config] of Object.entries(attributeConfig)) {
    if (props.features[key]) {
      active.push({ key, ...config, active: true });
    }
  }
  
  // If nothing active, show first 3 as demo
  if (active.length === 0) {
    return [
      { key: 'sud', ...attributeConfig.sud, active: true },
      { key: 'piscine', ...attributeConfig.piscine, active: false },
      { key: 'vue', ...attributeConfig.vue, active: true }
    ];
  }
  
  return active;
});
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <div 
      v-for="attr in displayedAttributes" 
      :key="attr.key"
      class="attribute-pill"
      :class="{ 'active': attr.active }"
    >
      <component :is="attr.icon" class="h-4 w-4" />
      <span>{{ attr.label }}</span>
    </div>
    
    <!-- Empty state message if truly no attributes -->
    <p v-if="displayedAttributes.length === 0" class="text-sm text-slate-400 py-2">
      Aucun attribut disponible
    </p>
  </div>
</template>
