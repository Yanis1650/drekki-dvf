export const CRITERIA = [
  { id: 'marche', label: 'Prix & marché', question: 'Les ventes comparables et le coût global correspondent-ils à mon projet ?', pro: 2, visite: 3 },
  { id: 'potentiel', label: 'Terrain & potentiel', question: 'La surface, les usages et les possibilités à vérifier correspondent-ils à mon projet ?', pro: 3, visite: 1 },
  { id: 'regles', label: 'Règles & servitudes', question: 'Les documents consultés permettent-ils les usages que j’envisage ?', pro: 3, visite: 2 },
  { id: 'acces', label: 'Accès & quotidien', question: 'L’accès, les déplacements et les services répondent-ils à mes besoins ?', pro: 2, visite: 3 },
  { id: 'risques', label: 'Risques & nuisances', question: 'Les risques et nuisances documentés sont-ils compatibles avec mon projet ?', pro: 3, visite: 3 },
  { id: 'etat', label: 'Bâti & travaux', question: 'L’état du bâti, l’énergie et les travaux nécessaires me conviennent-ils ?', pro: 2, visite: 3 },
];

export function cleanCriteria(input, objective = 'potentiel') {
  return Object.fromEntries(CRITERIA.map(c => {
    const v = input?.[c.id];
    const note = typeof v?.note === 'string' ? v.note : '';
    return [c.id, {
      weight: Number.isInteger(v?.weight) && v.weight >= 0 && v.weight <= 3 ? v.weight : c[objective === 'visite' ? 'visite' : 'pro'],
      rating: note.trim() && Number.isInteger(v?.rating) && v.rating >= 0 && v.rating <= 5 ? v.rating : null,
      note,
      blocked: v?.blocked === true && !!note.trim(),
    }];
  }));
}

// Subjective fit, explicitly separate from measured data and source reliability.
// Missing ratings give a range (0..5), never an implicit favourable or zero rating.
export function evaluateCriteria(input, objective) {
  const values = cleanCriteria(input, objective);
  const enabled = Object.values(values).filter(v => v.weight > 0);
  const rated = enabled.filter(v => v.rating !== null);
  const totalWeight = enabled.reduce((n, v) => n + v.weight, 0);
  const ratedWeight = rated.reduce((n, v) => n + v.weight, 0);
  const points = rated.reduce((n, v) => n + v.rating / 5 * v.weight, 0);
  const percent = n => totalWeight ? Math.round(n / totalWeight * 100) : null;
  return {
    count: rated.length, total: enabled.length, coverage: percent(ratedWeight),
    low: rated.length ? percent(points) : null,
    high: rated.length ? percent(points + totalWeight - ratedWeight) : null,
    score: rated.length && rated.length === enabled.length ? percent(points) : null,
    blockers: CRITERIA.filter(c => values[c.id].blocked).map(c => c.label),
  };
}

export function criteriaText(input, objective) {
  const values = cleanCriteria(input, objective), result = evaluateCriteria(values, objective);
  return ['ANALYSE MULTICRITÈRE PERSONNELLE', 'Notes saisies par l’utilisateur, pas un score automatique du territoire.',
    `Couverture : ${result.count}/${result.total} critères actifs. Score complet : ${result.score ?? 'non calculable'}/100.`,
    `Fourchette selon les critères manquants : ${result.low ?? 'non calculable'}–${result.high ?? 'non calculable'}/100.`,
    `Points bloquants signalés : ${result.blockers.join(', ') || 'aucun signalé (ne signifie pas absence de contrainte)'}`,
    ...CRITERIA.map(c => `${c.label} : ${values[c.id].rating ?? 'non renseigné'}/5 · poids ${values[c.id].weight} · ${values[c.id].blocked ? 'BLOQUANT' : ''}\nObservation / référence : ${values[c.id].note || 'non renseignée'}`),
  ].join('\n');
}
