<script setup>
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import MapCanvasShell from './components/MapCanvasShell.vue'
import { useBasemap } from './features/basemaps/useBasemap'
import { useDataLayers } from './features/data/useDataLayers'
import { useLayers } from './features/layers/useLayers'
import { useRanges } from './features/ranges/useRanges'
import { useRoutePlanner } from './features/route/useRoutePlanner'
import { useSimulator } from './features/simulator/useSimulator'

// `??` (not `||`) so an explicit empty value means "same origin" (the nginx
// container reverse-proxies the API), while an unset var still defaults to the
// local dev backend.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000'

const isSidebarCollapsed = ref(false)
const { basemapState, activeBasemap, setBasemap } = useBasemap()
const { layerState, toggleLayer, updateLayerStyle } = useLayers(API_BASE_URL)
const {
  rangeTrees,
  selectedRangeIds,
  selectedRangeGeoJson,
  rangeNodeLoading,
  selectedRangeRequest,
  pickModeEnabled: rangePickModeEnabled,
  pickLevel: rangePickLevel,
  toggleRange,
  loadRangeChildren,
  toggleRangeByPoint,
  setPickModeEnabled: setRangePickModeEnabled,
  setPickLevel: setRangePickLevel
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
  setRangePointFilterEnabled,
  getSimulatorCandidates,
  enterSimulator,
  exitSimulator,
  setSimulatorGeoJson
} = useDataLayers(API_BASE_URL, selectedRangeGeoJson, selectedRangeRequest)
const {
  simulatorState,
  simulatorCandidates,
  simulatorSpeeds,
  routeSimGeoJson,
  routeSimLinesGeoJson,
  routeSimLineProgress,
  routeSimHeatGeoJson,
  routeSimProgress,
  selectedRouteVehicle,
  startRouteSimulation,
  toggleRouteHeatmap,
  selectSimulatorDataset,
  setSimulatorTime,
  toggleSimulatorPlay,
  setSimulatorSpeed,
  stepSimulatorFrame,
  toggleSimulatorSmooth,
  selectSimulatorSegment,
  setSimulatorWindow,
  toggleSimulatorLive,
  toggleSimulatorAutoFollow,
  selectSimulatorFeature,
  toggleSimulatorTrack,
  stopSimulator
} = useSimulator(API_BASE_URL, {
  getSimulatorCandidates,
  enterSimulator,
  exitSimulator,
  setSimulatorGeoJson
})
const {
  routeForm,
  routeRuntime,
  routeResult,
  routeSummary,
  routeRows,
  droppedRows,
  routeLayerVisibility,
  routeLineGeoJson,
  routeStopGeoJson,
  routeAnchorGeoJson,
  pickMode,
  setPickMode,
  setDepotCoord,
  clearResult,
  toggleRouteLayerVisibility,
  toggleRouteVehicleVisibility,
  solveRoute
} = useRoutePlanner(API_BASE_URL, selectedRangeRequest, selectedRangeGeoJson)

const updateRouteField = ({ key, value }) => {
  if (!key) return
  routeForm.value = {
    ...routeForm.value,
    [key]: value
  }
}

const handleMapDepotPick = ({ mode, coordinate }) => {
  setDepotCoord(mode, coordinate)
}

const handleSimulateRoutePlan = () => {
  startRouteSimulation(routeResult.value)
}

const handleToggleRouteLayer = (layerKey) => {
  if (typeof layerKey === 'string' && layerKey.startsWith('vehicle:')) {
    const vehicleId = layerKey.slice('vehicle:'.length)
    if (vehicleId) {
      toggleRouteVehicleVisibility(vehicleId)
    }
    return
  }
  toggleRouteLayerVisibility(layerKey)
}
</script>

<template>
  <div class="map-tool" :class="{ collapsed: isSidebarCollapsed }">
    <Sidebar
      :layer-state="layerState"
      :basemap-state="basemapState"
      :range-trees="rangeTrees"
      :data-layer-state="dataLayerState"
      :data-aggregate="dataAggregate"
      :data-layer-runtime="dataLayerRuntime"
      :route-form="routeForm"
      :route-runtime="routeRuntime"
      :route-summary="routeSummary"
      :route-rows="routeRows"
      :route-dropped-rows="droppedRows"
      :route-pick-mode="pickMode"
      :range-point-filter-enabled="rangePointFilterEnabled"
      :selected-range-ids="selectedRangeIds"
      :range-node-loading="rangeNodeLoading"
      :range-pick-mode-enabled="rangePickModeEnabled"
      :range-pick-level="rangePickLevel"
      :simulator-state="simulatorState"
      :simulator-candidates="simulatorCandidates"
      :simulator-speeds="simulatorSpeeds"
      :collapsed="isSidebarCollapsed"
      @toggle-layer="toggleLayer"
      @update-layer-style="updateLayerStyle"
      @set-basemap="setBasemap"
      @toggle-range="toggleRange"
      @expand-range="loadRangeChildren"
      @set-range-pick-mode-enabled="setRangePickModeEnabled"
      @set-range-pick-level="setRangePickLevel"
      @toggle-data-layer="toggleDataLayer"
      @set-data-layer-mode="setDataLayerMode"
      @refresh-data-layer="refreshDataLayerByKey"
      @set-range-point-filter-enabled="setRangePointFilterEnabled"
      @update-route-field="updateRouteField"
      @set-route-pick-mode="setPickMode"
      @solve-route="solveRoute"
      @clear-route="clearResult"
      @select-simulator-dataset="selectSimulatorDataset"
      @set-simulator-time="setSimulatorTime"
      @toggle-simulator-play="toggleSimulatorPlay"
      @set-simulator-speed="setSimulatorSpeed"
      @step-simulator="stepSimulatorFrame"
      @toggle-simulator-smooth="toggleSimulatorSmooth"
      @select-simulator-segment="selectSimulatorSegment"
      @simulate-route-plan="handleSimulateRoutePlan"
      @stop-simulator="stopSimulator"
      @toggle-collapse="isSidebarCollapsed = !isSidebarCollapsed"
    />

    <main class="workspace">
      <MapCanvasShell
        :active-basemap="activeBasemap"
        :layer-state="layerState"
        :selected-range-geo-json="selectedRangeGeoJson"
        :data-layer-state="dataLayerState"
        :data-layer-geo-json="dataLayerGeoJson"
        :route-line-geo-json="routeLineGeoJson"
        :route-stop-geo-json="routeStopGeoJson"
        :route-anchor-geo-json="routeAnchorGeoJson"
        :route-layer-visibility="routeLayerVisibility"
        :route-pick-mode="pickMode"
        :range-pick-mode-enabled="rangePickModeEnabled"
        :range-pick-level="rangePickLevel"
        :simulator-state="simulatorState"
        :simulator-speeds="simulatorSpeeds"
        :route-sim-geo-json="routeSimGeoJson"
        :route-sim-lines-geo-json="routeSimLinesGeoJson"
        :route-sim-line-progress="routeSimLineProgress"
        :route-sim-heat-geo-json="routeSimHeatGeoJson"
        :route-sim-progress="routeSimProgress"
        :route-sim-selected-vehicle="selectedRouteVehicle"
        :route-vehicle-capacity-kg="Number(routeForm.vehicleCapacityKg) || 0"
        @toggle-layer="toggleLayer"
        @toggle-data-layer="toggleDataLayer"
        @toggle-route-layer="handleToggleRouteLayer"
        @route-map-click="handleMapDepotPick"
        @range-map-click="toggleRangeByPoint"
        @simulator-set-time="setSimulatorTime"
        @simulator-toggle-play="toggleSimulatorPlay"
        @simulator-set-speed="setSimulatorSpeed"
        @simulator-step="stepSimulatorFrame"
        @simulator-toggle-smooth="toggleSimulatorSmooth"
        @simulator-select-segment="selectSimulatorSegment"
        @simulator-set-window="setSimulatorWindow($event.from, $event.to)"
        @simulator-toggle-live="toggleSimulatorLive"
        @simulator-toggle-route-heatmap="toggleRouteHeatmap"
        @simulator-toggle-follow="toggleSimulatorAutoFollow"
        @simulator-select-feature="selectSimulatorFeature"
        @simulator-toggle-track="toggleSimulatorTrack"
        @simulator-stop="stopSimulator"
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
