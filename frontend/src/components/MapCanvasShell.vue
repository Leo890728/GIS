<script setup>
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import { getBoundaryLayerIds, useMapLayers } from './map/useMapLayers'
import { rangeLayerIds, useMapRanges } from './map/useMapRanges'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  },
  selectedRangeGeoJson: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle-layer'])

const mapEl = ref(null)
const map = ref(null)
const status = ref({ loading: false, error: '' })
const layerStateRef = toRef(props, 'layerState')
const selectedRangeGeoJsonRef = toRef(props, 'selectedRangeGeoJson')

const orderedLayerEntries = computed(() => Object.entries(props.layerState))
const { addBoundaryLayers, updateAllLayerVisibility } = useMapLayers(map, layerStateRef)
const { addRangeLayers, updateRangeGeoJson } = useMapRanges(map, selectedRangeGeoJsonRef)

const refreshLoading = () => {
  if (!map.value) return
  status.value.loading = !map.value.areTilesLoaded()
}

const enforceLayerOrder = () => {
  const m = map.value
  if (!m) return

  const orderedIds = [
    ...rangeLayerIds,
    ...getBoundaryLayerIds(props.layerState)
  ]

  for (const id of orderedIds) {
    if (m.getLayer(id)) {
      m.moveLayer(id)
    }
  }
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
    addRangeLayers()
    addBoundaryLayers()
    enforceLayerOrder()
    updateAllLayerVisibility()
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

watch(
  () => props.layerState,
  () => {
    updateAllLayerVisibility()
  },
  { deep: true }
)

watch(
  () => props.selectedRangeGeoJson,
  () => {
    updateRangeGeoJson()
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
        @click="emit('toggle-layer', key)"
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
