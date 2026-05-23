<script setup>
import { computed, onMounted, ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import TopToolbar from './components/TopToolbar.vue'
import MapCanvasShell from './components/MapCanvasShell.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

const layerState = ref({
  county: {
    label: '縣市界線',
    sourceId: 'county-source',
    layerId: 'county-line',
    sourceLayer: 'county',
    url: 'http://localhost:5000/tiles/county/{z}/{x}/{y}.pbf',
    color: '#2f7df4',
    maxNativeZoom: 9,
    minVisibleZoom: 5,
    active: true
  },
  township: {
    label: '鄉鎮市區界線',
    sourceId: 'township-source',
    layerId: 'township-line',
    sourceLayer: 'township',
    url: 'http://localhost:5000/tiles/township/{z}/{x}/{y}.pbf',
    color: '#27a693',
    maxNativeZoom: 12,
    minVisibleZoom: 8,
    active: true
  },
  village: {
    label: '村里界線',
    sourceId: 'village-source',
    layerId: 'village-line',
    sourceLayer: 'village',
    url: 'http://localhost:5000/tiles/village/{z}/{x}/{y}.pbf',
    color: '#d17827',
    maxNativeZoom: 14,
    minVisibleZoom: 12,
    active: true
  }
})

const rangeTree = ref([])
const selectedVillageCodes = ref([])
const isSidebarCollapsed = ref(false)

const toggleLayer = (key) => {
  const entry = layerState.value[key]
  if (!entry) return
  entry.active = !entry.active
}

const getTownVillageCodes = (town) =>
  (town?.villages || []).map((village) => village.villageCode).filter(Boolean)

const getCountyVillageCodes = (county) =>
  (county?.townships || []).flatMap((town) => getTownVillageCodes(town))

const toggleVillage = (payload) => {
  const villageCode = payload?.villageCode
  if (!villageCode) return

  const current = new Set(selectedVillageCodes.value)
  if (current.has(villageCode)) {
    current.delete(villageCode)
  } else {
    current.add(villageCode)
  }
  selectedVillageCodes.value = [...current]
}

const toggleTown = (townCode) => {
  const town = rangeTree.value.flatMap((county) => county.townships || []).find((row) => row.townCode === townCode)
  if (!town) return

  const villageCodes = getTownVillageCodes(town)
  if (!villageCodes.length) return

  const current = new Set(selectedVillageCodes.value)
  const isAllSelected = villageCodes.every((code) => current.has(code))

  for (const code of villageCodes) {
    if (isAllSelected) {
      current.delete(code)
    } else {
      current.add(code)
    }
  }

  selectedVillageCodes.value = [...current]
}

const toggleCounty = (countyCode) => {
  const county = rangeTree.value.find((row) => row.countyCode === countyCode)
  if (!county) return

  const villageCodes = getCountyVillageCodes(county)
  if (!villageCodes.length) return

  const current = new Set(selectedVillageCodes.value)
  const isAllSelected = villageCodes.every((code) => current.has(code))

  for (const code of villageCodes) {
    if (isAllSelected) {
      current.delete(code)
    } else {
      current.add(code)
    }
  }

  selectedVillageCodes.value = [...current]
}

const normalizeRangeTree = (payload) => {
  const counties = Array.isArray(payload?.counties) ? payload.counties : []
  return counties.map((county) => ({
    countyId: county?.countyId || '',
    countyCode: county?.countyCode || '',
    countyName: county?.countyName || county?.countyEng || county?.countyCode || '未知縣市',
    countyEng: county?.countyEng || '',
    townships: Array.isArray(county?.townships)
      ? county.townships.map((town) => ({
          townId: town?.townId || '',
          townCode: town?.townCode || '',
          townName: town?.townName || town?.townEng || town?.townCode || '未知鄉鎮',
          townEng: town?.townEng || '',
          villages: Array.isArray(town?.villages)
            ? town.villages.map((village) => ({
                villageCode: village?.villageCode || '',
                villageName: village?.villageName || village?.villageEng || village?.villageCode || '未知村里',
                villageEng: village?.villageEng || ''
              }))
            : []
        }))
      : []
  }))
}

const selectedTownCodes = computed(() => {
  const selectedVillageSet = new Set(selectedVillageCodes.value)
  const result = []

  for (const county of rangeTree.value) {
    for (const town of county.townships || []) {
      const villageCodes = getTownVillageCodes(town)
      if (!villageCodes.length) continue
      if (villageCodes.every((code) => selectedVillageSet.has(code))) {
        result.push(town.townCode)
      }
    }
  }

  return result
})

const loadRangesTree = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/regions/tree`)
    if (!response.ok) {
      throw new Error(`Failed to load regions tree: ${response.status}`)
    }

    const payload = await response.json()
    const tree = normalizeRangeTree(payload)
    rangeTree.value = tree

    const availableVillageCodes = new Set(
      tree.flatMap((county) => getCountyVillageCodes(county)).filter(Boolean)
    )

    selectedVillageCodes.value = selectedVillageCodes.value.filter((code) => availableVillageCodes.has(code))
  } catch (error) {
    console.error(error)
    rangeTree.value = []
    selectedVillageCodes.value = []
  }
}

onMounted(() => {
  loadRangesTree()
})
</script>

<template>
  <div class="map-tool" :class="{ collapsed: isSidebarCollapsed }">
    <Sidebar
      :layer-state="layerState"
      :range-tree="rangeTree"
      :selected-village-codes="selectedVillageCodes"
      :collapsed="isSidebarCollapsed"
      @toggle-layer="toggleLayer"
      @toggle-county="toggleCounty"
      @toggle-town="toggleTown"
      @toggle-village="toggleVillage"
      @toggle-collapse="isSidebarCollapsed = !isSidebarCollapsed"
    />

    <main class="workspace">
      <TopToolbar />
      <MapCanvasShell
        :layer-state="layerState"
        :selected-town-codes="selectedTownCodes"
        :selected-village-codes="selectedVillageCodes"
        @toggle-layer="toggleLayer"
      />
    </main>
  </div>
</template>

<style scoped>
.map-tool {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 320px 1fr;
  transition: grid-template-columns 260ms cubic-bezier(0.4, 0, 0.2, 1);
  background: #0b1220;
  color: #eaf1ff;
  font-family: Inter, 'Noto Sans TC', sans-serif;
}

.map-tool.collapsed {
  grid-template-columns: 84px 1fr;
}

.workspace {
  background: #0f1b2d;
  padding: 16px;
  display: grid;
  gap: 12px;
}

@media (max-width: 1100px) {
  .map-tool {
    grid-template-columns: 1fr;
  }

  .map-tool.collapsed {
    grid-template-columns: 1fr;
  }
}
</style>
