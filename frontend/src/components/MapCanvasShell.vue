<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  },
  selectedTownCodes: {
    type: Array,
    required: true
  },
  selectedVillageCodes: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['toggle-layer'])

const mapEl = ref(null)
const map = ref(null)
const status = ref({ loading: false, error: '' })

const orderedLayerEntries = computed(() => Object.entries(props.layerState))
const townshipRangeFillLayerId = 'township-range-fill'
const villageRangeFillLayerId = 'village-range-fill'

const getLineWidthExpression = (key) => {
  if (key === 'county') {
    return ['interpolate', ['linear'], ['zoom'], 5, 2.2, 9, 2.0, 12, 1.8, 16, 1.6, 20, 1.4]
  }
  if (key === 'township') {
    return ['interpolate', ['linear'], ['zoom'], 8, 1.6, 12, 1.4, 16, 1.1, 20, 0.9]
  }
  return ['interpolate', ['linear'], ['zoom'], 12, 1.2, 14, 1.0, 16, 0.8, 20, 0.6]
}

const refreshLoading = () => {
  if (!map.value) return
  status.value.loading = !map.value.areTilesLoaded()
}

const updateLayerVisibility = (key) => {
  const m = map.value
  if (!m) return

  const entry = props.layerState[key]
  if (!entry || !m.getLayer(entry.layerId)) return
  m.setLayoutProperty(entry.layerId, 'visibility', entry.active ? 'visible' : 'none')
}

const getTownshipRangeFilter = () => {
  if (!props.selectedTownCodes.length) {
    return ['==', ['get', 'TOWNCODE'], '__no_match__']
  }
  return ['in', ['get', 'TOWNCODE'], ['literal', props.selectedTownCodes]]
}

const updateTownshipRangeFillFilter = () => {
  const m = map.value
  if (!m || !m.getLayer(townshipRangeFillLayerId)) return
  m.setFilter(townshipRangeFillLayerId, getTownshipRangeFilter())
}

const getVillageRangeFilter = () => {
  if (!props.selectedVillageCodes.length) {
    return ['==', ['get', 'VILLCODE'], '__no_match__']
  }
  return ['in', ['get', 'VILLCODE'], ['literal', props.selectedVillageCodes]]
}

const updateVillageRangeFillFilter = () => {
  const m = map.value
  if (!m || !m.getLayer(villageRangeFillLayerId)) return
  m.setFilter(villageRangeFillLayerId, getVillageRangeFilter())
}

const enforceLayerOrder = () => {
  const m = map.value
  if (!m) return

  const orderedIds = [
    townshipRangeFillLayerId,
    villageRangeFillLayerId,
    props.layerState.village?.layerId,
    props.layerState.township?.layerId,
    props.layerState.county?.layerId
  ].filter(Boolean)

  for (const id of orderedIds) {
    if (m.getLayer(id)) {
      m.moveLayer(id)
    }
  }
}

const addBoundaryLayer = (key) => {
  const m = map.value
  if (!m) return

  const entry = props.layerState[key]
  if (!entry) return
  if (m.getSource(entry.sourceId) || m.getLayer(entry.layerId)) return

  m.addSource(entry.sourceId, {
    type: 'vector',
    tiles: [entry.url],
    minzoom: 0,
    maxzoom: entry.maxNativeZoom
  })

  if (key === 'township' && !m.getLayer(townshipRangeFillLayerId)) {
    m.addLayer({
      id: townshipRangeFillLayerId,
      type: 'fill',
      source: entry.sourceId,
      'source-layer': entry.sourceLayer,
      minzoom: entry.minVisibleZoom,
      filter: getTownshipRangeFilter(),
      paint: {
        'fill-color': '#57a6f5',
        'fill-opacity': 0.3
      }
    })
  }

  if (key === 'village' && !m.getLayer(villageRangeFillLayerId)) {
    m.addLayer({
      id: villageRangeFillLayerId,
      type: 'fill',
      source: entry.sourceId,
      'source-layer': entry.sourceLayer,
      minzoom: entry.minVisibleZoom,
      filter: getVillageRangeFilter(),
      paint: {
        'fill-color': '#d17827',
        'fill-opacity': 0.35
      }
    })
  }

  m.addLayer({
    id: entry.layerId,
    type: 'line',
    source: entry.sourceId,
    'source-layer': entry.sourceLayer,
    minzoom: entry.minVisibleZoom,
    layout: {
      'line-join': 'round',
      'line-cap': 'round',
      visibility: entry.active ? 'visible' : 'none'
    },
    paint: {
      'line-color': entry.color,
      'line-width': getLineWidthExpression(key),
      'line-opacity': 0.9
    }
  })
}

const createMap = () => {
  map.value = new maplibregl.Map({
    container: mapEl.value,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; OpenStreetMap contributors'
        }
      },
      layers: [
        {
          id: 'osm',
          type: 'raster',
          source: 'osm'
        }
      ]
    },
    center: [120.9605, 23.6978],
    zoom: 7,
    minZoom: 6,
    maxZoom: 20
  })

  map.value.addControl(new maplibregl.NavigationControl(), 'top-right')

  map.value.on('load', () => {
    Object.keys(props.layerState).forEach(addBoundaryLayer)
    enforceLayerOrder()
    Object.keys(props.layerState).forEach(updateLayerVisibility)
    refreshLoading()
  })

  map.value.on('sourcedata', refreshLoading)
  map.value.on('idle', refreshLoading)
  map.value.on('error', (event) => {
    const message = event?.error?.message || 'Map rendering error'
    if (message.includes('404')) {
      return
    }
    if (message.includes('Failed to fetch')) {
      status.value.error = '無法讀取向量磚，請確認 tile server 已啟動且 URL 正確。'
      return
    }
    status.value.error = message
  })
}

const toggleLayer = (key) => {
  emit('toggle-layer', key)
}

watch(
  () => props.layerState,
  () => {
    Object.keys(props.layerState).forEach(updateLayerVisibility)
  },
  { deep: true }
)

watch(
  () => props.selectedTownCodes,
  () => {
    updateTownshipRangeFillFilter()
  },
  { deep: true }
)

watch(
  () => props.selectedVillageCodes,
  () => {
    updateVillageRangeFillFilter()
  },
  { deep: true }
)

onMounted(() => {
  createMap()
})

onBeforeUnmount(() => {
  if (!map.value) return
  map.value.remove()
  map.value = null
})
</script>

<template>
  <section class="map-area">
    <div ref="mapEl" class="map-canvas"></div>

    <div class="legend-card">
      <p class="legend-title">Boundary Layers</p>
      <button
        v-for="[key, row] in orderedLayerEntries"
        :key="key"
        class="legend-row"
        :class="{ inactive: !row.active }"
        type="button"
        @click="toggleLayer(key)"
      >
        <span class="legend-chip" :style="{ backgroundColor: row.color }"></span>
        <span>{{ row.label }}</span>
      </button>
      <p v-if="status.loading" class="status-row">圖磚載入中...</p>
      <p v-else-if="status.error" class="status-row error">{{ status.error }}</p>
    </div>
  </section>
</template>

<style scoped>
.map-area {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  min-height: calc(100vh - 112px);
  background: #11213b;
}

.map-canvas {
  position: absolute;
  inset: 0;
}

.legend-card {
  position: absolute;
  top: 20px;
  left: 20px;
  border-radius: 10px;
  background: rgb(15 23 41 / 82%);
  border: 1px solid #2d4161;
  padding: 10px 12px;
  display: grid;
  gap: 6px;
  min-width: 188px;
}

.legend-title {
  margin: 0;
  color: #dce8ff;
  font-size: 12px;
  font-weight: 700;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #d3e1f7;
  font-size: 11px;
  background: transparent;
  border: 0;
  padding: 0;
  text-align: left;
  cursor: pointer;
}

.legend-row.inactive {
  color: #6f88aa;
}

.legend-chip {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgb(255 255 255 / 20%);
}

.status-row {
  margin: 4px 0 0;
  color: #cee6ff;
  font-size: 11px;
}

.status-row.error {
  color: #ffb3ad;
}
</style>
