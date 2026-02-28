/**
 * Composable for MapLibre map initialization and data fetching.
 */
import { onMounted, onUnmounted, ref, watch } from 'vue';
import maplibregl from 'maplibre-gl';
import client from '../api/client';
import { mapColorSchemes } from './mapColorSchemes';
import { addParcelleLayers, addTransactionLayers, setupMapEvents } from './mapLayerHelpers';

const CARTO_TILES = [
  'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
  'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
  'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'
];

export function useMapContainer(props, emit) {
  const mapContainer = ref(null);
  const isLoading = ref(true);
  let map = null;

  function createMapStyle() {
    return {
      version: 8,
      sources: {
        carto: {
          type: 'raster',
          tiles: CARTO_TILES,
          tileSize: 256,
          attribution: '© CARTO © OSM',
          maxzoom: 20
        }
      },
      layers: [{ id: 'carto-base', type: 'raster', source: 'carto' }]
    };
  }

  async function fetchTransactions() {
    if (!map?.getSource('transactions')) return;
    const b = map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    try {
      const res = await client.get(`/land/geojson?bbox=${bbox}`);
      map.getSource('transactions').setData(res.data);
    } catch (err) {
      console.error('Transactions fetch error:', err);
    }
  }

  async function fetchParcelles() {
    if (!map?.getSource('parcelles')) return;
    if (map.getZoom() < 13) {
      map.getSource('parcelles').setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const b = map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    const filterParam = props.activeFilter ? `&filter=${props.activeFilter}` : '';
    try {
      const res = await client.get(`/land/parcelles?bbox=${bbox}${filterParam}`);
      map.getSource('parcelles').setData(res.data);
    } catch (err) {
      console.error('Parcelles fetch error:', err);
    }
  }

  function applyParcelHighlights() {
    if (!map?.getLayer('parcelles-fill')) return;
    const scheme = mapColorSchemes[props.mode] || mapColorSchemes.prix;
    const sel = props.selectedParcel;
    const rel = props.relatedParcels || [];
    if (!sel && rel.length === 0) {
      map.setPaintProperty('parcelles-fill', 'fill-color', scheme.parcelles);
      map.setPaintProperty('parcelles-fill', 'fill-opacity', scheme.opacity || 0.25);
      map.setPaintProperty('parcelles-line', 'line-width', 1.5);
      map.setPaintProperty('parcelles-line', 'line-color', '#475569');
      return;
    }
    const eqSel = ['==', ['get', 'id_parcelle'], sel];
    const inRel = ['in', ['get', 'id_parcelle'], ['literal', rel]];
    let fillColor, lineWidth, lineColor;
    if (rel.length > 0 && sel) {
      fillColor = ['case', eqSel, 'rgba(239, 68, 68, 0.5)', inRel, 'rgba(251, 146, 60, 0.5)', scheme.parcelles];
      lineWidth = ['case', eqSel, 5, inRel, 3, 1.5];
      lineColor = ['case', eqSel, '#dc2626', inRel, '#ea580c', '#475569'];
    } else if (sel) {
      fillColor = ['case', eqSel, 'rgba(239, 68, 68, 0.5)', scheme.parcelles];
      lineWidth = ['case', eqSel, 5, 1.5];
      lineColor = ['case', eqSel, '#dc2626', '#475569'];
    } else {
      fillColor = ['case', inRel, 'rgba(251, 146, 60, 0.5)', scheme.parcelles];
      lineWidth = ['case', inRel, 3, 1.5];
      lineColor = ['case', inRel, '#ea580c', '#475569'];
    }
    map.setPaintProperty('parcelles-fill', 'fill-color', fillColor);
    map.setPaintProperty('parcelles-fill', 'fill-opacity', 0.5);
    map.setPaintProperty('parcelles-line', 'line-width', lineWidth);
    map.setPaintProperty('parcelles-line', 'line-color', lineColor);
  }

  onMounted(() => {
    if (!mapContainer.value) return;
    map = new maplibregl.Map({
      container: mapContainer.value,
      style: createMapStyle(),
      center: props.center,
      zoom: 13,
      pitch: 45,
      bearing: -17.6,
      antialias: true
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    map.on('load', () => {
      isLoading.value = false;
      addTransactionLayers(map, props.transactions, props.mode);
      addParcelleLayers(map, props.mode);
      setupMapEvents(map, emit, fetchTransactions, fetchParcelles);
      fetchTransactions();
      if (map.getZoom() >= 13) fetchParcelles();
      emit('map-loaded');
    });
  });

  watch(() => props.center, (newCenter) => {
    if (map) map.flyTo({ center: newCenter, essential: true, zoom: 16, pitch: 50, duration: 2000 });
  });
  watch(() => props.activeFilter, () => {
    if (map?.getSource('parcelles') && map.getZoom() >= 13) fetchParcelles();
  });
  watch(() => props.mode, (newMode) => {
    if (!map) return;
    const scheme = mapColorSchemes[newMode] || mapColorSchemes.prix;
    if (map.getLayer('parcelles-fill')) {
      map.setPaintProperty('parcelles-fill', 'fill-color', scheme.parcelles);
      map.setPaintProperty('parcelles-fill', 'fill-opacity', scheme.opacity || 0.25);
    }
    if (map.getLayer('unclustered-point')) {
      map.setPaintProperty('unclustered-point', 'circle-color', scheme.points);
    }
  });
  watch(() => props.selectedParcel, applyParcelHighlights);
  watch(() => props.relatedParcels, applyParcelHighlights, { deep: true });
  watch(() => props.transactions, (newData) => {
    if (map?.getSource('transactions')) map.getSource('transactions').setData(newData);
  });

  onUnmounted(() => {
    if (map) map.remove();
  });

  return { mapContainer, isLoading };
}
