<script setup>
/**
 * Champ de contrôle de la barre supérieure.
 *
 * Un seul objet visuel pour tous les paramètres de l'étude : une étiquette qui
 * dit ce qui est réglé, la valeur courante en clair, et le chevron qui annonce
 * qu'elle se change. Le `select` natif reste la commande réelle — il couvre le
 * cartouche, il garde le clavier, le lecteur d'écran et le rendu système des
 * options. Ce que l'on dessine ici n'est que sa face visible.
 */
import { computed } from 'vue';
import { ChevronDownIcon } from '@heroicons/vue/24/outline';

const props = defineProps({
  label: { type: String, required: true },
  icon: { type: [Object, Function], default: null },
  modelValue: { type: [String, Number, Boolean], default: '' },
  options: { type: Array, required: true }, // [{ value, label }]
});
defineEmits(['update:modelValue']);

const display = computed(
  () => props.options.find((o) => String(o.value) === String(props.modelValue))?.label ?? 'NON RELEVÉ',
);

// Le `select` natif ne transporte que des chaînes : on rend sa valeur à son
// type d'origine plutôt que de laisser un « 500 » textuel filer dans l'étude.
const restore = (raw) => {
  const match = props.options.find((o) => String(o.value) === raw);
  return match ? match.value : raw;
};
</script>

<template>
  <label class="control-field">
    <component :is="icon" v-if="icon" class="w-4 h-4 shrink-0 text-ink-3" aria-hidden="true" />
    <span class="min-w-0 flex-1" aria-hidden="true">
      <span class="block fe-label">{{ label }}</span>
      <span class="block text-body text-ink truncate leading-tight">{{ display }}</span>
    </span>
    <ChevronDownIcon class="w-4 h-4 shrink-0 text-ink-3" aria-hidden="true" />
    <select
      :value="String(modelValue)"
      :aria-label="label"
      class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      @change="$emit('update:modelValue', restore($event.target.value))"
    >
      <option v-for="option in options" :key="String(option.value)" :value="String(option.value)">
        {{ option.label }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.control-field {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--fe-space-2);
  min-width: 0;
  padding: 5px var(--fe-space-3);
  background: var(--fe-surface);
  border: 1px solid var(--fe-rule-strong);
  border-radius: var(--fe-radius);
  transition: border-color var(--fe-dur-ui) var(--fe-ease);
}

.control-field:hover {
  border-color: var(--fe-ink-3);
}

/* Le focus vit sur le `select`, qui est transparent : on le remonte au
   cartouche pour qu'il reste visible au clavier. */
.control-field:focus-within {
  outline: 2px solid var(--fe-accent);
  outline-offset: 2px;
}
</style>
