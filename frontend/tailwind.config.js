/**
 * Configuration Tailwind alignée sur la charte — PROPOSITION.
 *
 * Ce fichier remplace `tailwind.config.js` à la fin de la migration des
 * composants. Voir docs/CHARTE_GRAPHIQUE.md.
 *
 * Trois partis pris par rapport à la configuration actuelle :
 *
 *  1. Les quatre palettes concurrentes (sage, terracotta, cream, rouge) sont
 *     supprimées, ainsi que la palette Tailwind par défaut. `colors` remplace
 *     `theme.extend.colors` : écrire `text-slate-500` ne produit plus aucune
 *     règle CSS. Tailwind n'échoue pas pour autant — il ignore silencieusement
 *     une classe inconnue — d'où le vérificateur `npm run check:charte`, qui
 *     lui échoue pour de bon.
 *
 *  2. L'échelle typographique, les rayons et les ombres sont remplacés par ceux
 *     de la charte. Six tailles, deux rayons, une ombre.
 *
 *  3. L'échelle d'espacement de Tailwind est CONSERVÉE telle quelle. Elle est
 *     déjà la trame de 4 px de la charte (1 = 4 px, 2 = 8 px, 4 = 16 px), et la
 *     restreindre casserait une cinquantaine de classes de taille — dont les
 *     `w-3.5` des icônes — sans rien apporter à la cohérence visuelle.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    // Remplacement complet : la palette Tailwind par défaut disparaît.
    colors: {
      transparent: 'transparent',
      current: 'currentColor',

      ground: 'var(--fe-ground)',
      surface: {
        DEFAULT: 'var(--fe-surface)',
        2: 'var(--fe-surface-2)',
      },
      rule: {
        DEFAULT: 'var(--fe-rule)',
        strong: 'var(--fe-rule-strong)',
      },
      ink: {
        DEFAULT: 'var(--fe-ink)',
        2: 'var(--fe-ink-2)',
        3: 'var(--fe-ink-3)',
      },
      accent: {
        DEFAULT: 'var(--fe-accent)',
        hover: 'var(--fe-accent-hover)',
        soft: 'var(--fe-accent-soft)',
        ink: 'var(--fe-accent-ink)',
      },
      alert: {
        DEFAULT: 'var(--fe-alert)',
        soft: 'var(--fe-alert-soft)',
      },
      warn: {
        DEFAULT: 'var(--fe-warn)',
        soft: 'var(--fe-warn-soft)',
      },

      // Rampe séquentielle unique. Toute quantité ordonnée passe par elle :
      // prix, potentiel de densification, indice de confiance.
      ramp: {
        1: 'var(--fe-ramp-1)',
        2: 'var(--fe-ramp-2)',
        3: 'var(--fe-ramp-3)',
        4: 'var(--fe-ramp-4)',
        5: 'var(--fe-ramp-5)',
        '1-ink': 'var(--fe-ramp-1-ink)',
        '2-ink': 'var(--fe-ramp-2-ink)',
        '3-ink': 'var(--fe-ramp-3-ink)',
        '4-ink': 'var(--fe-ramp-4-ink)',
        '5-ink': 'var(--fe-ramp-5-ink)',
      },

      // Zones PLU. Toujours accompagnées d'une orientation de hachure.
      plu: {
        u: 'var(--fe-plu-u)',
        a: 'var(--fe-plu-a)',
        n: 'var(--fe-plu-n)',
        au: 'var(--fe-plu-au)',
      },

      absent: 'var(--fe-absent-ink)',
    },

    fontFamily: {
      sans: ['IBM Plex Sans', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      mono: ['IBM Plex Mono', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
    },

    // Six tailles, nommées par leur rôle. `text-sm`, `text-lg`, `text-2xl`
    // n'existent plus : une taille se choisit par ce qu'elle désigne.
    fontSize: {
      label: ['0.6875rem', { lineHeight: '1', letterSpacing: '0.06em' }],
      meta: ['0.75rem', { lineHeight: '1.35' }],
      body: ['0.8125rem', { lineHeight: '1.45' }],
      lead: ['0.9375rem', { lineHeight: '1.3' }],
      title: ['1.25rem', { lineHeight: '1.25' }],
      figure: ['1.75rem', { lineHeight: '1.1' }],
    },

    borderRadius: {
      none: '0',
      sm: '2px',            // champs, badges, pastilles de légende
      DEFAULT: '4px',       // panneaux, boutons
      full: '9999px',       // réservé aux jauges et compteurs circulaires
    },

    boxShadow: {
      none: 'none',
      overlay: 'var(--fe-shadow-overlay)', // couches réellement flottantes
    },

    extend: {
      // L'échelle d'espacement par défaut de Tailwind est conservée : c'est
      // déjà la trame de 4 px.
      transitionTimingFunction: {
        fe: 'cubic-bezier(0.2, 0, 0.2, 1)',
      },
      transitionDuration: {
        ui: '120ms',
        data: '300ms',
      },
      // Aucune animation décorative. `animate-pulse` reste disponible pour les
      // squelettes de chargement, qui portent bien une information.
    },
  },
  plugins: [],
};
