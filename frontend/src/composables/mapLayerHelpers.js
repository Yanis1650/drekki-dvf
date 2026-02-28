/**
 * MapLibre layer setup helpers for useMapContainer.
 */
import { mapColorSchemes } from './mapColorSchemes';

export function addTransactionLayers(map, transactions, mode) {
  const scheme = mapColorSchemes[mode] || mapColorSchemes.prix;
  map.addSource('transactions', {
    type: 'geojson',
    data: transactions,
    cluster: true,
    clusterMaxZoom: 14,
    clusterRadius: 50
  });
  map.addLayer({
    id: 'clusters',
    type: 'circle',
    source: 'transactions',
    filter: ['has', 'point_count'],
    paint: {
      'circle-color': ['step', ['get', 'point_count'], '#527f8c', 50, '#3f6775', 150, '#c63806'],
      'circle-radius': ['step', ['get', 'point_count'], 22, 50, 28, 150, 36],
      'circle-stroke-width': 3,
      'circle-stroke-color': 'rgba(255,255,255,0.9)'
    }
  });
  map.addLayer({
    id: 'cluster-count',
    type: 'symbol',
    source: 'transactions',
    filter: ['has', 'point_count'],
    layout: { 'text-field': '{point_count_abbreviated}', 'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'], 'text-size': 12 },
    paint: { 'text-color': '#ffffff' }
  });
  map.addLayer({
    id: 'unclustered-point',
    type: 'circle',
    source: 'transactions',
    filter: ['!', ['has', 'point_count']],
    paint: {
      'circle-color': scheme.points,
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 5, 15, 10, 18, 14],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#ffffff',
      'circle-opacity': 0.9
    }
  });
}

export function addParcelleLayers(map, mode) {
  const scheme = mapColorSchemes[mode] || mapColorSchemes.prix;
  map.addSource('parcelles', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] }
  });
  map.addLayer({
    id: 'parcelles-fill',
    type: 'fill',
    source: 'parcelles',
    minzoom: 13,
    paint: { 'fill-color': scheme.parcelles, 'fill-opacity': scheme.opacity || 0.25 }
  });
  map.addLayer({
    id: 'parcelles-line',
    type: 'line',
    source: 'parcelles',
    minzoom: 13,
    paint: { 'line-color': '#475569', 'line-width': 1.5, 'line-opacity': 0.6 }
  });
  map.addLayer({
    id: 'parcelles-highlight',
    type: 'line',
    source: 'parcelles',
    minzoom: 13,
    paint: {
      'line-color': '#6366f1',
      'line-width': 3,
      'line-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 1, 0]
    }
  });
}

export function setupMapEvents(map, emit, fetchTransactions, fetchParcelles) {
  map.on('click', 'unclustered-point', (e) => emit('transaction-click', e.features[0]));
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
  map.on('mouseenter', 'unclustered-point', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'unclustered-point', () => { map.getCanvas().style.cursor = ''; });
  map.on('mouseenter', 'parcelles-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'parcelles-fill', () => { map.getCanvas().style.cursor = ''; });
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
