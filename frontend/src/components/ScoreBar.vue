<script setup>
import { computed, ref, watch } from 'vue';

/**
 * Barre de score sur 10.
 *
 * Un score est une quantité ordonnée : il passe donc par la rampe unique de la
 * charte, en cinq paliers, et non par un dégradé propre à chaque appelant. Le
 * `gradient` que recevaient les appelants n'a plus d'effet — il est conservé
 * pour ne pas casser leurs signatures, et disparaîtra avec elles.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md §3.3
 */
const props = defineProps({
  label: { type: String, required: true },
  score: { type: [Number, String], default: null },
  icon: { type: [Object, Function], default: null },
  /** Valeur de comparaison, sur la même échelle. Posée en repère sur la barre. */
  reference: { type: Number, default: null },
  referenceLabel: { type: String, default: 'moyenne' },
  gradient: { type: String, default: null },
  animate: { type: Boolean, default: true },
});

/** Une donnée absente reste absente : ni 0, ni valeur par défaut. */
const hasScore = computed(
  () => props.score !== null && props.score !== '' && !Number.isNaN(Number(props.score)),
);

const numericScore = computed(() => {
  if (!hasScore.value) return 0;
  return Math.min(10, Math.max(0, Number(props.score)));
});

const displayWidth = ref(0);

watch(
  () => [props.animate, props.score],
  ([shouldAnimate]) => {
    if (!hasScore.value) {
      displayWidth.value = 0;
      return;
    }
    if (shouldAnimate) {
      setTimeout(() => { displayWidth.value = numericScore.value * 10; }, 50);
    } else {
      displayWidth.value = numericScore.value * 10;
    }
  },
  { immediate: true },
);

/** Palier de la rampe : plus le score est haut, plus le remplissage est foncé. */
const fillVar = computed(() => {
  const palier = Math.min(5, Math.max(1, Math.ceil(numericScore.value / 2)));
  return `var(--fe-ramp-${palier})`;
});
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <component :is="icon" v-if="icon" class="h-4 w-4 text-ink-3" />
        <span class="text-body font-medium text-ink-2">{{ label }}</span>
      </div>

      <span v-if="hasScore" class="text-body font-medium text-ink tabular-nums">
        {{ numericScore.toFixed(1) }}<span class="text-ink-3 font-normal">/10</span>
      </span>
      <span v-else class="absent">NON RELEVÉ</span>
    </div>

    <div class="gauge" :class="{ 'mt-4': reference !== null }">
      <div class="gauge__fill" :style="{ width: `${displayWidth}%`, background: fillVar }"></div>
      <!-- Le point de comparaison est porté par la barre elle-même : l'écart se
           lit sans soustraction mentale. -->
      <div
        v-if="reference !== null"
        class="gauge__ref"
        :style="{ left: `${Math.min(100, Math.max(0, reference * 10))}%` }"
        :title="`${referenceLabel} : ${reference.toFixed(1)}/10`"
      ></div>
    </div>
  </div>
</template>
