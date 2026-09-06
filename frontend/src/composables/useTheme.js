/**
 * Choix du thème.
 *
 * tokens.css définit déjà trois états : le réglage système, et deux choix
 * explicites portés par `data-theme`. Ce module ne fait que poser l'attribut et
 * s'en souvenir. Il ne définit aucune couleur — la charte reste seule à le
 * faire.
 */
import { ref } from 'vue';

const KEY = 'fe-theme';
export const THEMES = [
  { value: 'system', label: 'Système' },
  { value: 'light', label: 'Clair' },
  { value: 'dark', label: 'Sombre' },
];

function read() {
  try {
    const stored = window.localStorage.getItem(KEY);
    return THEMES.some((t) => t.value === stored) ? stored : 'system';
  } catch {
    // Navigation privée ou stockage désactivé : le réglage système fait foi.
    return 'system';
  }
}

const theme = ref(typeof window === 'undefined' ? 'system' : read());

function apply(value) {
  if (typeof document === 'undefined') return;
  if (value === 'system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', value);
}

export function setTheme(value) {
  theme.value = value;
  apply(value);
  try {
    window.localStorage.setItem(KEY, value);
  } catch { /* Le thème reste appliqué pour la session en cours. */ }
}

export function useTheme() {
  apply(theme.value);
  return { theme, setTheme, THEMES };
}
