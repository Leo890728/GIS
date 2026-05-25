<script setup>
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import TopToolbar from './components/TopToolbar.vue'
import MapCanvasShell from './components/MapCanvasShell.vue'
import { useLayers } from './features/layers/useLayers'
import { useRanges } from './features/ranges/useRanges'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

const isSidebarCollapsed = ref(false)
const { layerState, toggleLayer } = useLayers(API_BASE_URL)
const { rangeTree, selectedRangeIds, selectedRangeGeoJson, toggleRange } = useRanges(API_BASE_URL)
</script>

<template>
  <div class="map-tool" :class="{ collapsed: isSidebarCollapsed }">
    <Sidebar
      :layer-state="layerState"
      :range-tree="rangeTree"
      :selected-range-ids="selectedRangeIds"
      :collapsed="isSidebarCollapsed"
      @toggle-layer="toggleLayer"
      @toggle-range="toggleRange"
      @toggle-collapse="isSidebarCollapsed = !isSidebarCollapsed"
    />

    <main class="workspace">
      <TopToolbar />
      <MapCanvasShell
        :layer-state="layerState"
        :selected-range-geo-json="selectedRangeGeoJson"
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
