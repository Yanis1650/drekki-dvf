import { numberOrNull, money } from './market.js';
import { criteriaText } from './multicriteria.js';

export const OBJECTIVES = { potentiel: 'Étudier le potentiel', visite: 'Préparer une visite' };
export const DECISIONS = { qualifier: 'À qualifier', approfondir: 'À approfondir', visite: 'Visite prévue', ecarter: 'Écarté' };
const surface = v => `${v.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} m²`;

// Screening prompts, not a feasibility engine. Every automatic statement names
// its input; unknown regulatory/access data never become favourable findings.
export function buildDossier({ fiche, densification, transactions = [], historyAvailable = false, objective = 'potentiel' }) {
  const facts = [];
  const unknowns = [];
  const prices = transactions.filter(t => !t.is_outlier).map(t => numberOrNull(t.price_m2)).filter(p => p != null && p > 0);
  if (historyAvailable) {
    facts.push({ label: 'Historique de ventes', value: `${transactions.length} vente(s) renvoyée(s)`, source: 'DVF · historique de cette parcelle', kind: 'Donnée renvoyée' });
    if (prices.length) facts.push({ label: 'Prix moyen historique / m²', value: money(prices.reduce((a, b) => a + b, 0) / prices.length), source: `DVF · ${prices.length} prix exploitables, hors aberrantes · toutes dates`, kind: 'Calcul sur les ventes' });
  } else unknowns.push('L’historique DVF n’a pas pu être consulté.');
  if (!prices.length) unknowns.push('Aucun prix/m² exploitable dans l’historique disponible.');
  const area = numberOrNull(fiche?.surface_parcelle_m2 ?? densification?.surface_parcelle_m2);
  if (area != null && area > 0) facts.push({ label: 'Surface parcellaire renvoyée', value: surface(area), source: 'Fiche ou données de densification API · millésime non fourni', kind: 'Donnée renvoyée' });
  if (typeof fiche?.dpe_energie === 'string' && /^[A-G]$/i.test(fiche.dpe_energie.trim())) facts.push({ label: 'Classe énergie renvoyée', value: fiche.dpe_energie.trim().toUpperCase(), source: 'Fiche API · valeur agrégée du bâti, diagnostic et date à vérifier', kind: 'Donnée renvoyée' });
  const remaining = numberOrNull(densification?.surface_constructible_restante);
  if (remaining != null && remaining >= 0) {
    facts.push({ label: 'Surface restante estimée', value: surface(remaining), source: 'Modèle de densification Foncier Express · date de calcul non fournie', kind: 'Modélisé' });
  } else unknowns.push('Le potentiel de densification n’est pas renseigné.');
  if (fiche?.libelle_zone) facts.push({ label: 'Zonage renvoyé', value: String(fiche.libelle_zone), source: `Fiche API · date d’approbation renvoyée : ${fiche.plu_datappro || 'non fournie'}`, kind: 'À confronter au document en vigueur' });
  else unknowns.push('Le zonage n’est pas renseigné dans la fiche.');
  unknowns.push('L’accès, les servitudes et l’ensemble des règles applicables ne sont pas vérifiés par ce dossier.');
  unknowns.push('Les risques, les nuisances et la proximité des services ne sont pas renseignés par les sources consultées ici.');
  const checks = [
    { id: 'regles', title: 'Vérifier les règles applicables', why: fiche?.libelle_zone ? 'Un libellé de zone ne décrit pas toutes les règles et prescriptions.' : 'Le zonage manque : le potentiel calculé ne permet pas de conclure.', action: 'Relever les références du règlement et des prescriptions applicables ; faire préciser les points ambigus au service urbanisme.', source: 'Zonage de la fiche API, ou absence de zonage' },
    { id: 'acces', title: 'Éclaircir l’accès et les limites', why: 'Ces éléments ne sont pas établis par les données reçues.', action: objective === 'visite' ? 'Pendant la visite, demander comment se fait l’accès et quels documents décrivent les limites ou les servitudes.' : 'Rassembler les documents décrivant accès, limites et servitudes avant de retenir une hypothèse de division.', source: 'Information non couverte par les endpoints consultés' },
    { id: 'ventes', title: 'Comprendre les ventes retenues', why: prices.length < 5 ? 'Moins de cinq prix exploitables : la référence est fragile.' : 'Une moyenne historique ne constitue pas une estimation actuelle du bien.', action: 'Dans l’onglet Ventes, vérifier dates, surfaces et périmètre vendu ; noter les ventes réellement pertinentes.', source: 'Historique DVF de la parcelle' },
    { id: 'terrain', title: objective === 'visite' ? 'Préparer les questions sur place' : 'Confronter le potentiel au terrain', why: remaining == null ? 'Le potentiel manque et les caractéristiques du terrain restent à examiner.' : 'La surface modélisée ne prouve pas qu’un projet est réalisable.', action: objective === 'visite' ? 'Noter les usages actuels, les travaux envisagés et les documents à demander au vendeur.' : 'Documenter les usages actuels et les contraintes observées ; faire examiner le scénario par le professionnel compétent.', source: 'Modèle de densification et observations à recueillir' },
  ];
  if (objective === 'visite') checks.sort((a, b) => ['terrain', 'ventes', 'acces', 'regles'].indexOf(a.id) - ['terrain', 'ventes', 'acces', 'regles'].indexOf(b.id));
  return { facts, unknowns, checks, summary: remaining > 0 ? 'Un potentiel est signalé par le modèle. Les vérifications ci-dessous restent nécessaires.' : 'Les données disponibles ne permettent pas de conclure à un potentiel de transformation.' };
}

export function dossierText({ parcelId, objective, decision, notes, checks, criteria, analysis, savedAt }) {
  return [
    `Foncier Express — dossier ${parcelId}`, `Objectif : ${OBJECTIVES[objective]}`, `Décision personnelle : ${DECISIONS[decision]}`,
    `Export du ${savedAt}`, 'Données et observations à vérifier. Ce dossier ne valide ni un prix ni une faisabilité.',
    '\nREPÈRES', ...analysis.facts.map(f => `${f.label} : ${f.value}\n${f.kind} · ${f.source}`),
    '\nINCONNUES', ...analysis.unknowns,
    '\n' + criteriaText(criteria, objective),
    '\nVÉRIFICATIONS', ...analysis.checks.map(c => `${c.title} — ${checks[c.id]?.done ? 'Renseigné par l’utilisateur' : 'À vérifier'}\n${c.action}\nObservation / référence : ${checks[c.id]?.note || 'Non renseignée'}`),
    '\nNOTES PERSONNELLES', notes || 'Non renseignées',
  ].join('\n');
}
