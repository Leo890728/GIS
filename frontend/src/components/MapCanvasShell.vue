<script setup>
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import { getDataLayerEntryByPointLayerId, getDataLayerIds, getDataPointLayerIds, useMapDataLayers } from './map/useMapDataLayers'
import { formatTooltipItemValue } from '../features/data/formatters'
import { getBoundaryLayerIds, useMapLayers } from './map/useMapLayers'
import { rangeLayerIds, useMapRanges } from './map/useMapRanges'

const basemapSourceId = 'basemap-source'
const basemapLayerId = 'basemap-layer'

const props = defineProps({
  activeBasemap: {
    type: Object,
    required: true
  },
  layerState: {
    type: Object,
    required: true
  },
  selectedRangeGeoJson: {
    type: Object,
    required: true
  },
  dataLayerState: {
    type: Object,
    required: true
  },
  dataLayerGeoJson: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle-layer', 'toggle-data-layer'])

const mapEl = ref(null)
const map = ref(null)
const dataHoverPopup = ref(null)
const status = ref({ loading: false, error: '' })
const layerStateRef = toRef(props, 'layerState')
const selectedRangeGeoJsonRef = toRef(props, 'selectedRangeGeoJson')
const dataLayerStateRef = toRef(props, 'dataLayerState')
const dataLayerGeoJsonRef = toRef(props, 'dataLayerGeoJson')

const orderedLayerEntries = computed(() => Object.entries(props.layerState))
const orderedDataLayerEntries = computed(() => Object.entries(props.dataLayerState))
const { addBoundaryLayers, updateAllLayerVisibility } = useMapLayers(map, layerStateRef)
const { addRangeLayers, updateRangeGeoJson } = useMapRanges(map, selectedRangeGeoJsonRef)
const { addDataLayers, updateAllDataLayerVisibility, updateDataLayerGeoJson } = useMapDataLayers(
  map,
  dataLayerStateRef,
  dataLayerGeoJsonRef
)

const refreshLoading = () => {
  if (!map.value) return
  status.value.loading = !map.value.areTilesLoaded()
}

const applyBasemap = (basemap) => {
  const m = map.value
  if (!m || !basemap) return
  if (!m.isStyleLoaded()) return
  const tiles = Array.isArray(basemap.tiles) ? basemap.tiles.filter(Boolean) : []
  if (!tiles.length) return

  if (m.getLayer(basemapLayerId)) {
    m.removeLayer(basemapLayerId)
  }
  if (m.getSource(basemapSourceId)) {
    m.removeSource(basemapSourceId)
  }

  m.addSource(basemapSourceId, {
    type: 'raster',
    tiles,
    tileSize: Number(basemap.tileSize || 256),
    attribution: basemap.attribution || ''
  })

  const firstLayerId = m.getStyle()?.layers?.[0]?.id
  if (firstLayerId) {
    m.addLayer(
      {
        id: basemapLayerId,
        type: 'raster',
        source: basemapSourceId
      },
      firstLayerId
    )
  } else {
    m.addLayer({
      id: basemapLayerId,
      type: 'raster',
      source: basemapSourceId
    })
  }
}

const enforceLayerOrder = () => {
  const m = map.value
  if (!m) return

  const orderedIds = [
    ...getBoundaryLayerIds(props.layerState),
    ...rangeLayerIds,
    ...getDataLayerIds(props.dataLayerState)
  ]

  for (const id of orderedIds) {
    if (m.getLayer(id)) {
      m.moveLayer(id)
    }
  }
}

const escapeHtml = (value) =>
  String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')

const hideDataHoverPopup = () => {
  if (dataHoverPopup.value) {
    dataHoverPopup.value.remove()
    dataHoverPopup.value = null
  }
  if (map.value) {
    map.value.getCanvas().style.cursor = ''
  }
}

const buildDataTooltipHtml = (entry, properties) => {
  const tooltip = entry?.tooltip || {}
  const items = Array.isArray(tooltip.items) ? tooltip.items : []
  if (!items.length) return ''

  const titleField = tooltip.titleField
  const titleRawValue = titleField ? properties?.[titleField] : null
  const titleValue = titleRawValue == null || titleRawValue === '' ? '' : String(titleRawValue)
  const rows = items.map((item) => {
    const label = item?.label || item?.field || ''
    const value = formatTooltipItemValue(item, properties)
    return `<div class="hover-row"><span class="hover-label">${escapeHtml(label)}</span><span class="hover-value">${escapeHtml(value)}</span></div>`
  })

  const titleHtml = titleValue ? `<div class="hover-title">${escapeHtml(titleValue)}</div>` : ''
  return `<div class="hover-card">${titleHtml}${rows.join('')}</div>`
}

const handleDataHover = (event) => {
  const m = map.value
  if (!m) return

  const pointLayerIds = getDataPointLayerIds(props.dataLayerState).filter((layerId) => m.getLayer(layerId))
  if (!pointLayerIds.length) {
    hideDataHoverPopup()
    return
  }

  const features = m.queryRenderedFeatures(event.point, { layers: pointLayerIds })
  if (!features.length) {
    hideDataHoverPopup()
    return
  }

  const feature = features[0]
  const pointLayerId = feature?.layer?.id || ''
  const entry = getDataLayerEntryByPointLayerId(props.dataLayerState, pointLayerId)
  if (!entry?.tooltip?.enabled) {
    hideDataHoverPopup()
    return
  }

  const html = buildDataTooltipHtml(entry, feature.properties || {})
  if (!html) {
    hideDataHoverPopup()
    return
  }

  const coordinates = feature?.geometry?.coordinates || [event.lngLat.lng, event.lngLat.lat]
  if (!dataHoverPopup.value) {
    dataHoverPopup.value = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
      className: 'data-hover-popup'
    })
  }
  dataHoverPopup.value.setLngLat(coordinates).setHTML(html).addTo(m)
  m.getCanvas().style.cursor = 'pointer'
}

const createMap = () => {
  const initialTiles = Array.isArray(props.activeBasemap?.tiles) ? props.activeBasemap.tiles : []
  map.value = new maplibregl.Map({
    container: mapEl.value,
    style: {
      version: 8,
      sources: {
        [basemapSourceId]: {
          type: 'raster',
          tiles: initialTiles,
          tileSize: Number(props.activeBasemap?.tileSize || 256),
          attribution: props.activeBasemap?.attribution || ''
        }
      },
      layers: [
        {
          id: basemapLayerId,
          type: 'raster',
          source: basemapSourceId
        }
      ]
    },
    center: [120.9605, 23.6978],
    zoom: 7,
    minZoom: 6,
    maxZoom: 20
  })

  map.value.addControl(new maplibregl.NavigationControl(), 'top-right')

  map.value.on('load', async () => {
    applyBasemap(props.activeBasemap)
    addRangeLayers()
    await addDataLayers()
    addBoundaryLayers()
    enforceLayerOrder()
    updateAllLayerVisibility()
    updateAllDataLayerVisibility()
    refreshLoading()
  })

  map.value.on('mousemove', handleDataHover)
  map.value.on('mouseout', hideDataHoverPopup)
  map.value.on('dragstart', hideDataHoverPopup)
  map.value.on('zoomstart', hideDataHoverPopup)
  map.value.on('sourcedata', refreshLoading)
  map.value.on('idle', refreshLoading)
  map.value.on('error', (event) => {
    const message = event?.error?.message || 'Map rendering error'
    if (message.includes('404')) {
      return
    }
    if (message.includes('Failed to fetch')) {
      status.value.error = 'Unable to load map tiles. Check the tile server URL.'
      return
    }
    status.value.error = message
  })
}

watch(
  () => props.activeBasemap,
  () => {
    applyBasemap(props.activeBasemap)
    enforceLayerOrder()
  },
  { deep: true }
)

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

watch(
  () => props.dataLayerState,
  () => {
    updateAllDataLayerVisibility()
    enforceLayerOrder()
    hideDataHoverPopup()
  },
  { deep: true }
)

watch(
  () => props.dataLayerGeoJson,
  () => {
    updateDataLayerGeoJson()
  },
  { deep: true }
)

onMounted(() => {
  createMap()
})

onBeforeUnmount(() => {
  hideDataHoverPopup()
  if (!map.value) return
  map.value.remove()
  map.value = null
})
</script>

<template>
  <section class="map-area">
    <div ref="mapEl" class="map-canvas"></div>

    <div class="legend-card">
      <p class="legend-title">Boundary</p>
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

      <template v-if="orderedDataLayerEntries.length">
        <p class="legend-title data-title">Data Layers</p>
        <button
          v-for="[key, row] in orderedDataLayerEntries"
          :key="key"
          class="legend-row"
          :class="{ inactive: !row.active }"
          type="button"
          @click="emit('toggle-data-layer', key)"
        >
          <span class="legend-chip round" :style="{ backgroundColor: row.style?.color || '#f2c94c' }"></span>
          <span>{{ row.label }}</span>
        </button>
      </template>
    </div>

    <div v-if="status.loading || status.error" class="map-status-card" :class="{ error: status.error }">
      <p v-if="status.loading" class="status-row">Loading map tiles...</p>
      <p v-else class="status-row">{{ status.error }}</p>
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

.legend-title.data-title {
  margin-top: 6px;
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

.legend-chip.round {
  border-radius: 999px;
}

.status-row {
  margin: 0;
  color: #cee6ff;
  font-size: 11px;
}

.status-row.error {
  color: #ffb3ad;
}

.map-status-card {
  position: absolute;
  right: 20px;
  bottom: 20px;
  border-radius: 10px;
  border: 1px solid #2f4668;
  background: rgb(15 23 41 / 86%);
  padding: 8px 10px;
  min-width: 170px;
}

.map-status-card.error {
  border-color: #7a3f4a;
}

.map-status-card.error .status-row {
  color: #ffb3ad;
}

:deep(.data-hover-popup .maplibregl-popup-content) {
  background: rgb(17 26 43 / 94%);
  border: 1px solid #2f4668;
  border-radius: 10px;
  color: #eaf1ff;
  font-size: 11px;
  padding: 8px 10px;
  min-width: 180px;
  max-width: min(360px, calc(100vw - 48px));
  overflow: hidden;
}

:deep(.data-hover-popup .maplibregl-popup-tip) {
  border-top-color: #2f4668;
}

:deep(.data-hover-popup .hover-card) {
  display: grid;
  gap: 6px;
}

:deep(.data-hover-popup .hover-title) {
  font-size: 12px;
  font-weight: 700;
  color: #f4e3a5;
}

:deep(.data-hover-popup .hover-row) {
  display: grid;
  grid-template-columns: minmax(72px, 42%) minmax(0, 1fr);
  align-items: start;
  column-gap: 10px;
  row-gap: 2px;
}

:deep(.data-hover-popup .hover-label) {
  color: #9fb7da;
  overflow-wrap: anywhere;
  word-break: break-word;
}

:deep(.data-hover-popup .hover-value) {
  color: #eaf1ff;
  text-align: right;
  min-width: 0;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
