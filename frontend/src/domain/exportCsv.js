/**
 * Export de l'échantillon chargé.
 *
 * L'export ne recalcule rien et n'invente rien : il rend les mêmes mutations
 * que la carte et Marché, avec les mêmes exclusions signalées. Une valeur
 * absente sort vide — jamais zéro — et la colonne `is_outlier` accompagne le
 * prix pour que le fichier porte la même réserve que l'écran.
 */
const COLUMNS = [
  ['id_mutation', (p) => p.id_mutation],
  ['date_mutation', (p) => p.date_mutation],
  ['type_local', (p) => p.type_local],
  ['valeur_fonciere_eur', (p) => p.valeur_fonciere],
  ['prix_m2_eur', (p) => p.prix_m2],
  ['exclu_des_prix_agreges', (p) => (p.is_outlier ? 'oui' : 'non')],
  ['surface_reelle_bati_m2', (p) => p.surface_reelle_bati],
  ['surface_terrain_m2', (p) => p.surface_terrain],
  ['parcelles', (p) => (p.parcelles ?? []).join(' ')],
  ['longitude', (p, f) => f.geometry?.coordinates?.[0]],
  ['latitude', (p, f) => f.geometry?.coordinates?.[1]],
];

const cell = (value) => {
  if (value == null || value === '') return '';
  const text = String(value);
  return /[";\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

/** Sérialise l'échantillon en CSV point-virgule, lisible par un tableur français. */
export function studyToCsv(collection) {
  const rows = [COLUMNS.map(([name]) => name).join(';')];
  for (const feature of collection?.features ?? []) {
    rows.push(COLUMNS.map(([, get]) => cell(get(feature.properties ?? {}, feature))).join(';'));
  }
  return rows.join('\r\n');
}

/** Nom de fichier traçable : périmètre, rayon, date d'export. */
export function csvFilename(label, radius) {
  const place = (label || 'perimetre')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
    .slice(0, 40);
  return `foncier-express_${place || 'perimetre'}_${radius}m_${new Date().toISOString().slice(0, 10)}.csv`;
}

/** Déclenche le téléchargement. Isolé ici pour que la sérialisation reste testable. */
export function downloadCsv(collection, label, radius) {
  // BOM : sans lui, un tableur lit le fichier en ANSI et casse les accents.
  const blob = new Blob([String.fromCharCode(0xfeff) + studyToCsv(collection)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = csvFilename(label, radius);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
