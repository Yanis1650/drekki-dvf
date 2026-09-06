import { ref } from 'vue';
import { DECISIONS, OBJECTIVES } from '../domain/dossier.js';
import { cleanCriteria } from '../domain/multicriteria.js';

// Stable across Vite module replacement: providers and consumers keep one key.
export const DOSSIERS_KEY = Symbol.for('foncier-express:dossiers');
export const STORAGE_KEY = 'foncier-express:dossiers:v1';
const checkIds = ['regles', 'acces', 'ventes', 'terrain'];
const text = v => typeof v === 'string' ? v : '';
export function cleanDossier(value) {
  if (!value || typeof value.parcelId !== 'string' || !/^[0-9A-Z]{13,14}$/.test(value.parcelId)) return null;
  const checks = Object.fromEntries(checkIds.map(id => {
    const note = text(value.checks?.[id]?.note);
    return [id, { note, done: value.checks?.[id]?.done === true && !!note.trim() }];
  }));
  return { parcelId: value.parcelId, title: text(value.title), objective: Object.hasOwn(OBJECTIVES, value.objective) ? value.objective : 'potentiel',
    decision: Object.hasOwn(DECISIONS, value.decision) ? value.decision : 'qualifier', notes: text(value.notes), checks,
    criteria: cleanCriteria(value.criteria, value.objective), updatedAt: text(value.updatedAt) };
}
export function createDossierStore(storage) {
  const dossiers = ref([]), error = ref('');
  let unreadable = false;
  try {
    const stored = storage?.getItem(STORAGE_KEY);
    const data = stored ? JSON.parse(stored) : [];
    if (!Array.isArray(data)) throw new Error('Invalid storage');
    const clean = data.map(cleanDossier);
    if (clean.some(d => !d)) throw new Error('Unsupported record');
    dossiers.value = clean;
    if (!storage) throw new Error('No storage');
  } catch { unreadable = true; error.value = 'Les dossiers enregistrés ne peuvent pas être lus. Aucun enregistrement existant ne sera remplacé.'; }
  function save(draft) {
    if (unreadable) return false;
    const entry = cleanDossier({ ...draft, updatedAt: new Date().toISOString() });
    if (!entry) { error.value = 'Identifiant de parcelle invalide.'; return false; }
    const next = [entry, ...dossiers.value.filter(d => d.parcelId !== entry.parcelId)];
    try { storage.setItem(STORAGE_KEY, JSON.stringify(next)); }
    catch { error.value = 'Enregistrement impossible dans ce navigateur. Exportez le dossier pour conserver vos notes.'; return false; }
    dossiers.value = next; error.value = ''; return true;
  }
  return { dossiers, error, save, find: id => dossiers.value.find(d => d.parcelId === id) };
}
