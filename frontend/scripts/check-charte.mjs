#!/usr/bin/env node
/**
 * Vérificateur de charte graphique.
 *
 * Tailwind n'échoue pas sur une classe inconnue : il l'ignore, silencieusement.
 * Un `text-slate-500` oublié ne casse donc rien — il produit juste du texte sans
 * couleur, ce qui passe inaperçu jusqu'au jour où la charte a fondu. Ce script
 * est ce qui échoue à sa place.
 *
 *   npm run check:charte
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md
 */

import { readFileSync } from 'node:fs';
import { readdir } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const SRC = join(ROOT, 'src');

/** Palettes Tailwind par défaut, plus les quatre palettes abandonnées. */
const BANNED_PALETTES = [
  'slate', 'gray', 'zinc', 'neutral', 'stone',
  'red', 'orange', 'amber', 'yellow', 'lime', 'green', 'emerald', 'teal',
  'cyan', 'sky', 'blue', 'indigo', 'violet', 'purple', 'fuchsia', 'pink', 'rose',
  'sage', 'terracotta', 'cream', 'rouge',
].join('|');

const UTILITY_PREFIXES =
  'bg|text|border|from|to|via|ring|ring-offset|fill|stroke|divide|placeholder|decoration|outline|caret|accent|shadow';

const RULES = [
  {
    id: 'palette-hors-charte',
    why: 'une seule palette gouverne — voir tokens.css',
    re: new RegExp(`\\b(?:${UTILITY_PREFIXES})-(?:${BANNED_PALETTES})-\\d{2,3}\\b`, 'g'),
  },
  {
    id: 'blanc-noir-en-dur',
    why: 'utiliser surface / ink, qui suivent le thème',
    re: new RegExp(`\\b(?:${UTILITY_PREFIXES})-(?:white|black)(?:\\/\\d{1,3})?\\b`, 'g'),
  },
  {
    id: 'hexadecimal-en-dur',
    why: 'toute couleur vient d\'un jeton --fe-*',
    re: /#[0-9a-fA-F]{3,8}\b/g,
  },
  {
    id: 'taille-de-texte-hors-charte',
    why: 'six tailles nommées : label, meta, body, lead, title, figure',
    re: /\btext-(?:xs|sm|base|lg|xl|[2-9]xl)\b/g,
  },
  {
    id: 'rayon-hors-charte',
    why: 'rounded-sm (2px), rounded (4px), rounded-full pour les jauges',
    re: /\brounded-(?:md|lg|xl|[2-9]xl)\b/g,
  },
  {
    id: 'ombre-decorative',
    why: 'une seule ombre, shadow-overlay, pour les couches flottantes',
    re: /\bshadow-(?!overlay\b|none\b)[a-z0-9[\]()_,.%/-]+/g,
  },
  {
    id: 'degrade',
    why: 'aucun dégradé décoratif dans la charte',
    re: /\bbg-gradient-to-[a-z]{1,2}\b/g,
  },
  {
    id: 'verre-depoli',
    why: 'coût de rendu et contraste non déterministe',
    re: /\bbackdrop-(?:blur|saturate|brightness|filter)[a-z0-9[\]()_.%/-]*/g,
  },
  {
    id: 'animation-decorative',
    why: 'rien ne bouge sans porter d\'information',
    re: /\banimate-(?:shimmer|float|pulse-slow|bounce|spin-slow)\b/g,
  },
];

/** Fichiers exemptés, avec la raison. */
const EXEMPT = new Map([
  ['src/styles/tokens.js', 'valeurs de repli des jetons, pour les contextes sans DOM'],
  ['src/styles/tokens.css', 'fichier de jetons : c\'est là que vivent les hexadécimaux'],
]);

async function collect(dir, out = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) await collect(full, out);
    else if (/\.(vue|js|ts|css|html)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const files = await collect(SRC);
const findings = [];

for (const file of files) {
  const rel = relative(ROOT, file).replace(/\\/g, '/');
  if (EXEMPT.has(rel)) continue;

  const lines = readFileSync(file, 'utf8').split(/\r?\n/);
  lines.forEach((line, i) => {
    // Une ligne peut se soustraire à une règle en la nommant explicitement.
    if (line.includes('charte-ignore')) return;
    for (const rule of RULES) {
      rule.re.lastIndex = 0;
      for (const m of line.matchAll(rule.re)) {
        findings.push({ file: rel, line: i + 1, rule: rule.id, why: rule.why, match: m[0] });
      }
    }
  });
}

if (findings.length === 0) {
  console.log('Charte respectée — aucun écart détecté.');
  process.exit(0);
}

const byRule = new Map();
for (const f of findings) {
  if (!byRule.has(f.rule)) byRule.set(f.rule, []);
  byRule.get(f.rule).push(f);
}

console.error(`\n${findings.length} écart(s) à la charte graphique.\n`);
for (const [rule, items] of [...byRule].sort((a, b) => b[1].length - a[1].length)) {
  console.error(`  ${rule} — ${items[0].why}  (${items.length})`);
  for (const it of items.slice(0, 12)) {
    console.error(`    ${it.file}:${it.line}  ${it.match}`);
  }
  if (items.length > 12) console.error(`    … et ${items.length - 12} autre(s)`);
  console.error('');
}
console.error('Référence : docs/CHARTE_GRAPHIQUE.md');
console.error('Pour une exception justifiée, ajouter le commentaire charte-ignore sur la ligne.\n');
process.exit(1);
