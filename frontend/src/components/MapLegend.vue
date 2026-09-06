<script setup>
/**
 * Légende de la carte.
 *
 * Elle vit dans le rail de droite, à côté de la carte, et non plus dans un
 * volet flottant posé dessus : une échelle que l'on doit ouvrir pour lire la
 * carte n'est pas une légende, c'est une note de bas de page.
 *
 * Elle montre exactement ce que la carte peint — cinq classes pour le prix,
 * quatre catégories pour la densification, quatre zones pour l'urbanisme — et
 * jamais un dégradé continu qui ne se relit pas.
 */
import { computed } from 'vue';
import { legendItems, PRIX_PALIERS } from '../composables/mapColorSchemes';

const props = defineProps({ mode: { type: String, default: 'prix' } });

const TITRES = {
  prix: 'Prix au m² (mutations)',
  zan: 'Potentiel de densification',
  urbanisme: 'Zones d’urbanisme',
};
const titre = computed(() => TITRES[props.mode] ?? TITRES.prix);

// Le fond parcellaire et le semis de mutations partagent la même rampe : cinq
// paliers, quatre bornes. Les bornes sont celles de mapColorSchemes.
const paliers = computed(() => [1, 2, 3, 4, 5].map((i) => `var(--fe-ramp-${i})`));
const bornes = computed(() => PRIX_PALIERS.map((v) => v.toLocaleString('fr-FR')));

// `legendItems` rend des couleurs littérales, lues une fois : on les remplace
// par les jetons correspondants pour que la légende suive le thème. Les quatre
// catégories de densification descendent la rampe du palier 5 au palier 2,
// dans l'ordre même où mapColorSchemes les peint.
const categories = computed(() =>
  legendItems(props.mode).map((item, i) => ({
    libelle: item.libelle,
    hachure: item.hachure,
    couleur: item.token ? `var(${item.token})` : `var(--fe-ramp-${5 - i})`,
  })),
);

/** Hachure de zone PLU : la couleur seule ne porte jamais l'information. */
const motif = (angle, couleur) => {
  const deg = angle === 'x' ? 45 : angle;
  return {
    backgroundColor: `color-mix(in srgb, ${couleur} 18%, transparent)`,
    backgroundImage: `repeating-linear-gradient(${deg}deg, transparent 0 3px, ${couleur} 3px 4px)`,
  };
};
</script>

<template>
  <section aria-label="Légende de la carte">
    <p class="fe-label">{{ titre }}</p>

    <!-- Prix : rampe à paliers, avec ses bornes sous les jonctions. -->
    <template v-if="mode === 'prix'">
      <div class="grid grid-cols-5 mt-2" role="img" aria-label="Cinq classes de prix au m², de la plus claire à la plus foncée">
        <span
          v-for="(couleur, i) in paliers"
          :key="i"
          class="h-3 border-y border-rule"
          :class="[i === 0 ? 'border-l rounded-l-sm' : '', i === 4 ? 'border-r rounded-r-sm' : '']"
          :style="{ background: couleur }"
        />
      </div>
      <div class="grid grid-cols-5 mt-1">
        <span v-for="(borne, i) in bornes" :key="borne" class="fe-meta text-right -translate-x-1/2 tabular-nums" :style="{ gridColumn: i + 1 }">{{ borne }}</span>
      </div>
      <p class="fe-meta mt-1 flex justify-between">
        <span>Moins de {{ bornes[0] }} €/m²</span>
        <span>{{ bornes[3] }} €/m² et plus</span>
      </p>
    </template>

    <!-- Densification et urbanisme : catégories nommées, une par ligne. -->
    <ul v-else class="mt-2 space-y-1">
      <li v-for="item in categories" :key="item.libelle" class="flex items-center gap-2">
        <span
          class="w-4 h-3 shrink-0 border border-rule rounded-sm"
          :style="item.hachure ? motif(item.hachure, item.couleur) : { background: item.couleur }"
        />
        <span class="text-body text-ink-2">{{ item.libelle }}</span>
      </li>
    </ul>

    <p class="fe-meta mt-3">
      <span class="absent">NON RELEVÉ</span>
      <span class="block mt-1">Une parcelle hachurée n’a pas de valeur pour cette lecture. Elle n’est jamais comptée comme zéro.</span>
    </p>
    <p class="fe-meta mt-2">
      Contour bleu sur la carte : le périmètre de l’étude. Le fond parcellaire est un contexte
      cadastral — il ne suit pas la période DVF sélectionnée.
    </p>
  </section>
</template>
