import { computed, ref } from 'vue'

export const createBasemapState = () => ({
  osm: {
    label: 'OpenStreetMap',
    detail: 'Street map',
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize: 256,
    attribution: '&copy; OpenStreetMap contributors',
    active: true
  },
  cartoVoyager: {
    label: 'Carto Voyager',
    detail: 'Colorful canvas',
    tiles: ['https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'],
    tileSize: 256,
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    active: false
  },
  cartoLight: {
    label: 'Carto Light',
    detail: 'Light canvas',
    tiles: ['https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'],
    tileSize: 256,
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    active: false
  },
  cartoDark: {
    label: 'Carto Dark',
    detail: 'Dark canvas',
    tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
    tileSize: 256,
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    active: false
  },
  esriSatellite: {
    label: 'Esri Satellite',
    detail: 'World imagery',
    tiles: ['https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    tileSize: 256,
    attribution: 'Source: Esri, Maxar, Earthstar Geographics',
    active: false
  }
})

export const getActiveBasemapEntry = (basemapState) => {
  const entries = Object.entries(basemapState || {})
  const activeEntry = entries.find(([, value]) => value?.active)
  if (activeEntry) {
    return { key: activeEntry[0], ...(activeEntry[1] || {}) }
  }
  if (!entries.length) return null
  return { key: entries[0][0], ...(entries[0][1] || {}) }
}

export const useBasemap = () => {
  const basemapState = ref(createBasemapState())

  const activeBasemap = computed(() => getActiveBasemapEntry(basemapState.value))

  const setBasemap = (key) => {
    if (!basemapState.value[key]) return
    for (const [entryKey, value] of Object.entries(basemapState.value)) {
      value.active = entryKey === key
    }
  }

  return {
    basemapState,
    activeBasemap,
    setBasemap
  }
}
