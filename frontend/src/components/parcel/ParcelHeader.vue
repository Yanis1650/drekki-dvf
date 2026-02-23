<script setup>
import { computed } from 'vue';

const props = defineProps({
  parcelId: {
    type: String,
    default: null
  },
  coordinates: {
    type: Array,
    default: null // [lon, lat]
  }
});

const emit = defineEmits(['close']);

// Generate satellite image URL using Mapbox Static Images API
// Falls back to IGN orthophoto if no Mapbox token
const satelliteUrl = computed(() => {
  if (!props.coordinates || props.coordinates.length < 2) {
    return null;
  }
  
  const [lon, lat] = props.coordinates;
  const zoom = 18;
  const width = 440;
  const height = 160;
  
  // Use IGN orthophoto (free, no token required)
  // WMTS URL for IGN orthophotos
  const ignUrl = `https://wxs.ign.fr/essentiels/geoportail/wmts?` +
    `SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&` +
    `STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&` +
    `TILEMATRIX=${zoom}&TILECOL=${lon2tile(lon, zoom)}&TILEROW=${lat2tile(lat, zoom)}`;
  
  // Alternative: Static map from Mapbox (requires token)
  // const mapboxToken = 'YOUR_MAPBOX_TOKEN';
  // return `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/${lon},${lat},${zoom}/${width}x${height}@2x?access_token=${mapboxToken}`;
  
  // Use a reliable static image service - OpenStreetMap tiles as placeholder
  // For production, you'd use IGN WMTS or Mapbox
  return `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${zoom}/${lat2tile(lat, zoom)}/${lon2tile(lon, zoom)}`;
});

// Convert lon/lat to tile coordinates
const lon2tile = (lon, zoom) => {
  return Math.floor((lon + 180) / 360 * Math.pow(2, zoom));
};

const lat2tile = (lat, zoom) => {
  return Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom));
};

// Format parcel ID for display
const formattedId = computed(() => {
  if (!props.parcelId) return '';
  // Format: DEP-COM-PREF-SECT-NUM
  const id = props.parcelId;
  if (id.length === 14) {
    return `${id.slice(0, 2)}-${id.slice(2, 5)}-${id.slice(5, 8)}-${id.slice(8, 10)}-${id.slice(10)}`;
  }
  return id;
});
</script>

<template>
  <div class="parcel-header">
    <!-- Satellite Background -->
    <div class="header-bg">
      <img 
        v-if="satelliteUrl" 
        :src="satelliteUrl" 
        alt="Vue satellite"
        class="satellite-img"
        @error="(e) => e.target.style.display = 'none'"
      />
      <div class="gradient-overlay"></div>
      <div class="noise-overlay"></div>
    </div>
    
    <!-- Content -->
    <div class="header-content">
      <div class="header-info">
        <div class="badge-row">
          <span class="type-badge">
            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"/>
            </svg>
            Parcelle cadastrale
          </span>
        </div>
        <h2 class="parcel-id">{{ formattedId }}</h2>
        <p class="parcel-raw" v-if="parcelId">ID: {{ parcelId }}</p>
      </div>
      
      <button @click="emit('close')" class="close-btn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
    
    <!-- Coordinates Badge -->
    <div class="coords-badge" v-if="coordinates">
      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
      </svg>
      {{ coordinates[1]?.toFixed(5) }}, {{ coordinates[0]?.toFixed(5) }}
    </div>
  </div>
</template>

<style scoped>
.parcel-header {
  position: relative;
  height: 140px;
  overflow: hidden;
}

.header-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #527f8c, #39616d);
}

.satellite-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.9;
}

.gradient-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(57, 97, 109, 0.3) 0%,
    rgba(26, 41, 47, 0.7) 100%
  );
}

.noise-overlay {
  position: absolute;
  inset: 0;
  opacity: 0.03;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
}

.header-content {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  height: 100%;
}

.header-info {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 100%;
}

.badge-row {
  margin-bottom: 8px;
}

.type-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.parcel-id {
  font-size: 22px;
  font-weight: 800;
  color: white;
  margin: 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  letter-spacing: 0.02em;
}

.parcel-raw {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
  margin: 4px 0 0 0;
  font-family: monospace;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  border: none;
  border-radius: 10px;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.05);
}

.close-btn svg {
  width: 18px;
  height: 18px;
  stroke: white;
}

.coords-badge {
  position: absolute;
  bottom: 12px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
  font-family: 'JetBrains Mono', monospace;
}
</style>
