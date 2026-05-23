<script setup>
import { computed, ref } from 'vue'
import {
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  Ellipsis,
  Hand,
  Minus,
  MousePointer2,
  PanelLeftClose,
  PanelLeftOpen,
  Pentagon,
  Slash,
  Square
} from 'lucide-vue-next'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  },
  rangeTree: {
    type: Array,
    required: true
  },
  selectedVillageCodes: {
    type: Array,
    required: true
  },
  collapsed: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-layer', 'toggle-county', 'toggle-town', 'toggle-village', 'toggle-collapse'])

const activeMode = ref('ranges')
const expandedCountyCodes = ref([])
const expandedTownCodes = ref([])

const selectedVillageCodeSet = computed(() => new Set(props.selectedVillageCodes))

const getTownVillageCodes = (town) =>
  (town?.villages || []).map((village) => village.villageCode).filter(Boolean)

const getCountyVillageCodes = (county) =>
  (county?.townships || []).flatMap((town) => getTownVillageCodes(town))

const totalVillageCount = computed(() => props.rangeTree.reduce((total, county) => total + getCountyVillageCodes(county).length, 0))
const selectedVillageCount = computed(() => props.selectedVillageCodes.length)

const layerDetailMap = {
  county: 'County Boundary',
  township: 'Township Boundary',
  village: 'Village Boundary'
}

const layerItems = computed(() =>
  Object.entries(props.layerState).map(([key, value]) => ({
    key,
    name: value.label,
    detail: layerDetailMap[key] || value.sourceLayer,
    enabled: value.active
  }))
)

const activeLayerCount = computed(() => layerItems.value.filter((item) => item.enabled).length)

const isCountyExpanded = (countyCode) => expandedCountyCodes.value.includes(countyCode)
const isTownExpanded = (townCode) => expandedTownCodes.value.includes(townCode)

const toggleCountyExpand = (countyCode) => {
  expandedCountyCodes.value = expandedCountyCodes.value.includes(countyCode)
    ? expandedCountyCodes.value.filter((code) => code !== countyCode)
    : [...expandedCountyCodes.value, countyCode]
}

const toggleTownExpand = (townCode) => {
  expandedTownCodes.value = expandedTownCodes.value.includes(townCode)
    ? expandedTownCodes.value.filter((code) => code !== townCode)
    : [...expandedTownCodes.value, townCode]
}

const isVillageSelected = (villageCode) => selectedVillageCodeSet.value.has(villageCode)

const townSelectedVillageCount = (town) => getTownVillageCodes(town).filter((code) => selectedVillageCodeSet.value.has(code)).length

const isTownFullySelected = (town) => {
  const codes = getTownVillageCodes(town)
  return codes.length > 0 && codes.every((code) => selectedVillageCodeSet.value.has(code))
}

const isTownPartiallySelected = (town) => {
  const selected = townSelectedVillageCount(town)
  return selected > 0 && !isTownFullySelected(town)
}

const countySelectedVillageCount = (county) => getCountyVillageCodes(county).filter((code) => selectedVillageCodeSet.value.has(code)).length

const isCountyFullySelected = (county) => {
  const codes = getCountyVillageCodes(county)
  return codes.length > 0 && codes.every((code) => selectedVillageCodeSet.value.has(code))
}

const isCountyPartiallySelected = (county) => {
  const selected = countySelectedVillageCount(county)
  return selected > 0 && !isCountyFullySelected(county)
}

const toggleLayer = (key) => {
  emit('toggle-layer', key)
}

const toggleCounty = (countyCode) => {
  emit('toggle-county', countyCode)
}

const toggleTown = (townCode) => {
  emit('toggle-town', townCode)
}

const toggleVillage = (townCode, villageCode) => {
  emit('toggle-village', { townCode, villageCode })
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
      <h2 v-if="!props.collapsed">{{ activeMode === 'layers' ? 'Layers' : 'Ranges' }}</h2>
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
          :class="{ active: activeMode === 'layers' }"
          type="button"
          :aria-pressed="activeMode === 'layers'"
          @click="openMode('layers')"
        >
          <Square :size="14" />
          <span>Layers</span>
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
      </div>
    </div>

    <template v-else>
      <div class="mode-switch">
        <button
          class="mode-btn"
          :class="{ active: activeMode === 'layers' }"
          type="button"
          :aria-pressed="activeMode === 'layers'"
          @click="activeMode = 'layers'"
        >
          Layers
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
      </div>

      <section v-if="activeMode === 'layers'" class="layers-panel">
        <div class="panel-title-row">
          <h3>Map Layers</h3>
          <span class="count-badge">{{ activeLayerCount }} active</span>
        </div>

        <article v-for="layer in layerItems" :key="layer.key" class="region-card expanded">
          <button class="region-row region-toggle" type="button" :aria-pressed="layer.enabled" @click="toggleLayer(layer.key)">
            <div class="check-box" :class="{ selected: layer.enabled }">
              <Check v-if="layer.enabled" :size="10" />
            </div>
            <div class="region-label-wrap">
              <p class="region-name">{{ layer.name }}</p>
              <p class="region-meta">{{ layer.detail }}</p>
            </div>
          </button>
        </article>
      </section>

      <section v-else class="ranges-panel">
        <div class="panel-title-row">
          <h3>Ranges</h3>
          <span class="count-badge">{{ selectedVillageCount }} / {{ totalVillageCount }} selected</span>
        </div>

        <article class="region-card expanded">
          <header class="region-row">
            <div class="check-box selected">
              <Minus :size="10" />
            </div>
            <div class="region-label-wrap">
              <p class="region-name">全區域</p>
              <p class="region-meta">{{ selectedVillageCount }}/{{ totalVillageCount }} selected</p>
            </div>
            <ChevronDown class="caret" :size="14" />
          </header>

          <div class="county-list">
            <article v-for="county in rangeTree" :key="county.countyCode || county.countyName" class="county-card">
              <div class="county-row">
                <button
                  class="check-box county-toggle"
                  type="button"
                  :class="{ selected: isCountyFullySelected(county), partial: isCountyPartiallySelected(county) }"
                  :aria-pressed="isCountyFullySelected(county)"
                  @click="toggleCounty(county.countyCode)"
                >
                  <Check v-if="isCountyFullySelected(county)" :size="10" />
                  <Minus v-else-if="isCountyPartiallySelected(county)" :size="10" />
                </button>

                <button class="county-label-btn" type="button" @click="toggleCountyExpand(county.countyCode)">
                  <div class="region-label-wrap">
                    <p class="region-name">{{ county.countyName }}</p>
                    <p class="region-meta">{{ countySelectedVillageCount(county) }}/{{ getCountyVillageCodes(county).length }} 村里</p>
                  </div>
                  <ChevronDown v-if="isCountyExpanded(county.countyCode)" class="caret" :size="14" />
                  <ChevronRight v-else class="caret" :size="14" />
                </button>
              </div>

              <div v-if="isCountyExpanded(county.countyCode)" class="township-list">
                <article v-for="town in county.townships || []" :key="town.townCode || town.townName" class="township-card">
                  <div class="township-row">
                    <button
                      class="check-box township-toggle"
                      type="button"
                      :class="{ selected: isTownFullySelected(town), partial: isTownPartiallySelected(town) }"
                      :aria-pressed="isTownFullySelected(town)"
                      @click="toggleTown(town.townCode)"
                    >
                      <Check v-if="isTownFullySelected(town)" :size="10" />
                      <Minus v-else-if="isTownPartiallySelected(town)" :size="10" />
                    </button>

                    <button class="town-label-btn" type="button" @click="toggleTownExpand(town.townCode)">
                      <div class="region-label-wrap">
                        <p class="region-name sub">{{ town.townName }}</p>
                        <p class="region-meta">{{ townSelectedVillageCount(town) }}/{{ getTownVillageCodes(town).length }} 村里</p>
                      </div>
                      <ChevronDown v-if="isTownExpanded(town.townCode)" class="caret" :size="14" />
                      <ChevronRight v-else class="caret" :size="14" />
                    </button>
                  </div>

                  <div v-if="isTownExpanded(town.townCode)" class="village-list">
                    <button
                      v-for="village in town.villages || []"
                      :key="village.villageCode || village.villageName"
                      class="district-row district-toggle"
                      type="button"
                      :aria-pressed="isVillageSelected(village.villageCode)"
                      :class="{ off: !isVillageSelected(village.villageCode) }"
                      @click="toggleVillage(town.townCode, village.villageCode)"
                    >
                      <div class="check-box" :class="{ selected: isVillageSelected(village.villageCode) }">
                        <Check v-if="isVillageSelected(village.villageCode)" :size="10" />
                      </div>
                      <div class="region-label-wrap">
                        <p class="region-name sub">{{ village.villageName }}</p>
                        <p class="region-meta">{{ village.villageCode || 'N/A' }}</p>
                      </div>
                      <Ellipsis class="more" :size="14" />
                    </button>
                  </div>
                </article>
              </div>
            </article>
          </div>
        </article>
      </section>

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

<style scoped>
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

.icon-button :deep(svg) {
  transition: transform 260ms cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar.collapsed .icon-button :deep(svg) {
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
.layers-panel {
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
.township-card {
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

.county-label-btn,
.town-label-btn {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  width: 100%;
  display: flex;
  align-items: center;
  text-align: left;
}

.township-list {
  margin-top: 6px;
  display: grid;
  gap: 6px;
}

.village-list {
  margin-top: 6px;
  margin-left: 18px;
  display: grid;
  gap: 4px;
}

.district-row {
  border: 1px solid #2a3a54;
  border-radius: 8px;
  background: #1a2940;
  display: flex;
  align-items: center;
  padding: 7px 8px;
}

.district-toggle {
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.district-row.off {
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
