<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown, Flame, LocateFixed, RefreshCw, Settings } from 'lucide-vue-next'

const props = defineProps({
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
  rangePointFilterEnabled: {
    type: Boolean,
    default: false
  },
  selectedRangeCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'toggle-data-layer',
  'set-data-layer-mode',
  'refresh-data-layer',
  'set-range-point-filter-enabled'
])
const expandedState = ref({})
const nowMs = ref(Date.now())
let nowTimer = null

const dataLayerItems = computed(() =>
  Object.entries(props.dataLayerState).map(([key, value]) => ({
    key,
    name: value.label,
    detail: value.detail,
    enabled: value.active,
    mode: value.style?.mode || 'points',
    color: value.style?.color || '#f2c94c',
    supportedModes: Array.isArray(value.supportedModes) && value.supportedModes.length ? value.supportedModes : ['points', 'heatmap']
  }))
)
const modeMeta = {
  points: { label: 'Points', icon: LocateFixed },
  heatmap: { label: 'Heatmap', icon: Flame }
}

const summary = computed(() => props.dataAggregate?.summary || { count: 0 })
const groupEntries = computed(() => Object.entries(summary.value.groups || {}).slice(0, 4))
const aggregateConfig = computed(() => props.dataAggregate?.config || {})
const sumField = computed(() => aggregateConfig.value.sumField || '')
const avgField = computed(() => aggregateConfig.value.avgField || '')
const sumLabel = computed(() => aggregateConfig.value.sumLabel || 'Sum')
const avgLabel = computed(() => aggregateConfig.value.avgLabel || 'Average')
const sumDigits = computed(() => Number.isFinite(Number(aggregateConfig.value.sumDigits)) ? Number(aggregateConfig.value.sumDigits) : 1)
const avgDigits = computed(() => Number.isFinite(Number(aggregateConfig.value.avgDigits)) ? Number(aggregateConfig.value.avgDigits) : 1)
const sumValue = computed(() =>
  sumField.value ? Number(summary.value.sum?.[sumField.value] || 0).toFixed(sumDigits.value) : Number(0).toFixed(sumDigits.value)
)
const avgValue = computed(() => {
  if (!avgField.value) return 'N/A'
  const value = summary.value.avg?.[avgField.value]
  return value == null ? 'N/A' : Number(value).toFixed(avgDigits.value)
})

const isExpanded = (key) => (expandedState.value[key] ?? true) === true

const toggleExpanded = (key) => {
  expandedState.value[key] = !isExpanded(key)
}

const isAggregateLayer = (layerKey) => props.dataAggregate?.layerKey === layerKey

const getRuntime = (layerKey) => props.dataLayerRuntime?.[layerKey] || {}

const formatRemaining = (remainingSeconds) => {
  const total = Math.max(0, Math.floor(remainingSeconds || 0))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

const getCountdownText = (layerKey) => {
  const runtime = getRuntime(layerKey)
  if (!runtime?.isDynamic) return ''
  if (runtime.isFetching) return 'Updating...'
  if (!runtime.nextRefreshAt) return '--:--'
  const diffSeconds = Math.ceil((runtime.nextRefreshAt - nowMs.value) / 1000)
  return formatRemaining(diffSeconds)
}

const shouldShowCountdown = (layerKey) => getRuntime(layerKey)?.isDynamic === true
const isDynamicLayer = (layerKey) => getRuntime(layerKey)?.isDynamic === true
const showRangeFilterHint = computed(() => props.rangePointFilterEnabled && props.selectedRangeCount === 0)

const getCurrentModeMeta = (layer) => modeMeta[layer.mode] || { label: layer.mode, icon: LocateFixed }

const cycleMode = (layer) => {
  const modes = Array.isArray(layer.supportedModes) && layer.supportedModes.length ? layer.supportedModes : ['points']
  if (modes.length <= 1) return
  const index = modes.indexOf(layer.mode)
  const next = modes[(index + 1) % modes.length]
  emit('set-data-layer-mode', { key: layer.key, mode: next })
}

onMounted(() => {
  nowTimer = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (nowTimer) {
    clearInterval(nowTimer)
    nowTimer = null
  }
})
</script>

<template>
  <section class="data-panel">
    <div class="panel-title-row">
      <h3>Data Layers</h3>
    </div>
    <button
      class="range-filter-btn"
      type="button"
      :aria-pressed="props.rangePointFilterEnabled"
      :class="{ active: props.rangePointFilterEnabled }"
      @click="emit('set-range-point-filter-enabled', !props.rangePointFilterEnabled)"
    >
      只顯示已選擇 range 內資料點
    </button>
    <p v-if="showRangeFilterHint" class="data-status hint">已啟用範圍過濾，請先在 Ranges 選擇範圍。</p>

    <article v-for="layer in dataLayerItems" :key="layer.key" class="region-card" :class="{ expanded: isExpanded(layer.key) }">
      <div class="card-head">
        <button
          class="region-row region-toggle"
          type="button"
          :aria-pressed="layer.enabled"
          @click="emit('toggle-data-layer', layer.key)"
        >
          <div class="switch-dot" :class="{ selected: layer.enabled }">
            <span class="switch-knob"></span>
          </div>
          <div class="region-label-wrap">
            <p class="region-name marquee-line">
              <span class="marquee-static">{{ layer.name }}</span>
              <span class="marquee-track" aria-hidden="true">
                <span class="marquee-segment">{{ layer.name }}</span>
                <span class="marquee-segment">{{ layer.name }}</span>
              </span>
            </p>
            <p class="region-meta marquee-line">
              <span class="marquee-static">{{ layer.detail }}</span>
              <span class="marquee-track" aria-hidden="true">
                <span class="marquee-segment">{{ layer.detail }}</span>
                <span class="marquee-segment">{{ layer.detail }}</span>
              </span>
            </p>
          </div>
        </button>

        <div class="head-actions">
          <div v-if="isDynamicLayer(layer.key)" class="live-badge">
            <span class="live-dot"></span>
            <span>LIVE</span>
          </div>
          <button
            class="collapse-btn"
            type="button"
            :aria-label="isExpanded(layer.key) ? 'Collapse data item' : 'Expand data item'"
            :aria-expanded="isExpanded(layer.key)"
            @click.stop="toggleExpanded(layer.key)"
          >
            <ChevronDown :size="13" :class="{ rotated: !isExpanded(layer.key) }" />
          </button>
        </div>
      </div>

      <div v-if="isExpanded(layer.key)" class="expanded-content">
        <button
          class="mode-dropdown-btn"
          type="button"
          @click="cycleMode(layer)"
        >
          <span class="mode-left">
            <component :is="getCurrentModeMeta(layer).icon" :size="12" />
            <span>{{ getCurrentModeMeta(layer).label }}</span>
          </span>
          <ChevronDown :size="12" />
        </button>
        <div class="content-divider"></div>

        <div v-if="isAggregateLayer(layer.key)" class="metric-list">
          <div class="summary-row">
            <span class="summary-label">Count</span>
            <strong>{{ summary.count || 0 }}</strong>
          </div>
          <div class="summary-row">
            <span class="summary-label">{{ sumLabel }}</span>
            <strong>{{ sumValue }}</strong>
          </div>
          <div v-if="avgField" class="summary-row">
            <span class="summary-label">{{ avgLabel }}</span>
            <strong>{{ avgValue }}</strong>
          </div>
        </div>
        <p v-if="isAggregateLayer(layer.key) && props.dataAggregate.loading" class="data-status">Loading aggregate...</p>
        <p v-else-if="isAggregateLayer(layer.key) && props.dataAggregate.error" class="data-status error">{{ props.dataAggregate.error }}</p>

        <div v-if="isAggregateLayer(layer.key) && groupEntries.length" class="metric-list compact">
          <div v-for="[group, groupSummary] in groupEntries" :key="group" class="summary-row">
            <span class="summary-label">{{ group }}</span>
            <strong>{{ groupSummary.count || 0 }}</strong>
          </div>
        </div>

        <template v-if="shouldShowCountdown(layer.key)">
          <div class="content-divider"></div>
          <div class="footer-row">
            <span class="countdown-text">Next refresh {{ getCountdownText(layer.key) }}</span>
            <div class="footer-actions">
              <button
                class="inline-refresh-btn"
                type="button"
                aria-label="Refresh this data layer"
                :disabled="getRuntime(layer.key)?.isFetching"
                @click.stop="emit('refresh-data-layer', layer.key)"
              >
                <RefreshCw :size="12" />
              </button>
              <button class="inline-refresh-btn" type="button" aria-label="Data settings">
                <Settings :size="12" />
              </button>
            </div>
          </div>
        </template>
      </div>
    </article>
  </section>
</template>

<style scoped>
.data-panel {
  display: grid;
  gap: 8px;
}

.panel-title-row h3 {
  margin: 0;
  color: #eaf4ff;
  font-size: 14px;
  font-weight: 700;
}

.range-filter-btn {
  border-radius: 6px;
  border: 1px solid #35527c;
  background: #102038;
  color: #c6dcff;
  font-size: 11px;
  font-weight: 600;
  padding: 8px 10px;
  text-align: left;
}

.range-filter-btn.active {
  border-color: #7cb9ff;
  background: #17355b;
  color: #eef6ff;
}

.region-card {
  border-radius: 6px;
  border: 1px solid #3b82f6;
  background: #0a0f1a;
  padding: 12px;
  display: grid;
  gap: 10px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.region-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.region-toggle {
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  padding: 0;
  cursor: pointer;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.switch-dot {
  width: 32px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid #3b82f6;
  background: #1b2b44;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-shrink: 0;
}

.switch-dot.selected {
  justify-content: flex-end;
}

.switch-knob {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: #b9f3d2;
}

.region-label-wrap {
  flex: 1;
  width: 0;
  min-width: 0;
  overflow: hidden;
  display: grid;
  gap: 2px;
}

.region-name,
.region-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.region-name {
  margin: 0;
  color: #eaf4ff;
  font-family: 'Fira Sans', Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
}

.region-meta {
  margin: 0;
  color: #9fb7da;
  font-family: 'Fira Sans', Inter, sans-serif;
  font-size: 10px;
  font-weight: 500;
}

.marquee-line {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  position: relative;
  overflow: hidden;
  white-space: nowrap;
}

.marquee-static {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 1;
  transition: opacity 120ms ease;
}

.marquee-track {
  position: absolute;
  inset: 0 auto 0 0;
  display: inline-flex;
  align-items: center;
  gap: 24px;
  width: max-content;
  opacity: 0;
  pointer-events: none;
  transform: translateX(0);
}

.marquee-segment {
  display: inline-block;
  white-space: nowrap;
}

.region-label-wrap:hover .marquee-static {
  opacity: 0;
}

.region-label-wrap:hover .marquee-track {
  opacity: 1;
  animation: hover-marquee-x 6s linear infinite;
}

@keyframes hover-marquee-x {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(calc(-50% - 12px));
  }
}

.live-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #1e2a44;
  border-radius: 999px;
  background: #0f1b2d;
  padding: 4px 8px;
  color: #fde68a;
  font-family: 'Fira Code', monospace;
  font-size: 9px;
  font-weight: 700;
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #f59e0b;
}

.countdown-text {
  color: #7ea3d6;
  font-size: 10px;
  font-weight: 500;
  font-family: 'Fira Sans', Inter, sans-serif;
  min-width: 0;
  text-align: right;
}

.inline-refresh-btn {
  width: 24px;
  height: 24px;
  border: 1px solid #1e2a44;
  border-radius: 6px;
  background: #132238;
  color: #93c5fd;
  display: grid;
  place-items: center;
  padding: 0;
}

.inline-refresh-btn:disabled {
  opacity: 0.5;
}

.collapse-btn {
  width: 22px;
  height: 22px;
  border: 1px solid #1e2a44;
  border-radius: 6px;
  background: #132238;
  color: #93c5fd;
  display: grid;
  place-items: center;
  padding: 0;
}

.collapse-btn :deep(svg) {
  transition: transform 180ms ease;
}

.collapse-btn :deep(svg.rotated) {
  transform: rotate(-90deg);
}

.expanded-content {
  display: grid;
  gap: 10px;
}

.mode-dropdown-btn {
  border: 1px solid #2a3a54;
  border-radius: 6px;
  background: #0f1729;
  color: #eaf4ff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 28px;
  padding: 0 8px;
  font-size: 10px;
  font-weight: 600;
  width: 100%;
}

.mode-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.content-divider {
  width: 100%;
  height: 1px;
  background: #1e2a44;
}

.metric-list {
  display: grid;
  gap: 6px;
}

.metric-list.compact {
  gap: 5px;
}

.summary-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
}

.summary-label {
  color: #9fb7da;
}

.summary-row strong {
  color: #eaf4ff;
  font-size: 12px;
  font-family: 'Fira Code', monospace;
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.data-status {
  margin: 2px 0 0;
  color: #cee6ff;
  font-size: 10px;
}

.data-status.error {
  color: #ffb3ad;
}

.data-status.hint {
  margin: 0;
  color: #9fc5f8;
}
</style>
