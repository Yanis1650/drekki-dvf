/**
 * Mise en place des couches MapLibre, alignée sur la charte.
 *
 * Le changement principal tient en une phrase : à partir du zoom 16, une
 * mutation n'est plus une pastille colorée mais son prix écrit. Une pastille
 * impose un aller-retour permanent avec la légende et ne livre qu'un ordre de
 * grandeur ; le chiffre écrit donne la valeur exacte, et le semis donne quand
 * même la forme d'ensemble.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md §6
 */
import { createHatchImage, token } from '../styles/tokens';
import {
  HATCH_ABSENT,
  PLU_ZONES,
  absenceFilter,
  absenceProperty,
  fillOpacity,
  parcelFill,
  pluHatchId,
  pointFill,
} from './mapColorSchemes';

/** Zoom à partir duquel la valeur s'écrit au lieu de se coder en couleur. */
export const ZOOM_VALEURS = 16;

/** Police du semis. Doit exister dans le jeu de glyphes déclaré par le style. */
const FONT = ['Open Sans Regular'];

/**
 * Enregistre les motifs de hachure. À rappeler après un changement de thème :
 * les traits sont dessinés dans l'encre courante.
 */
export function registerHatchImages(map) {
  const add = (id, options) => {
    if (map.hasImage(id)) map.removeImage(id);
    map.addImage(id, createHatchImage(options));
  };

  add(HATCH_ABSENT, { angle: 45, color: token('--fe-absent-ink') });
  for (const zone of PLU_ZONES) {
    add(pluHatchId(zone.code), { angle: zone.hachure, color: token('--fe-ink'), lineWidth: 1 });
  }
}

export function addTransactionLayers(map, transactions, mode) {
  map.addSource('transactions', {
    type: 'geojson',
    data: transactions,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 50,
  });

  // Les agrégats ne portent pas de valeur : ils sont de l'interface, donc froids.
  map.addLayer({
    id: 'clusters',
    type: 'circle',
    source: 'transactions',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': token('--fe-accent'),
      'circle-radius': ['step', ['get', 'point_count'], 16, 50, 21, 150, 27],
      'circle-stroke-width': 1,
      'circle-stroke-color': token('--fe-surface'),
    },
  });

  map.addLayer({
    id: 'cluster-count',
    type: 'symbol',
    source: 'transactions',
    filter: ['has', 'point_count'],
    layout: {
      'text-field': '{point_count_abbreviated}',
      'text-font': FONT,
      'text-size': 12,
    },
    paint: { 'text-color': token('--fe-accent-ink') },
  });

  // En dessous du seuil d'écriture, la mutation reste une pastille de la rampe.
  map.addLayer({
    id: 'unclustered-point',
    type: 'circle',
    source: 'transactions',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-color': pointFill(mode),
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 15, 6],
      'circle-stroke-width': 0.75,
      'circle-stroke-color': token('--fe-ink'),
      'circle-opacity': ['interpolate', ['linear'], ['zoom'], ZOOM_VALEURS - 0.5, 1, ZOOM_VALEURS, 0],
      'circle-stroke-opacity': ['interpolate', ['linear'], ['zoom'], ZOOM_VALEURS - 0.5, 0.7, ZOOM_VALEURS, 0],
    },
  });

  // Le semis. Halo de la couleur du fond pour rester lisible au-dessus de
  // n'importe quel palier de la rampe — c'est la technique cartographique
  // usuelle pour poser un chiffre sur une plage colorée.
  map.addLayer({
    id: 'valeurs',
    type: 'symbol',
    source: 'transactions',
    filter: ['!', ['has', 'point_count']],
    minzoom: ZOOM_VALEURS,
    layout: {
      'text-field': [
        'concat',
        ['number-format', ['get', 'prix_m2'], { locale: 'fr-FR', 'max-fraction-digits': 0 }],
        ' €',
      ],
      'text-font': FONT,
      'text-size': 12,
      'text-allow-overlap': false,
      'text-padding': 4,
    },
    paint: {
      'text-color': token('--fe-ink'),
      'text-halo-color': token('--fe-surface'),
      'text-halo-width': 1.5,
    },
  });
}

export function addParcelleLayers(map, mode) {
  map.addSource('parcelles', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  });

  map.addLayer({
    id: 'parcelles-fill',
    type: 'fill',
    source: 'parcelles',
    minzoom: 13,
    paint: { 'fill-color': parcelFill(mode), 'fill-opacity': fillOpacity(mode) },
  });

  // Absence de donnée : hachurée, jamais grise. Un gris neutre se lirait comme
  // une valeur basse ; la hachure ne peut être confondue avec aucune mesure.
  map.addLayer({
    id: 'parcelles-absence',
    type: 'fill',
    source: 'parcelles',
    minzoom: 13,
    filter: absenceFilter(absenceProperty(mode)),
    paint: { 'fill-pattern': HATCH_ABSENT, 'fill-opacity': 0.9 },
  });

  // Second support des zones PLU : l'orientation de la hachure. La carte reste
  // lisible en niveaux de gris et à l'impression.
  const pluPattern = ['match', ['get', 'zone_plu']];
  PLU_ZONES.forEach((z) => pluPattern.push(z.code, pluHatchId(z.code)));
  pluPattern.push(pluHatchId(PLU_ZONES[0].code));

  map.addLayer({
    id: 'parcelles-plu-hachure',
    type: 'fill',
    source: 'parcelles',
    minzoom: 13,
    filter: ['has', 'zone_plu'],
    layout: { visibility: mode === 'urbanisme' ? 'visible' : 'none' },
    paint: { 'fill-pattern': pluPattern, 'fill-opacity': 0.55 },
  });

  map.addLayer({
    id: 'parcelles-line',
    type: 'line',
    source: 'parcelles',
    minzoom: 13,
    paint: { 'line-color': token('--fe-ink'), 'line-width': 0.5, 'line-opacity': 0.45 },
  });

  // Le froid ne dit qu'une chose : ceci est sélectionné ou survolé.
  map.addLayer({
    id: 'parcelles-highlight',
    type: 'line',
    source: 'parcelles',
    minzoom: 13,
    paint: {
      'line-color': token('--fe-accent'),
      'line-width': 2,
      'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 1, 0],
    },
  });
}

export function setupMapEvents(map, emit, fetchTransactions, fetchParcelles) {
  map.on('click', 'unclustered-point', (e) => emit('transaction-click', e.features[0]));
  map.on('click', 'valeurs', (e) => emit('transaction-click', e.features[0]));
  map.on('click', 'parcelles-fill', (e) => {
    if (e.features.length > 0) emit('parcel-click', e.features[0]);
  });

  let hoveredParcelId = null;
  map.on('mousemove', 'parcelles-fill', (e) => {
    if (e.features.length === 0) return;
    const fid = e.features[0].id;
    if (fid == null) return;
    if (hoveredParcelId != null && hoveredParcelId !== fid) {
      try { map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: false }); } catch (_) {}
    }
    hoveredParcelId = fid;
    try { map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: true }); } catch (_) {}
  });
  map.on('mouseleave', 'parcelles-fill', () => {
    if (hoveredParcelId != null) {
      try { map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: false }); } catch (_) {}
    }
    hoveredParcelId = null;
  });

  for (const layer of ['unclustered-point', 'valeurs', 'parcelles-fill', 'clusters']) {
    map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
  }

  map.on('click', 'clusters', (e) => {
    const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] });
    if (features.length === 0) return;
    const clusterId = features[0].properties.cluster_id;
    map.getSource('transactions').getClusterExpansionZoom(clusterId, (err, zoom) => {
      if (err) return;
      map.easeTo({ center: features[0].geometry.coordinates, zoom });
    });
  });

  map.on('moveend', () => {
    fetchTransactions();
    fetchParcelles();
  });
}
