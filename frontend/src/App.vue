<script setup>
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import TopToolbar from './components/TopToolbar.vue'
import MapCanvasShell from './components/MapCanvasShell.vue'
import { useBasemap } from './features/basemaps/useBasemap'
import { useDataLayers } from './features/data/useDataLayers'
import { useLayers } from './features/layers/useLayers'
import { useRanges } from './features/ranges/useRanges'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

const isSidebarCollapsed = ref(false)
const { basemapState, activeBasemap, setBasemap } = useBasemap()
const { layerState, toggleLayer, updateLayerStyle } = useLayers(API_BASE_URL)
const {
  rangeTree,
  selectedRangeIds,
  selectedRangeGeoJson,
  rangeNodeLoading,
  selectedRangeRequest,
  toggleRange,
  loadVillageStatZones
} = useRanges(API_BASE_URL)
const {
  dataLayerState,
  rangePointFilterEnabled,
  dataLayerGeoJson,
  dataLayerRuntime,
  dataAggregate,
  toggleDataLayer,
  setDataLayerMode,
  refreshDataLayerByKey,
  setRangePointFilterEnabled
} = useDataLayers(API_BASE_URL, selectedRangeGeoJson, selectedRangeRequest)
</script>

<template>
  <div class="map-tool" :class="{ collapsed: isSidebarCollapsed }">
    <Sidebar
      :layer-state="layerState"
      :basemap-state="basemapState"
      :range-tree="rangeTree"
      :data-layer-state="dataLayerState"
      :data-aggregate="dataAggregate"
      :data-layer-runtime="dataLayerRuntime"
      :range-point-filter-enabled="rangePointFilterEnabled"
      :selected-range-ids="selectedRangeIds"
      :range-node-loading="rangeNodeLoading"
      :collapsed="isSidebarCollapsed"
      @toggle-layer="toggleLayer"
      @update-layer-style="updateLayerStyle"
      @set-basemap="setBasemap"
      @toggle-range="toggleRange"
      @expand-range="loadVillageStatZones"
      @toggle-data-layer="toggleDataLayer"
      @set-data-layer-mode="setDataLayerMode"
      @refresh-data-layer="refreshDataLayerByKey"
      @set-range-point-filter-enabled="setRangePointFilterEnabled"
      @toggle-collapse="isSidebarCollapsed = !isSidebarCollapsed"
    />

    <main class="workspace">
      <TopToolbar />
      <MapCanvasShell
        :active-basemap="activeBasemap"
        :layer-state="layerState"
        :selected-range-geo-json="selectedRangeGeoJson"
        :data-layer-state="dataLayerState"
        :data-layer-geo-json="dataLayerGeoJson"
        @toggle-layer="toggleLayer"
        @toggle-data-layer="toggleDataLayer"
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
