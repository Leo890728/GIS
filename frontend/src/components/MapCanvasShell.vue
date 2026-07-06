<script setup>
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import { getDataLayerEntryByPointLayerId, getDataLayerIds, getDataPointLayerIds, useMapDataLayers } from './map/useMapDataLayers'
import { formatTooltipItemValue, resolveTooltipTitle } from '../features/data/formatters'
import { getBoundaryLayerIds, useMapLayers } from './map/useMapLayers'
import { rangeLayerIds, useMapRanges } from './map/useMapRanges'
import { useMapRouteLayers } from './map/useMapRouteLayers'
import SimulatorControlBar from '../features/simulator/SimulatorControlBar.vue'
import AnalyticsDrawer from '../features/simulator/AnalyticsDrawer.vue'
import RouteVehicleDrawer from '../features/simulator/RouteVehicleDrawer.vue'
import { ensureIcons } from '../features/data/icons/registry'

const basemapSourceId = 'basemap-source'
const basemapLayerId = 'basemap-layer'
const routeStopLayerId = 'route-stop-layer'
const routeStopOrderLayerId = 'route-stop-order-layer'

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
  },
  routeLineGeoJson: {
    type: Object,
    required: true
  },
  routeStopGeoJson: {
    type: Object,
    required: true
  },
  routeAnchorGeoJson: {
    type: Object,
    required: true
  },
  routeLayerVisibility: {
    type: Object,
    default: () => ({
      line: true,
      stops: true,
      anchors: true,
      vehicles: {}
    })
  },
  routePickMode: {
    type: String,
    default: ''
  },
  simulatorState: {
    type: Object,
    default: () => ({ active: false })
  },
  simulatorSpeeds: {
    type: Array,
    default: () => [1, 10, 30, 60]
  },
  routeSimGeoJson: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] })
  },
  routeSimTraveledGeoJson: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] })
  },
  routeSimRemainingGeoJson: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] })
  },
  routeSimHeatGeoJson: {
    type: Object,
    default: () => ({ type: 'FeatureCollection', features: [] })
  },
  routeSimSelectedVehicle: {
    type: Object,
    default: null
  },
  routeSimProgress: {
    type: Object,
    default: () => ({})
  },
  routeVehicleCapacityKg: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'toggle-layer',
  'toggle-data-layer',
  'toggle-route-layer',
  'route-map-click',
  'simulator-set-time',
  'simulator-toggle-play',
  'simulator-set-speed',
  'simulator-step',
  'simulator-toggle-smooth',
  'simulator-select-segment',
  'simulator-set-window',
  'simulator-toggle-live',
  'simulator-toggle-route-heatmap',
  'simulator-toggle-follow',
  'simulator-select-feature',
  'simulator-toggle-track',
  'simulator-stop'
])

const mapEl = ref(null)
const map = ref(null)
// True once the initial style 'load' has fired. Style mutations (add/remove
// layers & sources) are safe from this point on, even while sources are still
// streaming — unlike map.isStyleLoaded(), which reports false whenever a source
// is loading (e.g. the simulator's geojson is re-fed every frame during
// playback), and would otherwise silently drop basemap/overlay updates.
const mapLoaded = ref(false)
const dataHoverPopup = ref(null)
let lastHoverPoint = null
const status = ref({ loading: false, error: '' })
const layerStateRef = toRef(props, 'layerState')
const selectedRangeGeoJsonRef = toRef(props, 'selectedRangeGeoJson')
const dataLayerStateRef = toRef(props, 'dataLayerState')
const dataLayerGeoJsonRef = toRef(props, 'dataLayerGeoJson')
const routeLineGeoJsonRef = toRef(props, 'routeLineGeoJson')
const routeStopGeoJsonRef = toRef(props, 'routeStopGeoJson')
const routeAnchorGeoJsonRef = toRef(props, 'routeAnchorGeoJson')
const routeLayerVisibilityRef = toRef(props, 'routeLayerVisibility')

const orderedLayerEntries = computed(() => Object.entries(props.layerState))
const orderedDataLayerEntries = computed(() => Object.entries(props.dataLayerState))

// Field labels for the analytics drawer come from the simulated dataset's
// layer config (tooltip labels + propertyLabels extras), not hardcoded UI maps.
const simulatorPropertyLabels = computed(() => {
  const dataId = props.simulatorState?.dataId
  if (!dataId) return {}
  const entry = Object.values(props.dataLayerState || {}).find(
    (layer) => (layer.query?.dataId || layer.dataId) === dataId
  )
  return entry?.propertyLabels || {}
})
const routeTypeLabels = {
  start: '起點',
  end: '終點',
  pickup: '收運點',
  disposal: '處理場',
  dropped: '未排入'
}
const formatRouteType = (value) => routeTypeLabels[value] || value
const routeLegendItems = computed(() => [
  {
    key: 'line',
    label: '路線',
    color: '#ffd166',
    active: props.routeLayerVisibility?.line !== false
  },
  {
    key: 'stops',
    label: '停靠點',
    color: '#34d399',
    active: props.routeLayerVisibility?.stops !== false
  },
  {
    key: 'anchors',
    label: '起訖點',
    color: '#22d3ee',
    active: props.routeLayerVisibility?.anchors !== false
  }
])
const routeVehicleLegendItems = computed(() => {
  const features = Array.isArray(props.routeLineGeoJson?.features) ? props.routeLineGeoJson.features : []
  const vehiclesVisibility = props.routeLayerVisibility?.vehicles || {}
  return features
    .map((feature) => {
      const properties = feature?.properties || {}
      const vehicleId = properties.vehicleId
      if (!vehicleId) return null
      const vehicleColor = properties.vehicleColor || '#ffd166'
      return {
        key: `vehicle:${vehicleId}`,
        label: vehicleId,
        color: vehicleColor,
        active: vehiclesVisibility[vehicleId] !== false
      }
    })
    .filter((item, index, array) => item && array.findIndex((target) => target.key === item.key) === index)
})
const { addBoundaryLayers, updateAllLayerVisibility } = useMapLayers(map, layerStateRef)
const { addRangeLayers, updateRangeGeoJson } = useMapRanges(map, selectedRangeGeoJsonRef)
const { addDataLayers, updateAllDataLayerVisibility, updateDataLayerGeoJson } = useMapDataLayers(
  map,
  dataLayerStateRef,
  dataLayerGeoJsonRef
)
const { addRouteLayers, updateRouteGeoJson, updateRouteVisibility } = useMapRouteLayers(
  map,
  routeLineGeoJsonRef,
  routeStopGeoJsonRef,
  routeAnchorGeoJsonRef,
  routeLayerVisibilityRef
)

const refreshLoading = () => {
  if (!map.value) return
  status.value.loading = !map.value.areTilesLoaded()
}

const applyBasemap = (basemap) => {
  const m = map.value
  if (!m || !basemap) return
  if (!mapLoaded.value) return
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
    ...rangeLayerIds,
    ...getBoundaryLayerIds(props.layerState),
    ...getDataLayerIds(props.dataLayerState),
    'route-line-layer',
    'route-sim-line-traveled-layer',
    'route-sim-line-remaining-layer',
    'route-sim-heat-layer',
    'route-stop-layer',
    'route-stop-order-layer',
    'route-anchor-layer',
    'route-sim-vehicle-layer',
    'route-sim-vehicle-label-layer'
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
    map.value.getCanvas().style.cursor = ['start', 'end'].includes(props.routePickMode) ? 'crosshair' : ''
  }
}

const buildDataTooltipHtml = (entry, properties) => {
  const tooltip = entry?.tooltip || {}
  const items = Array.isArray(tooltip.items) ? tooltip.items : []
  if (!items.length) return ''

  const titleValue = resolveTooltipTitle(tooltip, properties)
  const rows = items.map((item) => {
    const label = item?.label || item?.field || ''
    const value = formatTooltipItemValue(item, properties)
    return `<div class="hover-row"><span class="hover-label">${escapeHtml(label)}</span><span class="hover-value">${escapeHtml(value)}</span></div>`
  })

  const titleHtml = titleValue ? `<div class="hover-title">${escapeHtml(titleValue)}</div>` : ''
  return `<div class="hover-card">${titleHtml}${rows.join('')}</div>`
}

const buildRouteTooltipHtml = (properties) => {
  if (!properties || typeof properties !== 'object') return ''
  const rows = []
  const appendRow = (label, value) => {
    if (value == null || value === '') return
    rows.push(
      `<div class="hover-row"><span class="hover-label">${escapeHtml(label)}</span><span class="hover-value">${escapeHtml(value)}</span></div>`
    )
  }

  appendRow('車輛', properties.vehicleId)
  appendRow('站序', properties.stopIndex != null && Number(properties.stopIndex) >= 0 ? Number(properties.stopIndex) + 1 : '-')
  appendRow('類型', formatRouteType(properties.type))
  appendRow('名稱', properties.name)
  appendRow('載重 (kg)', properties.loadKg)
  appendRow('合併點數', properties.memberCount)

  const legDistance = properties.legFromPrevDistanceM
  const legDuration = properties.legFromPrevDurationS
  appendRow('前段距離 (m)', legDistance)
  appendRow('前段時間 (s)', legDuration)

  if (!rows.length) return ''
  const titleValue = properties.name || formatRouteType(properties.type) || '路線節點'
  return `<div class="hover-card"><div class="hover-title">${escapeHtml(titleValue)}</div>${rows.join('')}</div>`
}

const handleDataHover = (event) => {
  const m = map.value
  if (!m) return
  if (['start', 'end'].includes(props.routePickMode)) {
    hideDataHoverPopup()
    return
  }

  if (m.getLayer(routeStopLayerId)) {
    const routeFeatures = m.queryRenderedFeatures(event.point, { layers: [routeStopOrderLayerId, routeStopLayerId] })
    if (routeFeatures.length) {
      const routeFeature = routeFeatures[0]
      const html = buildRouteTooltipHtml(routeFeature.properties || {})
      if (html) {
        const coordinates = routeFeature?.geometry?.coordinates || [event.lngLat.lng, event.lngLat.lat]
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
        return
      }
    }
  }

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

// In the simulator, clicking a data point selects that entity: the Analytics
// drawer shows its info and offers a trajectory overlay. Clicking empty map
// space clears the selection.
const handleSimulatorClick = (event) => {
  const m = map.value
  if (!m || !props.simulatorState?.active) return
  // Route-plan playback: clicking a simulated truck opens the vehicle drawer
  // (stop timeline + current load); clicking empty space closes it.
  if (props.simulatorState.mode === 'route-plan') {
    if (!m.getLayer('route-sim-vehicle-layer')) return
    const vehicleFeatures = m.queryRenderedFeatures(event.point, { layers: ['route-sim-vehicle-layer'] })
    const vehicleFeature = vehicleFeatures[0]
    const trackKey = vehicleFeature?.properties?.__trackKey
    if (trackKey == null || trackKey === '') {
      emit('simulator-select-feature', null)
      return
    }
    emit('simulator-select-feature', {
      key: String(trackKey),
      properties: vehicleFeature.properties || {},
      coordinates: vehicleFeature?.geometry?.coordinates || [event.lngLat.lng, event.lngLat.lat]
    })
    return
  }
  const pointLayerIds = getDataPointLayerIds(props.dataLayerState).filter((layerId) => m.getLayer(layerId))
  if (!pointLayerIds.length) return
  const features = m.queryRenderedFeatures(event.point, { layers: pointLayerIds })
  if (!features.length) {
    emit('simulator-select-feature', null)
    return
  }
  const feature = features[0]
  const properties = feature.properties || {}
  const key = properties.__trackKey
  if (key == null || key === '') {
    emit('simulator-select-feature', null)
    return
  }
  const coordinates = feature?.geometry?.coordinates || [event.lngLat.lng, event.lngLat.lat]
  emit('simulator-select-feature', { key: String(key), properties, coordinates })
}

// While a tooltip is open, re-run the hover lookup as the underlying data
// updates (e.g. during simulator playback) so its content/position track the
// moving points instead of going stale.
const refreshHoverFromData = () => {
  if (!dataHoverPopup.value || !lastHoverPoint || !map.value) return
  requestAnimationFrame(() => {
    if (!dataHoverPopup.value || !lastHoverPoint || !map.value) return
    handleDataHover(lastHoverPoint)
  })
}

const createMap = () => {
  const initialTiles = Array.isArray(props.activeBasemap?.tiles) ? props.activeBasemap.tiles : []
  map.value = new maplibregl.Map({
    container: mapEl.value,
    style: {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
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
    mapLoaded.value = true
    applyBasemap(props.activeBasemap)
    addRangeLayers()
    await addDataLayers()
    addRouteLayers()
    addBoundaryLayers()
    enforceLayerOrder()
    updateAllLayerVisibility()
    updateAllDataLayerVisibility()
    updateRouteVisibility()
    refreshLoading()
  })

  map.value.on('mousemove', (event) => {
    lastHoverPoint = { point: event.point, lngLat: event.lngLat }
    handleDataHover(event)
  })
  map.value.on('click', (event) => {
    if (['start', 'end'].includes(props.routePickMode)) {
      emit('route-map-click', {
        mode: props.routePickMode,
        coordinate: [Number(event.lngLat.lng.toFixed(6)), Number(event.lngLat.lat.toFixed(6))]
      })
      return
    }
    handleSimulatorClick(event)
  })
  map.value.on('mouseout', hideDataHoverPopup)
  map.value.on('dragstart', hideDataHoverPopup)
  map.value.on('zoomstart', hideDataHoverPopup)
  // Only the raster basemap drives the "loading tiles" status; data-source
  // updates (e.g. simulator playback writing GeoJSON every frame) must not
  // toggle it, otherwise the indicator flickers.
  map.value.on('sourcedata', (event) => {
    if (event.sourceId === basemapSourceId) refreshLoading()
  })
  map.value.on('idle', refreshLoading)
  map.value.on('error', (event) => {
    const message = event?.error?.message || '地圖繪製錯誤'
    if (message.includes('404')) {
      return
    }
    if (message.includes('Failed to fetch')) {
      status.value.error = '無法載入地圖圖磚，請檢查圖磚伺服器網址。'
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

// Shallow on purpose: writers replace the dict identity per change (see
// setLayerGeoJson), and the simulator feeds a frame every ~16ms during
// playback — a deep watch would re-traverse every feature of every loaded
// layer per frame.
watch(
  () => props.dataLayerGeoJson,
  () => {
    updateDataLayerGeoJson()
    refreshHoverFromData()
  }
)

watch(
  () => props.routeLineGeoJson,
  () => {
    updateRouteGeoJson()
  },
  { deep: true }
)

watch(
  () => props.routeStopGeoJson,
  () => {
    updateRouteGeoJson()
  },
  { deep: true }
)

watch(
  () => props.routeAnchorGeoJson,
  () => {
    updateRouteGeoJson()
  },
  { deep: true }
)

watch(
  () => props.routeLayerVisibility,
  () => {
    updateRouteVisibility()
  },
  { deep: true }
)

watch(
  () => props.routePickMode,
  () => {
    if (!map.value) return
    map.value.getCanvas().style.cursor = ['start', 'end'].includes(props.routePickMode) ? 'crosshair' : ''
  }
)

// Auto-follow: recenter on the simulator's current centroid (frame cadence).
// Updates arrive every rendered frame, so a restarted 600ms easeTo would sit
// forever in its slow-start phase and fight the render loop. Instead: a big
// jump (follow just enabled, or a seek teleported the vehicle) gets one
// uninterrupted ease; the per-frame small deltas use jumpTo, which is a cheap
// transform update — the interpolated vehicle motion supplies the smoothness.
let followEaseUntilReal = 0
watch(
  () => props.simulatorState?.followCenter,
  (center) => {
    if (!map.value || !props.simulatorState?.autoFollow || !Array.isArray(center)) return
    const nowReal = performance.now()
    if (nowReal < followEaseUntilReal) return // let the recenter ease finish
    const target = map.value.project({ lng: center[0], lat: center[1] })
    const current = map.value.project(map.value.getCenter())
    if (Math.hypot(target.x - current.x, target.y - current.y) > 100) {
      followEaseUntilReal = nowReal + 400
      map.value.easeTo({ center, duration: 400 })
    } else {
      map.value.jumpTo({ center })
    }
  }
)

// Single-entity trajectory overlay: a road-following line (dim = not yet
// travelled, bright = travelled so far), origin/destination markers, and a ring
// tracking the selected point's live position. All sit *beneath* the live data
// point icons so the moving vehicles stay on top.
const ensureSelectionLayers = () => {
  const m = map.value
  if (!m || !mapLoaded.value) return false

  // Insert beneath the first data point layer so icons render above the track.
  const pointLayerIds = getDataPointLayerIds(props.dataLayerState).filter((id) => m.getLayer(id))
  const beforeId = pointLayerIds[0]
  const addLayer = (def) => {
    if (m.getLayer(def.id)) return
    if (beforeId) m.addLayer(def, beforeId)
    else m.addLayer(def)
  }

  if (!m.getSource('sim-track-source')) {
    m.addSource('sim-track-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  if (!m.getSource('sim-track-traveled-source')) {
    m.addSource('sim-track-traveled-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  if (!m.getSource('sim-track-endpoints-source')) {
    m.addSource('sim-track-endpoints-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  if (!m.getSource('sim-selected-source')) {
    m.addSource('sim-selected-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }

  addLayer({
    id: 'sim-track-line-casing',
    type: 'line',
    source: 'sim-track-source',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#0b1220', 'line-width': 6, 'line-opacity': 0.55 }
  })
  addLayer({
    id: 'sim-track-line',
    type: 'line',
    source: 'sim-track-source',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#6f88aa', 'line-width': 3, 'line-opacity': 0.7 }
  })
  addLayer({
    id: 'sim-track-traveled',
    type: 'line',
    source: 'sim-track-traveled-source',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#f4c95d', 'line-width': 3.5, 'line-opacity': 0.95 }
  })
  addLayer({
    id: 'sim-track-endpoints',
    type: 'circle',
    source: 'sim-track-endpoints-source',
    paint: {
      'circle-radius': 5.5,
      'circle-color': ['match', ['get', 'role'], 'start', '#34d399', 'end', '#eb5757', '#f4c95d'],
      'circle-stroke-color': '#0b1220',
      'circle-stroke-width': 1.5
    }
  })
  addLayer({
    id: 'sim-selected-ring',
    type: 'circle',
    source: 'sim-selected-source',
    paint: {
      'circle-radius': 9,
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': '#f4c95d',
      'circle-stroke-width': 2.5,
      'circle-stroke-opacity': 0.95
    }
  })
  return true
}

const setSelectionSource = (sourceId, fc) => {
  if (!ensureSelectionLayers()) return
  const src = map.value.getSource(sourceId)
  if (src) src.setData(fc || { type: 'FeatureCollection', features: [] })
}

watch(
  () => props.simulatorState?.trackGeoJson,
  (fc) => setSelectionSource('sim-track-source', fc)
)

watch(
  () => props.simulatorState?.trackTraveledGeoJson,
  (fc) => setSelectionSource('sim-track-traveled-source', fc)
)

watch(
  () => props.simulatorState?.trackEndpointsGeoJson,
  (fc) => setSelectionSource('sim-track-endpoints-source', fc)
)

// The ring follows the selected entity's live position (simulatorState.selectedPos
// is re-synced every frame), so it tracks the moving point and disappears when
// the selection is cleared — never lingering at a stale spot during playback.
watch(
  () => props.simulatorState?.selectedPos,
  (coordinates) => {
    if (!ensureSelectionLayers()) return
    const src = map.value.getSource('sim-selected-source')
    if (!src) return
    src.setData(
      Array.isArray(coordinates)
        ? { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates } }] }
        : { type: 'FeatureCollection', features: [] }
    )
  }
)

// --- Route-plan playback: traveled/remaining route split + stop fading -------
//
// While simulating, the static route-line-layer is hidden and replaced by two
// shared layers fed per frame: the traveled portion (translucent vehicle color)
// and the remaining portion (solid). Stops already served fade to translucent
// via a rebuilt paint expression.
const ROUTE_STOP_OPACITY_DEFAULT = 0.92
let routeSimPaintApplied = false

// Base heat weight: the garbage volume at the stop, scaled so a typical stop
// (~500 kg) contributes weight 1 and huge aggregated cells saturate at 3.
const ROUTE_SIM_HEAT_BASE_WEIGHT = ['min', 3, ['/', ['to-number', ['get', 'demandKg']], 500]]

// Served stops stop contributing heat — their garbage has been collected.
const buildHeatWeightExpression = (progressMap) => {
  const branches = []
  for (const [vehicleId, info] of Object.entries(progressMap)) {
    branches.push(vehicleId, [
      'case',
      ['<', ['get', 'stopIndex'], Number(info.visitedStops) || 0],
      0,
      ROUTE_SIM_HEAT_BASE_WEIGHT
    ])
  }
  if (!branches.length) return ROUTE_SIM_HEAT_BASE_WEIGHT
  return ['match', ['get', 'vehicleId'], ...branches, ROUTE_SIM_HEAT_BASE_WEIGHT]
}

// Served stops (stopIndex below the vehicle's visited count) fade out.
const buildVisitedStopExpression = (progressMap, visitedValue, defaultValue) => {
  const branches = []
  for (const [vehicleId, info] of Object.entries(progressMap)) {
    branches.push(vehicleId, [
      'case',
      ['<', ['get', 'stopIndex'], Number(info.visitedStops) || 0],
      visitedValue,
      defaultValue
    ])
  }
  if (!branches.length) return defaultValue
  return ['match', ['get', 'vehicleId'], ...branches, defaultValue]
}

const setStopLayersVisibility = (m, visible) => {
  const visibility = visible ? 'visible' : 'none'
  if (m.getLayer('route-stop-layer')) m.setLayoutProperty('route-stop-layer', 'visibility', visibility)
  if (m.getLayer('route-stop-order-layer')) m.setLayoutProperty('route-stop-order-layer', 'visibility', visibility)
}

const resetRouteSimPaint = () => {
  const m = map.value
  if (!m || !routeSimPaintApplied) return
  routeSimPaintApplied = false
  if (m.getLayer('route-line-layer')) {
    m.setLayoutProperty(
      'route-line-layer',
      'visibility',
      props.routeLayerVisibility?.line === false ? 'none' : 'visible'
    )
  }
  setStopLayersVisibility(m, props.routeLayerVisibility?.stops !== false)
  if (m.getLayer('route-sim-heat-layer')) {
    m.setLayoutProperty('route-sim-heat-layer', 'visibility', 'none')
  }
  if (m.getLayer('route-stop-layer')) {
    m.setPaintProperty('route-stop-layer', 'circle-opacity', ROUTE_STOP_OPACITY_DEFAULT)
    m.setPaintProperty('route-stop-layer', 'circle-stroke-opacity', 1)
  }
  if (m.getLayer('route-stop-order-layer')) {
    m.setPaintProperty('route-stop-order-layer', 'text-opacity', 1)
  }
}

const applyRouteSimProgress = () => {
  const m = map.value
  if (!m || !mapLoaded.value) return
  const simulating = props.simulatorState?.active && props.simulatorState?.mode === 'route-plan'
  const progressMap = props.routeSimProgress || {}
  if (!simulating || !Object.keys(progressMap).length) {
    resetRouteSimPaint()
    return
  }
  routeSimPaintApplied = true

  // The traveled/remaining split layers replace the static route lines.
  if (m.getLayer('route-line-layer')) {
    m.setLayoutProperty('route-line-layer', 'visibility', 'none')
  }

  // Heat view swaps the stop dots for a heatmap whose weight drops to zero at
  // stops the truck has already served.
  const heatOn = props.simulatorState?.routeHeatmap === true
  if (m.getLayer('route-sim-heat-layer')) {
    m.setLayoutProperty('route-sim-heat-layer', 'visibility', heatOn ? 'visible' : 'none')
    if (heatOn) {
      m.setPaintProperty('route-sim-heat-layer', 'heatmap-weight', buildHeatWeightExpression(progressMap))
    }
  }
  setStopLayersVisibility(m, !heatOn && props.routeLayerVisibility?.stops !== false)

  if (m.getLayer('route-stop-layer')) {
    m.setPaintProperty(
      'route-stop-layer',
      'circle-opacity',
      buildVisitedStopExpression(progressMap, 0.25, ROUTE_STOP_OPACITY_DEFAULT)
    )
    m.setPaintProperty(
      'route-stop-layer',
      'circle-stroke-opacity',
      buildVisitedStopExpression(progressMap, 0.25, 1)
    )
  }
  if (m.getLayer('route-stop-order-layer')) {
    m.setPaintProperty(
      'route-stop-order-layer',
      'text-opacity',
      buildVisitedStopExpression(progressMap, 0.3, 1)
    )
  }
}

watch(
  () => props.routeSimProgress,
  () => applyRouteSimProgress()
)

watch(
  () => [props.simulatorState?.active, props.simulatorState?.mode, props.simulatorState?.routeHeatmap],
  () => applyRouteSimProgress()
)

// Simulated garbage-truck positions during route-plan playback: a truck sprite
// per vehicle (8-direction tcg-v2 set, picked by heading in `truckIconId`),
// with the vehicle id above in the vehicle's color. The traveled/remaining
// route split renders beneath the stop dots (see enforceLayerOrder) so stops
// stay clickable and visible on top of the lines.
const ROUTE_SIM_TRUCK_ICONS = Array.from({ length: 8 }, (_, index) => ({
  id: `tcg-v2-garbage-o0${index + 1}`,
  src: `/icons/tcg-v2/noGarbage_truck_o0${index + 1}.png`
}))

const ensureRouteSimLayers = () => {
  const m = map.value
  if (!m || !mapLoaded.value) return false
  let createdLayers = false
  // Idempotent: skips ids already registered by the live data layers.
  ensureIcons(m, ROUTE_SIM_TRUCK_ICONS).catch((error) => console.warn(error))
  if (!m.getSource('route-sim-source')) {
    m.addSource('route-sim-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  if (!m.getSource('route-sim-line-traveled-source')) {
    m.addSource('route-sim-line-traveled-source', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    })
  }
  if (!m.getSource('route-sim-line-remaining-source')) {
    m.addSource('route-sim-line-remaining-source', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] }
    })
  }
  if (!m.getSource('route-sim-heat-source')) {
    m.addSource('route-sim-heat-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  }
  if (!m.getLayer('route-sim-heat-layer')) {
    createdLayers = true
    m.addLayer({
      id: 'route-sim-heat-layer',
      type: 'heatmap',
      source: 'route-sim-heat-source',
      layout: { visibility: 'none' },
      paint: {
        'heatmap-weight': ROUTE_SIM_HEAT_BASE_WEIGHT,
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 14, 12, 26, 16, 44],
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 8, 0.8, 14, 1.4],
        'heatmap-opacity': 0.75
      }
    })
  }
  if (!m.getLayer('route-sim-line-traveled-layer')) {
    createdLayers = true
    m.addLayer({
      id: 'route-sim-line-traveled-layer',
      type: 'line',
      source: 'route-sim-line-traveled-source',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'vehicleColor'],
        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1.8, 11, 3.2, 16, 5.0],
        'line-opacity': 0.28
      }
    })
  }
  if (!m.getLayer('route-sim-line-remaining-layer')) {
    createdLayers = true
    m.addLayer({
      id: 'route-sim-line-remaining-layer',
      type: 'line',
      source: 'route-sim-line-remaining-source',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'vehicleColor'],
        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1.8, 11, 3.2, 16, 5.0],
        'line-opacity': 0.9
      }
    })
  }
  if (!m.getLayer('route-sim-vehicle-layer')) {
    createdLayers = true
    m.addLayer({
      id: 'route-sim-vehicle-layer',
      type: 'symbol',
      source: 'route-sim-source',
      layout: {
        'icon-image': ['get', 'truckIconId'],
        'icon-size': ['interpolate', ['linear'], ['zoom'], 6, 0.6, 12, 0.9, 16, 1.2],
        'icon-allow-overlap': true,
        'icon-ignore-placement': true
      }
    })
  }
  if (!m.getLayer('route-sim-vehicle-label-layer')) {
    createdLayers = true
    m.addLayer({
      id: 'route-sim-vehicle-label-layer',
      type: 'symbol',
      source: 'route-sim-source',
      layout: {
        'text-field': ['get', 'vehicleId'],
        'text-font': ['Open Sans Regular'],
        'text-size': 10,
        'text-offset': [0, -2.2],
        'text-anchor': 'bottom',
        'text-allow-overlap': true,
        'text-ignore-placement': true
      },
      paint: {
        // The truck sprite replaced the per-vehicle colored dot, so the label
        // carries the vehicle color for telling trucks apart.
        'text-color': ['get', 'vehicleColor'],
        'text-halo-color': '#0f1729',
        'text-halo-width': 1.4
      }
    })
  }
  // Newly added layers land on top of everything; re-assert the intended
  // stacking (sim route lines below stop dots, vehicle dots on top).
  if (createdLayers) enforceLayerOrder()
  return true
}

const setRouteSimSourceData = (sourceId, fc) => {
  if (!ensureRouteSimLayers()) return
  const src = map.value.getSource(sourceId)
  if (src) src.setData(fc || { type: 'FeatureCollection', features: [] })
}

// Route *simulation* overlays (moving trucks + progress lines + heat), fed per
// frame by useSimulator — distinct from the route *plan* layers above
// (routeLineGeoJson etc.), which show the solved static route. One watch per
// source on purpose: during playback only the vehicle points change every
// frame, so the heavier line/heat sources must not re-upload with them.
const bindRouteSimSource = (getter, sourceId) => watch(getter, (fc) => setRouteSimSourceData(sourceId, fc))
bindRouteSimSource(() => props.routeSimGeoJson, 'route-sim-source')
bindRouteSimSource(() => props.routeSimTraveledGeoJson, 'route-sim-line-traveled-source')
bindRouteSimSource(() => props.routeSimRemainingGeoJson, 'route-sim-line-remaining-source')
bindRouteSimSource(() => props.routeSimHeatGeoJson, 'route-sim-heat-source')

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
      <p class="legend-title">邊界</p>
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
        <p class="legend-title data-title">資料圖層</p>
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

      <template v-if="routeLegendItems.length">
        <p class="legend-title data-title">路線</p>
        <button
          v-for="item in routeLegendItems"
          :key="item.key"
          class="legend-row"
          :class="{ inactive: !item.active }"
          type="button"
          @click="emit('toggle-route-layer', item.key)"
        >
          <span class="legend-chip round" :style="{ backgroundColor: item.color }"></span>
          <span>{{ item.label }}</span>
        </button>

        <template v-if="routeVehicleLegendItems.length">
          <p class="legend-title vehicle-title">車輛</p>
          <button
            v-for="item in routeVehicleLegendItems"
            :key="item.key"
            class="legend-row"
            :class="{ inactive: !item.active }"
            type="button"
            @click="emit('toggle-route-layer', item.key)"
          >
            <span class="legend-chip round" :style="{ backgroundColor: item.color }"></span>
            <span>{{ item.label }}</span>
          </button>
        </template>
      </template>
    </div>

    <div v-if="status.loading || status.error" class="map-status-card" :class="{ error: status.error }">
      <p v-if="status.loading" class="status-row">載入地圖圖磚中...</p>
      <p v-else class="status-row">{{ status.error }}</p>
    </div>

    <SimulatorControlBar
      v-if="props.simulatorState?.active"
      :simulator-state="props.simulatorState"
      :simulator-speeds="props.simulatorSpeeds"
      @set-time="emit('simulator-set-time', $event)"
      @toggle-play="emit('simulator-toggle-play')"
      @set-speed="emit('simulator-set-speed', $event)"
      @step="emit('simulator-step', $event)"
      @toggle-smooth="emit('simulator-toggle-smooth')"
      @select-segment="emit('simulator-select-segment', $event)"
      @set-window="emit('simulator-set-window', $event)"
      @toggle-live="emit('simulator-toggle-live')"
      @toggle-route-heatmap="emit('simulator-toggle-route-heatmap')"
      @stop="emit('simulator-stop')"
    />

    <AnalyticsDrawer
      v-if="props.simulatorState?.active && props.simulatorState?.mode !== 'route-plan'"
      :simulator-state="props.simulatorState"
      :property-labels="simulatorPropertyLabels"
      @toggle-track="emit('simulator-toggle-track')"
      @toggle-follow="emit('simulator-toggle-follow')"
      @clear-selection="emit('simulator-select-feature', null)"
    />

    <RouteVehicleDrawer
      v-if="props.simulatorState?.active && props.simulatorState?.mode === 'route-plan' && props.routeSimSelectedVehicle"
      :simulator-state="props.simulatorState"
      :vehicle="props.routeSimSelectedVehicle"
      :capacity-kg="props.routeVehicleCapacityKg"
      @close="emit('simulator-select-feature', null)"
      @seek="emit('simulator-set-time', $event)"
      @toggle-follow="emit('simulator-toggle-follow')"
    />
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

.legend-title.vehicle-title {
  margin-top: 4px;
  font-size: 11px;
  color: #a6c4ea;
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
