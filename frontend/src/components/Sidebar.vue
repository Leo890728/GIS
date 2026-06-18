<script setup>
import { ref } from 'vue'
import {
  Circle,
  Database,
  Hand,
  History,
  Navigation,
  MousePointer2,
  PanelLeftClose,
  PanelLeftOpen,
  Pentagon,
  Slash,
  Square
} from 'lucide-vue-next'
import DataPanel from '../features/data/DataPanel.vue'
import BasemapPanel from '../features/basemaps/BasemapPanel.vue'
import LayerPanel from '../features/layers/LayerPanel.vue'
import RangePanel from '../features/ranges/RangePanel.vue'
import RoutePanel from '../features/route/RoutePanel.vue'
import SimulatorPanel from '../features/simulator/SimulatorPanel.vue'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  },
  basemapState: {
    type: Object,
    required: true
  },
  rangeTree: {
    type: Array,
    required: true
  },
  dataLayerState: {
    type: Object,
    required: true
  },
  dataAggregate: {
    type: Object,
    required: true
  },
  dataLayerRuntime: {
    type: Object,
    required: true
  },
  routeForm: {
    type: Object,
    required: true
  },
  routeRuntime: {
    type: Object,
    required: true
  },
  routeSummary: {
    type: Object,
    required: true
  },
  routeRows: {
    type: Array,
    required: true
  },
  routeDroppedRows: {
    type: Array,
    required: true
  },
  routePickMode: {
    type: String,
    default: ''
  },
  rangePointFilterEnabled: {
    type: Boolean,
    default: false
  },
  selectedRangeIds: {
    type: Array,
    required: true
  },
  rangeNodeLoading: {
    type: Object,
    default: () => ({})
  },
  simulatorState: {
    type: Object,
    required: true
  },
  simulatorCandidates: {
    type: Array,
    default: () => []
  },
  simulatorSpeeds: {
    type: Array,
    default: () => [1, 10, 30, 60]
  },
  collapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'toggle-layer',
  'update-layer-style',
  'set-basemap',
  'toggle-range',
  'expand-range',
  'toggle-data-layer',
  'set-data-layer-mode',
  'refresh-data-layer',
  'set-range-point-filter-enabled',
  'toggle-collapse',
  'update-route-field',
  'set-route-pick-mode',
  'solve-route',
  'clear-route',
  'select-simulator-dataset',
  'set-simulator-time',
  'toggle-simulator-play',
  'set-simulator-speed',
  'step-simulator',
  'toggle-simulator-smooth',
  'stop-simulator'
])

const activeMode = ref('ranges')

const modeLabels = {
  basemap: 'Basemap',
  layers: 'Boundary',
  ranges: 'Ranges',
  route: 'Route',
  data: 'Data',
  simulator: 'Simulator'
}

const openMode = (mode) => {
  activeMode.value = mode
  if (props.collapsed) {
    emit('toggle-collapse')
  }
}

const drawingTools = [
  [
    { key: 'draw-box', label: 'Draw Box', icon: MousePointer2, active: false },
    { key: 'edit', label: 'Edit', icon: Hand, active: false }
  ],
  [
    { key: 'lasso', label: 'Lasso', icon: Slash, active: false },
    { key: 'polygon', label: 'Polygon', icon: Pentagon, active: true }
  ],
  [
    { key: 'rect-area', label: 'Rect Area', icon: Square, active: false },
    { key: 'circle-area', label: 'Circle Area', icon: Circle, active: false }
  ]
]
</script>

<template>
  <aside class="sidebar" :class="{ collapsed: props.collapsed }">
    <header class="sidebar-header">
      <h2 v-if="!props.collapsed">{{ modeLabels[activeMode] }}</h2>
      <button
        class="icon-button"
        type="button"
        :aria-label="props.collapsed ? 'Expand panel' : 'Collapse panel'"
        @click="emit('toggle-collapse')"
      >
        <PanelLeftOpen v-if="props.collapsed" :size="16" />
        <PanelLeftClose v-else :size="16" />
      </button>
    </header>

    <div v-if="props.collapsed" class="collapsed-body">
      <div class="sidebar-divider"></div>

      <div class="compact-mode-switch">
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'basemap' }"
          type="button"
          :aria-pressed="activeMode === 'basemap'"
          @click="openMode('basemap')"
        >
          <Circle :size="14" />
          <span>Basemap</span>
        </button>
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'layers' }"
          type="button"
          :aria-pressed="activeMode === 'layers'"
          @click="openMode('layers')"
        >
          <Square :size="14" />
          <span>Boundary</span>
        </button>
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'ranges' }"
          type="button"
          :aria-pressed="activeMode === 'ranges'"
          @click="openMode('ranges')"
        >
          <Pentagon :size="14" />
          <span>Ranges</span>
        </button>
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'data' }"
          type="button"
          :aria-pressed="activeMode === 'data'"
          @click="openMode('data')"
        >
          <Database :size="14" />
          <span>Data</span>
        </button>
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'route' }"
          type="button"
          :aria-pressed="activeMode === 'route'"
          @click="openMode('route')"
        >
          <Navigation :size="14" />
          <span>Route</span>
        </button>
        <button
          class="compact-mode-btn"
          :class="{ active: activeMode === 'simulator' }"
          type="button"
          :aria-pressed="activeMode === 'simulator'"
          @click="openMode('simulator')"
        >
          <History :size="14" />
          <span>Simulator</span>
        </button>
      </div>
    </div>

    <template v-else>
      <div class="mode-switch">
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'basemap' }"
          type="button"
          :aria-pressed="activeMode === 'basemap'"
          @click="activeMode = 'basemap'"
        >
          Basemap
        </button>
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'layers' }"
          type="button"
          :aria-pressed="activeMode === 'layers'"
          @click="activeMode = 'layers'"
        >
          Boundary
        </button>
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'ranges' }"
          type="button"
          :aria-pressed="activeMode === 'ranges'"
          @click="activeMode = 'ranges'"
        >
          Ranges
        </button>
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'route' }"
          type="button"
          :aria-pressed="activeMode === 'route'"
          @click="activeMode = 'route'"
        >
          Route
        </button>
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'data' }"
          type="button"
          :aria-pressed="activeMode === 'data'"
          @click="activeMode = 'data'"
        >
          Data
        </button>
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'simulator' }"
          type="button"
          :aria-pressed="activeMode === 'simulator'"
          @click="activeMode = 'simulator'"
        >
          Simulator
        </button>
      </div>

      <BasemapPanel
        v-if="activeMode === 'basemap'"
        :basemap-state="basemapState"
        @set-basemap="emit('set-basemap', $event)"
      />

      <LayerPanel
        v-else-if="activeMode === 'layers'"
        :layer-state="layerState"
        @toggle-layer="emit('toggle-layer', $event)"
        @update-layer-style="emit('update-layer-style', $event)"
      />

      <RangePanel
        v-else-if="activeMode === 'ranges'"
        :range-tree="rangeTree"
        :selected-range-ids="selectedRangeIds"
        :range-node-loading="rangeNodeLoading"
        @toggle-range="emit('toggle-range', $event)"
        @expand-range="emit('expand-range', $event)"
      />

      <RoutePanel
        v-else-if="activeMode === 'route'"
        :route-form="routeForm"
        :route-runtime="routeRuntime"
        :route-summary="routeSummary"
        :route-rows="routeRows"
        :dropped-rows="routeDroppedRows"
        :pick-mode="routePickMode"
        :selected-range-count="selectedRangeIds.length"
        @update-route-field="emit('update-route-field', $event)"
        @set-pick-mode="emit('set-route-pick-mode', $event)"
        @solve-route="emit('solve-route')"
        @clear-route="emit('clear-route')"
      />

      <SimulatorPanel
        v-else-if="activeMode === 'simulator'"
        :simulator-state="simulatorState"
        :simulator-candidates="simulatorCandidates"
        :simulator-speeds="simulatorSpeeds"
        @select-dataset="emit('select-simulator-dataset', $event)"
        @set-time="emit('set-simulator-time', $event)"
        @toggle-play="emit('toggle-simulator-play')"
        @set-speed="emit('set-simulator-speed', $event)"
        @step="emit('step-simulator', $event)"
        @toggle-smooth="emit('toggle-simulator-smooth')"
        @stop="emit('stop-simulator')"
      />

      <DataPanel
        v-else
        :data-layer-state="dataLayerState"
        :data-aggregate="dataAggregate"
        :data-layer-runtime="dataLayerRuntime"
        :range-point-filter-enabled="rangePointFilterEnabled"
        :selected-range-count="selectedRangeIds.length"
        @toggle-data-layer="emit('toggle-data-layer', $event)"
        @set-data-layer-mode="emit('set-data-layer-mode', $event)"
        @refresh-data-layer="emit('refresh-data-layer', $event)"
        @set-range-point-filter-enabled="emit('set-range-point-filter-enabled', $event)"
      />

      <section v-if="activeMode === 'ranges'" class="tools-panel">
        <h3>Range Drawing Tools</h3>
        <div class="tools-grid">
          <div v-for="row in drawingTools" :key="row[0].key" class="tool-row">
            <button
              v-for="tool in row"
              :key="tool.key"
              class="tool-btn"
              :class="{ active: tool.active }"
              type="button"
            >
              <span class="tool-icon" aria-hidden="true">
                <component :is="tool.icon" :size="16" class="tool-icon-svg" />
              </span>
              <span>{{ tool.label }}</span>
            </button>
          </div>
        </div>
      </section>
    </template>
  </aside>
</template>

<style>
.sidebar {
  background: #111a2b;
  border-right: 1px solid #2f4668;
  padding: 20px 16px;
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: 12px;
  transition:
    padding 260ms cubic-bezier(0.4, 0, 0.2, 1),
    gap 260ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed {
  padding: 20px 10px;
  gap: 16px;
}

.collapsed-body {
  display: grid;
  gap: 16px;
}

.sidebar-divider {
  width: 100%;
  height: 1px;
  background: #2f4668;
}

.compact-mode-switch {
  display: grid;
  gap: 10px;
}

.compact-mode-btn {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #bfd3f2;
  font-size: 9px;
  font-weight: 600;
  padding: 8px 6px;
  display: grid;
  justify-items: center;
  gap: 4px;
}

.compact-mode-btn.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sidebar-header,
.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar.collapsed .sidebar-header {
  justify-content: center;
}

.sidebar.collapsed .icon-button {
  background: #2a4d7a;
}

.region-row {
  display: flex;
  align-items: center;
}

.region-toggle {
  width: 100%;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 22px;
}

.icon-button {
  width: 38px;
  height: 34px;
  border: 0;
  border-radius: 8px;
  background: #223652;
  color: #d6e4ff;
  display: grid;
  place-items: center;
  transition:
    background-color 220ms ease,
    color 220ms ease;
}

.icon-button svg {
  transition: transform 260ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed .icon-button svg {
  transform: rotate(180deg);
}

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-items: start;
  gap: 8px;
}

.mode-btn {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 600;
  padding: 6px 10px;
}

.mode-btn.active {
  color: #eaf4ff;
  background: #2a4d7a;
  border-color: #5fa3e3;
  font-weight: 700;
}

.ranges-panel,
.layers-panel,
.data-panel {
  display: grid;
  gap: 6px;
}

.panel-title-row h3,
.tools-panel h3 {
  margin: 0;
  font-size: 14px;
}

.count-badge {
  background: #1e314d;
  border: 1px solid #3d5f8a;
  border-radius: 999px;
  color: #bfd3f2;
  font-size: 9px;
  font-weight: 600;
  padding: 3px 8px;
}

.region-card {
  border-radius: 8px;
  border: 1px solid #2f4668;
  background: #16243a;
  padding: 7px 8px;
}

.region-card.expanded {
  background: #1e314d;
  border-color: #3d5f8a;
}

.region-label-wrap {
  display: grid;
  gap: 2px;
  justify-items: start;
  margin-right: auto;
  margin-left: 8px;
}

.region-name {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  color: #e1ebff;
}

.region-name.sub {
  font-size: 10px;
  font-weight: 600;
}

.region-meta {
  margin: 0;
  color: #9fb7da;
  font-size: 9px;
}

.range-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  border: 1px solid rgb(255 255 255 / 30%);
  flex-shrink: 0;
}

.check-box {
  width: 14px;
  height: 14px;
  border: 1px solid #4a5e7a;
  border-radius: 3px;
  background: #223652;
  color: #eaf4ff;
  display: grid;
  place-items: center;
  padding: 0;
}

.check-box.selected {
  border-color: #6ea9e8;
  background: #2a4d7a;
}

.check-box.partial {
  border-color: #6ea9e8;
  background: #2a4d7a;
}

.county-list {
  margin-top: 6px;
  display: grid;
  gap: 6px;
  max-height: 420px;
  overflow: auto;
  padding-right: 4px;
}

.county-card,
.township-card,
.range-node-leaf {
  border: 1px solid #2a3a54;
  border-radius: 8px;
  background: #1a2940;
  padding: 6px;
}

.county-row,
.township-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.range-label-btn,
.range-leaf-btn {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  width: 100%;
  display: flex;
  align-items: center;
  text-align: left;
}

.range-children {
  margin-top: 6px;
  display: grid;
  gap: 6px;
}

.range-children.nested {
  margin-left: 18px;
}

.district-row {
  border: 1px solid #2a3a54;
  border-radius: 8px;
  background: #1a2940;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
}

.district-toggle {
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.district-row.off,
.range-leaf-btn.off {
  border-color: #25374e;
  background: #15263c;
}

.more,
.caret {
  color: #88a4c8;
  flex-shrink: 0;
  margin-left: auto;
}

.tools-panel {
  display: grid;
  gap: 10px;
  margin-top: auto;
}

.tools-grid,
.tool-row {
  display: grid;
  gap: 8px;
}

.tool-row {
  grid-template-columns: 1fr 1fr;
}

.tool-btn {
  border-radius: 10px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #d6e6ff;
  display: grid;
  justify-items: center;
  gap: 4px;
  padding: 8px;
  font-size: 11px;
  font-weight: 600;
}

.tool-btn.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
  font-weight: 700;
}

.tool-icon {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 20px;
  border-radius: 6px;
  background: rgba(207, 227, 255, 0.1);
}

.tool-icon-svg {
  display: block;
}

@media (max-width: 1100px) {
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #2f4668;
  }

  .tools-panel {
    margin-top: 0;
  }
}

@media (max-width: 640px) {
  .tool-row {
    grid-template-columns: 1fr;
  }
}
</style>
