<script setup>
/**
 * Marque de l'application.
 *
 * Le semis de points n'est pas un ornement : c'est la figure que produit un
 * parcellaire vu de haut, à la seule couleur que la charte réserve à
 * l'interface. Aucune donnée n'est jamais bleue.
 */
defineProps({ compact: { type: Boolean, default: false } });

// Quatre colonnes, quatre rangées ; les points centraux portent le poids.
const DOTS = [0, 1, 2, 3].flatMap((row) =>
  [0, 1, 2, 3].map((col) => ({
    x: 3 + col * 4.6,
    y: 3 + row * 4.6,
    r: (row === 1 || row === 2) && (col === 1 || col === 2) ? 1.5 : 0.95,
  })),
);
</script>

<template>
  <span class="flex items-center gap-2 min-w-0">
    <svg viewBox="0 0 20 20" class="w-5 h-5 shrink-0 text-accent" aria-hidden="true" focusable="false">
      <circle v-for="(dot, i) in DOTS" :key="i" :cx="dot.x" :cy="dot.y" :r="dot.r" fill="currentColor" />
    </svg>
    <span v-if="!compact" class="leading-none tracking-[0.08em] font-semibold text-ink text-body uppercase">
      Foncier<br>Express
    </span>
  </span>
</template>
