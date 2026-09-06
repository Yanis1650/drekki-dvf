/**
 * Initialisation de la carte MapLibre et récupération des données.
 *
 * Deux partis pris de la charte s'appliquent ici :
 *
 *  - Le fond de carte ne porte aucune couleur saturée. Les tuiles IGN sont
 *    désaturées à l'affichage, pour que la donnée soit la seule chose colorée
 *    à l'écran.
 *
 *  - La vue est à plat. L'inclinaison de 45° d'origine faisait joli mais
 *    déformait les parcelles, c'est-à-dire précisément ce que l'utilisateur
 *    vient lire.
 *
 * Référence : docs/CHARTE_GRAPHIQUE.md
 */
import { onMounted, onUnmounted, ref, watch } from 'vue';
import maplibregl from 'maplibre-gl';
import { studyBoundary } from '../domain/studyGeometry.js';
import client from '../api/client';
import { token } from '../styles/tokens';
import {
  absenceFilter,
  absenceProperty,
  fillOpacity,
  parcelFill,
  pointFill,
} from './mapColorSchemes';
import {
  addParcelleLayers,
  addTransactionLayers,
  registerHatchImages,
  setupMapEvents,
} from './mapLayerHelpers';

// Fond de carte IGN (Géoplateforme) : libre, sans clé d'API, et servi par le
// même hôte que le WFS d'urbanisme déjà utilisé par le pipeline.
//
// Remplace les tuiles CARTO `basemaps.cartocdn.com`, qui exigent désormais une
// clé : elles continuent de se charger, mais estampillées « API KEY REQUIRED »
// sur toute la carte.
const IGN_TILES = [
  'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0' +
    '&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM' +
    '&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}'
];

// Jeu de glyphes nécessaire aux couches de texte — le semis de valeurs et le
// compte des agrégats. Le style d'origine n'en déclarait aucun, ce qui rendait
// déjà le compte des agrégats muet.
const GLYPHS = 'https://data.geopf.fr/annexes/ressources/vectorTiles/fonts/{fontstack}/{range}.pbf';

export function useMapContainer(props, emit) {
  const mapContainer = ref(null);
  const isLoading = ref(true);
  let map = null;
  let resizeObserver;
  let parcelRequest = 0;
  let parcelController;

  function createMapStyle() {
    return {
      version: 8,
      glyphs: GLYPHS,
      sources: {
        ign: {
          type: 'raster',
          tiles: IGN_TILES,
          tileSize: 256,
          attribution: '© IGN — Géoplateforme',
          maxzoom: 19
        }
      },
      layers: [{
        id: 'ign-base',
        type: 'raster',
        source: 'ign',
        paint: {
          // Le fond recule pour que la donnée passe devant.
          'raster-saturation': -0.9,
          'raster-contrast': -0.15,
          'raster-opacity': 0.85
        }
      }]
    };
  }

  async function fetchParcelles() {
    if (!map?.getSource('parcelles')) return;
    const request = ++parcelRequest;
    parcelController?.abort();
    parcelController = new AbortController();
    if (map.getZoom() < 13) {
      map.getSource('parcelles').setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const b = map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    const filterParam = props.activeFilter ? `&filter=${props.activeFilter}` : '';
    try {
      const res = await client.get(`/land/parcelles?bbox=${bbox}${filterParam}`, { signal: parcelController.signal });
      if (request !== parcelRequest || !map) return;
      map.getSource('parcelles').setData(res.data);
      emit('context-error', '');
    } catch (err) {
      if (request !== parcelRequest || !map) return;
      map.getSource('parcelles').setData({ type: 'FeatureCollection', features: [] });
      emit('context-error', 'Cadastre et données parcellaires NON RELEVÉS pour cette vue.');
    }
  }

  /**
   * Sélection et parcelles apparentées.
   *
   * Elles se signalent par le trait, pas par un remplissage de couleur : le
   * remplissage porte déjà la donnée, et le rouge d'origine annonçait un
   * problème là où il n'y avait qu'une sélection.
   */
  function applyParcelHighlights() {
    if (!map?.getLayer('parcelles-fill')) return;
    const sel = props.selectedParcel;
    const rel = props.relatedParcels || [];
    const ink = token('--fe-ink');
    const accent = token('--fe-accent');

    if (!sel && rel.length === 0) {
      map.setPaintProperty('parcelles-line', 'line-width', 0.5);
      map.setPaintProperty('parcelles-line', 'line-color', ink);
      map.setPaintProperty('parcelles-line', 'line-opacity', 0.45);
      return;
    }

    const eqSel = ['==', ['get', 'id_parcelle'], sel];
    const inRel = ['in', ['get', 'id_parcelle'], ['literal', rel]];

    map.setPaintProperty('parcelles-line', 'line-color',
      ['case', eqSel, accent, inRel, accent, ink]);
    map.setPaintProperty('parcelles-line', 'line-width',
      ['case', eqSel, 2.5, inRel, 1.5, 0.5]);
    map.setPaintProperty('parcelles-line', 'line-opacity',
      ['case', eqSel, 1, inRel, 0.8, 0.45]);
  }

  /** Applique un mode de carte à toutes les couches concernées. */
  function applyMode(mode) {
    if (!map) return;
    if (map.getLayer('parcelles-fill')) {
      map.setPaintProperty('parcelles-fill', 'fill-color', parcelFill(mode));
      map.setPaintProperty('parcelles-fill', 'fill-opacity', fillOpacity(mode));
    }
    if (map.getLayer('parcelles-absence')) {
      map.setFilter('parcelles-absence', absenceFilter(absenceProperty(mode)));
    }
    if (map.getLayer('parcelles-plu-hachure')) {
      map.setLayoutProperty('parcelles-plu-hachure', 'visibility',
        mode === 'urbanisme' ? 'visible' : 'none');
    }
    if (map.getLayer('unclustered-point')) {
      map.setPaintProperty('unclustered-point', 'circle-color', pointFill('prix'));
    }
  }

  onMounted(() => {
    if (!mapContainer.value) return;
    map = new maplibregl.Map({
      container: mapContainer.value,
      style: createMapStyle(),
      center: props.center,
      zoom: 14,
      pitch: 0,
      bearing: 0,
      antialias: true
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    resizeObserver = new ResizeObserver(() => map?.resize());
    resizeObserver.observe(mapContainer.value);
    map.on('load', () => {
      isLoading.value = false;
      registerHatchImages(map);
      addParcelleLayers(map, props.mode);
      addTransactionLayers(map, props.transactions, props.mode);
      map.addSource('study-area', { type: 'geojson', data: studyBoundary(props.center, props.radius) });
      map.addLayer({ id: 'study-boundary', type: 'line', source: 'study-area', paint: { 'line-color': token('--fe-accent'), 'line-width': 2, 'line-dasharray': [3, 2] } });
      setupMapEvents(map, emit, () => {}, fetchParcelles);
      if (map.getZoom() >= 13) fetchParcelles();
      emit('map-loaded');
    });
  });

  watch([() => props.center, () => props.radius], () => {
    map?.getSource('study-area')?.setData(studyBoundary(props.center, props.radius));
  });
  watch(() => props.center, (newCenter) => {
    if (map) map.flyTo({ center: newCenter, zoom: 14, duration: 300 });
  });
  watch(() => props.activeFilter, () => {
    if (map?.getSource('parcelles') && map.getZoom() >= 13) fetchParcelles();
  });
  watch(() => props.mode, applyMode);
  watch(() => props.selectedParcel, applyParcelHighlights);
  watch(() => props.relatedParcels, applyParcelHighlights, { deep: true });
  watch(() => props.transactions, (newData) => {
    if (map?.getSource('transactions')) map.getSource('transactions').setData(newData);
  });

  onUnmounted(() => {
    resizeObserver?.disconnect();
    parcelRequest++;
    parcelController?.abort();
    if (map) map.remove();
    map = null;
  });

  return { mapContainer, isLoading };
}
