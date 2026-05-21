<script setup>
import { onMounted, ref } from 'vue'
import L from 'leaflet'
import 'leaflet.vectorgrid'

const mapEl = ref(null)
const map = ref(null)
const TILE_SERVER = 'http://localhost:5000'
const layerState = ref({
  county: {
    label: '直轄市/縣市界線',
    layerName: 'county',
    url: `${TILE_SERVER}/tiles/county/{z}/{x}/{y}.pbf`,
    minZoom: 5,
    maxZoom: 9,
    active: true,
    layer: null
  },
  township: {
    label: '鄉鎮市區界線',
    layerName: 'township',
    url: `${TILE_SERVER}/tiles/township/{z}/{x}/{y}.pbf`,
    minZoom: 8,
    maxZoom: 12,
    active: false,
    layer: null
  },
  village: {
    label: '村里界圖',
    layerName: 'village',
    url: `${TILE_SERVER}/tiles/village/{z}/{x}/{y}.pbf`,
    minZoom: 12,
    maxZoom: 18,
    active: false,
    layer: null
  }
})
const status = ref({ loading: false, error: '' })

const LAYER_STYLES = {
  county: { color: '#1d4ed8', weight: 2, fill: true, fillColor: '#1d4ed8', fillOpacity: 0.08 },
  township: { color: '#0f766e', weight: 1.5, fill: true, fillColor: '#0f766e', fillOpacity: 0.06 },
  village: { color: '#7c2d12', weight: 1, fill: true, fillColor: '#7c2d12', fillOpacity: 0.05 }
}

const HOVER_STYLES = {
  county: { color: '#1d4ed8', weight: 2.5, fill: true, fillColor: '#1d4ed8', fillOpacity: 0.25 },
  township: { color: '#0f766e', weight: 2, fill: true, fillColor: '#0f766e', fillOpacity: 0.22 },
  village: { color: '#7c2d12', weight: 1.5, fill: true, fillColor: '#7c2d12', fillOpacity: 0.2 }
}

const getFeatureId = (feature) => {
  if (feature?.id !== undefined && feature?.id !== null) return feature.id
  const props = feature?.properties || {}
  const primaryKeys = ['id', 'ID', 'Id', 'OBJECTID', 'FID', 'OBJECT_ID', 'GID']
  for (const key of primaryKeys) {
    if (props[key] !== undefined && props[key] !== null) return props[key]
  }
  const entries = Object.keys(props)
    .sort()
    .map((key) => `${key}:${props[key]}`)
    .join('|')
  return entries || undefined
}

const createMap = () => {
  map.value = L.map(mapEl.value, {
    center: [23.6978, 120.9605],
    zoom: 7,
    maxZoom: 18,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map.value)
}

const createVectorLayer = (key) => {
  const entry = layerState.value[key]
  const layer = L.vectorGrid.protobuf(entry.url, {
    vectorTileLayerStyles: {
      [entry.layerName]: LAYER_STYLES[key]
    },
    minZoom: entry.minZoom,
    maxZoom: entry.maxZoom,
    interactive: true,
    getFeatureId
  })

  layer.on('loading', () => {
    status.value.loading = true
  })
  layer.on('load', () => {
    status.value.loading = false
  })
  layer.on('tileerror', (event) => {
    status.value.loading = false
    status.value.error = event.error?.message || 'Tile load error'
  })

  layer.on('mouseover', (event) => {
    const id = getFeatureId(event.layer?.feature || { properties: event.layer?.properties, id: event.layer?.id })
    if (!id) return
    layer.setFeatureStyle(id, HOVER_STYLES[key])
  })

  layer.on('mouseout', (event) => {
    const id = getFeatureId(event.layer?.feature || { properties: event.layer?.properties, id: event.layer?.id })
    if (!id) return
    layer.resetFeatureStyle(id)
  })

  return layer
}

const toggleLayer = async (key) => {
  const entry = layerState.value[key]
  entry.active = !entry.active
  if (entry.active) {
    if (!entry.layer) {
      entry.layer = createVectorLayer(key)
    }
    entry.layer.addTo(map.value)
  } else if (entry.layer) {
    map.value.removeLayer(entry.layer)
  }
}

onMounted(async () => {
  createMap()
  const countyLayer = createVectorLayer('county')
  layerState.value.county.layer = countyLayer
  countyLayer.addTo(map.value)
})
</script>

<template>
  <div class="page">
    <header class="hero">
      <div>
        <p class="eyebrow">Leaflet + GeoJSON</p>
        <h1>台灣行政界線圖層切換</h1>
        <p class="subtitle">三個開關，分別顯示直轄市/縣市、鄉鎮市區、村里界線。</p>
      </div>
      <div class="legend">
        <div class="legend-row">
          <span class="legend-swatch swatch-county"></span>
          <span>直轄市/縣市界線</span>
        </div>
        <div class="legend-row">
          <span class="legend-swatch swatch-township"></span>
          <span>鄉鎮市區界線</span>
        </div>
        <div class="legend-row">
          <span class="legend-swatch swatch-village"></span>
          <span>村里界圖</span>
        </div>
      </div>
    </header>

    <section class="controls">
      <button
        v-for="(entry, key) in layerState"
        :key="key"
        class="toggle"
        :class="{ active: entry.active }"
        type="button"
        @click="toggleLayer(key)"
      >
        <span class="toggle-dot"></span>
        <span>{{ entry.label }}</span>
      </button>
      <div class="status" v-if="status.loading">正在載入圖層…</div>
      <div class="status error" v-else-if="status.error">{{ status.error }}</div>
    </section>

    <section class="map-shell">
      <div ref="mapEl" class="map"></div>
    </section>
  </div>
</template>
