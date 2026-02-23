<script setup>
import { onMounted, ref, watch, onUnmounted, computed } from 'vue';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import client from '../api/client';
import { useColorScale, prixScale } from '../composables/useColorScale';

const props = defineProps({
  center: {
    type: Array,
    default: () => [-1.6778, 48.1173], // Rennes
  },
  transactions: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] }),
  },
  mode: {
    type: String,
    default: 'prix' // 'prix' or 'zan'
  },
  selectedParcel: {
    type: String,
    default: null
  },
  relatedParcels: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['map-loaded', 'transaction-click', 'parcel-click']);

const mapContainer = ref(null);
const isLoading = ref(true);
let map = null;

// Initialize D3-based color scale
const { getMapLibreExpression } = prixScale();

// Color schemes for different modes
const colorSchemes = {
  prix: {
    parcelles: [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'prix_m2_moyen'], 3000],
      1000, '#22c55e',   // Green
      3000, '#84cc16',   // Lime
      5000, '#eab308',   // Yellow
      7000, '#f97316',   // Orange
      10000, '#ef4444'   // Red
    ],
    points: [
      'interpolate',
      ['linear'],
      ['get', 'prix_m2'],
      1000, '#22c55e',
      3000, '#84cc16',
      5000, '#eab308',
      7000, '#f97316',
      10000, '#ef4444',
      15000, '#dc2626'
    ]
  },
  zan: {
    parcelles: [
      'match',
      ['get', 'densification_categorie'],
      'FORT', '#10b981',     // Emerald
      'MOYEN', '#eab308',    // Yellow
      'FAIBLE', '#f97316',   // Orange
      'SATURE', '#ef4444',   // Red
      '#94a3b8'              // Default gray
    ],
    points: [
      'interpolate',
      ['linear'],
      ['coalesce', ['get', 'zan_score'], 0.5],
      0, '#ef4444',
      0.3, '#f97316',
      0.5, '#eab308',
      0.7, '#22c55e',
      1, '#059669'
    ]
  },
  urbanisme: {
    parcelles: [
      'match',
      ['get', 'zone_plu'],
      'U', '#f59e0b',      // Amber - Urbain
      'AU', '#f97316',     // Orange - À Urbaniser
      'N', '#22c55e',      // Green - Naturel
      'A', '#84cc16',      // Lime - Agricole
      '#94a3b8'            // Default gray
    ],
    points: [
      'interpolate',
      ['linear'],
      ['get', 'prix_m2'],
      1000, '#22c55e',
      5000, '#eab308',
      10000, '#ef4444'
    ],
    opacity: 0.4  // Higher opacity for PLU overlay
  }
};

onMounted(() => {
  if (!mapContainer.value) return;

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: {
      version: 8,
      sources: {
        'carto': {
          type: 'raster',
          tiles: [
            'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
            'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'
          ],
          tileSize: 256,
          attribution: '© <a href="https://carto.com/">CARTO</a> © <a href="https://www.openstreetmap.org/copyright">OSM</a>',
          maxzoom: 20
        }
      },
      layers: [
        {
          id: 'carto-base',
          type: 'raster',
          source: 'carto'
        }
      ]
    },
    center: props.center,
    zoom: 13,
    pitch: 45,
    bearing: -17.6,
    antialias: true
  });
  
  // Custom navigation controls with compact style
  map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');

  map.on('load', () => {
    isLoading.value = false;
    
    // --- Transactions Source (Clustering) ---
    map.addSource('transactions', {
      type: 'geojson',
      data: props.transactions,
      cluster: true,
      clusterMaxZoom: 14,
      clusterRadius: 50
    });

    // Clusters - Modern style
    map.addLayer({
      id: 'clusters',
      type: 'circle',
      source: 'transactions',
      filter: ['has', 'point_count'],
      paint: {
        'circle-color': [
          'step',
          ['get', 'point_count'],
          '#527f8c',  // Sage-500
          50, '#3f6775',  // Sage-600
          150, '#c63806'  // Terracotta-600
        ],
        'circle-radius': [
          'step',
          ['get', 'point_count'],
          22,
          50, 28,
          150, 36
        ],
        'circle-stroke-width': 3,
        'circle-stroke-color': 'rgba(255,255,255,0.9)'
      }
    });
    
    // Cluster count labels
    map.addLayer({
      id: 'cluster-count',
      type: 'symbol',
      source: 'transactions',
      filter: ['has', 'point_count'],
      layout: {
        'text-field': '{point_count_abbreviated}',
        'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
        'text-size': 12
      },
      paint: {
        'text-color': '#ffffff'
      }
    });

    // Unclustered Points
    map.addLayer({
      id: 'unclustered-point',
      type: 'circle',
      source: 'transactions',
      filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': colorSchemes.prix.points,
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          10, 5,
          15, 10,
          18, 14
        ],
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.9
      }
    });

    // --- Parcelles Source (Polygons) ---
    map.addSource('parcelles', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    });

    map.addLayer({
      id: 'parcelles-fill',
      type: 'fill',
      source: 'parcelles',
      minzoom: 13,
      paint: {
        'fill-color': colorSchemes.prix.parcelles,
        'fill-opacity': 0.25
      }
    });

    map.addLayer({
      id: 'parcelles-line',
      type: 'line',
      source: 'parcelles',
      minzoom: 13,
      paint: {
        'line-color': '#475569',
        'line-width': 1.5,
        'line-opacity': 0.6
      }
    });

    // Parcel hover highlight
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

    // Events - Transaction click
    map.on('click', 'unclustered-point', (e) => {
      const feature = e.features[0];
      emit('transaction-click', feature);
    });
    
    // Parcelle click - emit event to open side panel
    const handleParcelleClick = (e) => {
      if (e.features.length > 0) {
        const feature = e.features[0];
        
        // DEBUG: Log parcel click details
        console.log('🔍 [PARCEL CLICK] Feature properties:', feature.properties);
        console.log('🔍 [PARCEL CLICK] id_parcelle:', feature.properties.id_parcelle);
        console.log('🔍 [PARCEL CLICK] id_parcelle length:', feature.properties.id_parcelle?.length);
        console.log('🔍 [PARCEL CLICK] All keys:', Object.keys(feature.properties));
        
        emit('parcel-click', feature);
      }
    };

    map.on('click', 'parcelles-fill', handleParcelleClick);
    
    // Hover effects on parcels
    let hoveredParcelId = null;
    
    map.on('mousemove', 'parcelles-fill', (e) => {
      if (e.features.length > 0) {
        const feature = e.features[0];
        // Use feature.id if it exists, otherwise skip hover effect
        const featureId = feature.id;
        
        if (featureId !== undefined && featureId !== null) {
          if (hoveredParcelId !== null && hoveredParcelId !== featureId) {
            try {
              map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: false });
            } catch (err) { /* ignore */ }
          }
          hoveredParcelId = featureId;
          try {
            map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: true });
          } catch (err) { /* ignore */ }
        }
      }
    });
    
    map.on('mouseleave', 'parcelles-fill', () => {
      if (hoveredParcelId !== null) {
        try {
          map.setFeatureState({ source: 'parcelles', id: hoveredParcelId }, { hover: false });
        } catch (err) { /* ignore */ }
      }
      hoveredParcelId = null;
    });
    
    // Cursor changes
    map.on('mouseenter', 'unclustered-point', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'unclustered-point', () => {
      map.getCanvas().style.cursor = '';
    });
    map.on('mouseenter', 'parcelles-fill', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'parcelles-fill', () => {
      map.getCanvas().style.cursor = '';
    });
    
    // Cluster click to zoom
    map.on('click', 'clusters', (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] });
      const clusterId = features[0].properties.cluster_id;
      map.getSource('transactions').getClusterExpansionZoom(clusterId, (err, zoom) => {
        if (err) return;
        map.easeTo({
          center: features[0].geometry.coordinates,
          zoom: zoom
        });
      });
    });
    
    // Fetch data on map move
    map.on('moveend', () => {
      fetchTransactions();
      fetchParcelles();
    });
    
    // Initial fetch
    fetchTransactions();
    if (map.getZoom() >= 13) {
      fetchParcelles();
    }

    emit('map-loaded');
  });
});

// Watch center prop to move map
watch(() => props.center, (newCenter) => {
  if (map) {
    map.flyTo({
      center: newCenter,
      essential: true,
      zoom: 16,
      pitch: 50,
      duration: 2000
    });
  }
});

// Watch mode prop to update colors
watch(() => props.mode, (newMode) => {
  if (!map) return;
  
  const scheme = colorSchemes[newMode] || colorSchemes.prix;
  
  // Update parcelles fill color
  if (map.getLayer('parcelles-fill')) {
    map.setPaintProperty('parcelles-fill', 'fill-color', scheme.parcelles);
    // Adjust opacity for urbanisme mode (higher visibility for PLU zones)
    const opacity = scheme.opacity || 0.25;
    map.setPaintProperty('parcelles-fill', 'fill-opacity', opacity);
  }
  
  // Update unclustered points color
  if (map.getLayer('unclustered-point')) {
    map.setPaintProperty('unclustered-point', 'circle-color', scheme.points);
  }
  
  console.log(`[MapContainer] Mode changed to: ${newMode}`);
});

// Function to apply parcel highlights (reusable)
const applyParcelHighlights = () => {
  if (!map || !map.getLayer('parcelles-fill')) return;
  
  const scheme = colorSchemes[props.mode] || colorSchemes.prix;
  const selectedId = props.selectedParcel;
  const relatedIds = props.relatedParcels || [];

  if (selectedId || relatedIds.length > 0) {
    // Build highlight expressions considering both selected and related parcels
    let fillColorExpression;
    let lineWidthExpression;
    let lineColorExpression;

    if (relatedIds.length > 0 && selectedId) {
      // Both selected and related - use case with in expression
      fillColorExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        'rgba(239, 68, 68, 0.6)', // Red for selected
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        'rgba(251, 146, 60, 0.6)', // Orange for related (filiation)
        scheme.parcelles
      ];
      
      lineWidthExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        4,
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        3,
        1.5
      ];
      
      lineColorExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        '#dc2626', // Red
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        '#ea580c', // Orange
        '#475569'
      ];
    } else if (selectedId) {
      // Only selected parcel
      fillColorExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        'rgba(239, 68, 68, 0.6)',
        scheme.parcelles
      ];
      
      lineWidthExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        4,
        1.5
      ];
      
      lineColorExpression = [
        'case',
        ['==', ['get', 'id_parcelle'], selectedId],
        '#dc2626',
        '#475569'
      ];
    } else {
      // Only related parcels
      fillColorExpression = [
        'case',
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        'rgba(251, 146, 60, 0.6)',
        scheme.parcelles
      ];
      
      lineWidthExpression = [
        'case',
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        3,
        1.5
      ];
      
      lineColorExpression = [
        'case',
        ['in', ['get', 'id_parcelle'], ['literal', relatedIds]],
        '#ea580c',
        '#475569'
      ];
    }

    map.setPaintProperty('parcelles-fill', 'fill-color', fillColorExpression);
    map.setPaintProperty('parcelles-fill', 'fill-opacity', 0.5);
    map.setPaintProperty('parcelles-line', 'line-width', lineWidthExpression);
    map.setPaintProperty('parcelles-line', 'line-color', lineColorExpression);
  } else {
    // Reset to base styling
    map.setPaintProperty('parcelles-fill', 'fill-color', scheme.parcelles);
    map.setPaintProperty('parcelles-fill', 'fill-opacity', scheme.opacity || 0.25);
    map.setPaintProperty('parcelles-line', 'line-width', 1.5);
    map.setPaintProperty('parcelles-line', 'line-color', '#475569');
  }
};

// Watch selectedParcel prop for visual highlight (DVF-style)
watch(() => props.selectedParcel, () => {
  applyParcelHighlights();
});

// Watch relatedParcels for filiation hover highlight
watch(() => props.relatedParcels, () => {
  applyParcelHighlights();
}, { deep: true });

// Fetch DVF Transactions (Points)
const fetchTransactions = async () => {
  if (!map) return;
  
  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth()
  ].join(',');

  try {
    const res = await client.get(`/land/geojson?bbox=${bbox}`);
    if (map.getSource('transactions')) {
      map.getSource('transactions').setData(res.data);
    }
  } catch (err) {
    console.error("Transactions fetch error:", err);
  }
};

// Fetch Cadastral Parcels (Polygons)
const fetchParcelles = async () => {
  if (!map) return;
  const zoom = map.getZoom();
  
  if (zoom < 13) {
    if (map.getSource('parcelles')) {
      map.getSource('parcelles').setData({ type: 'FeatureCollection', features: [] });
    }
    return;
  }

  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth()
  ].join(',');

  try {
    const res = await client.get(`/land/parcelles?bbox=${bbox}`);
    if (map.getSource('parcelles')) {
      map.getSource('parcelles').setData(res.data);
    }
  } catch (err) {
    console.error("Parcelles fetch error:", err);
  }
};

// Watch transactions prop to update data
watch(() => props.transactions, (newData) => {
  if (map && map.getSource('transactions')) {
    map.getSource('transactions').setData(newData);
  }
});

onUnmounted(() => {
  if (map) map.remove();
});
</script>

<template>
  <div class="relative w-full h-full">
    <!-- Map Container -->
    <div ref="mapContainer" class="w-full h-full"></div>
    
    <!-- Loading Overlay -->
    <Transition
      enter-active-class="transition-opacity duration-500"
      leave-active-class="transition-opacity duration-500"
      enter-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div 
        v-if="isLoading" 
        class="absolute inset-0 bg-gradient-to-br from-slate-50 via-white to-sage-50 flex items-center justify-center"
      >
        <div class="text-center">
          <div class="relative w-20 h-20 mx-auto mb-6">
            <!-- Outer ring -->
            <div class="absolute inset-0 rounded-full border-4 border-slate-200"></div>
            <!-- Spinning ring -->
            <div class="absolute inset-0 rounded-full border-4 border-sage-500 border-t-transparent animate-spin"></div>
            <!-- Inner gradient circle -->
            <div class="absolute inset-3 rounded-full bg-gradient-to-br from-sage-500 to-sage-700 opacity-20 animate-pulse"></div>
          </div>
          <p class="text-slate-600 font-semibold text-lg">Chargement de la carte</p>
          <p class="text-slate-400 text-sm mt-1">Préparation des données foncières...</p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
/* MapLibre controls styling */
.maplibregl-ctrl-top-right {
  top: 80px !important;
}

.maplibregl-ctrl-group {
  background: rgba(255, 255, 255, 0.95) !important;
  backdrop-filter: blur(12px) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
  border: 1px solid rgba(255, 255, 255, 0.5) !important;
  overflow: hidden;
}

.maplibregl-ctrl-group button {
  width: 40px !important;
  height: 40px !important;
}

.maplibregl-ctrl-group button + button {
  border-top: 1px solid rgba(226, 232, 240, 0.8) !important;
}

.maplibregl-ctrl-group button:hover {
  background-color: #f8fafc !important;
}

/* Popup styling */
.maplibregl-popup-content {
  padding: 0 !important;
  border-radius: 16px !important;
  font-family: 'DM Sans', sans-serif !important;
  background: rgba(255, 255, 255, 0.98) !important;
  backdrop-filter: blur(12px) !important;
  border: 1px solid rgba(63, 103, 117, 0.15) !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15) !important;
}

.maplibregl-popup-close-button {
  font-size: 20px !important;
  padding: 8px 12px !important;
  color: #64748b !important;
}

.maplibregl-popup-close-button:hover {
  color: #1e293b !important;
  background: #f1f5f9 !important;
}
</style>
