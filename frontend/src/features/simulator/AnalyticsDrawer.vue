<script setup>
import { computed, ref } from 'vue'
import { BarChart3, ChevronRight, TriangleAlert } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  }
})

const open = ref(true)

const fmt = (ms) => {
  if (ms == null) return '--'
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString([], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const fmtShort = (ms) => {
  if (ms == null) return '--'
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const segments = computed(() => props.simulatorState.segments ?? [])
const sessionLabel = computed(() => {
  const index = props.simulatorState.selectedSegmentIndex
  if (index === -1 || !segments.value.length) return 'All sessions'
  const seg = segments.value[index]
  return seg ? `${fmtShort(seg.from)} – ${fmtShort(seg.to)}` : 'All sessions'
})

const smoothPct = computed(() => {
  const p = props.simulatorState.smoothProgress
  return p?.total ? Math.round((p.done / p.total) * 100) : 0
})
</script>

<template>
  <aside class="drawer" :class="{ collapsed: !open }">
    <button
      class="drawer-handle"
      type="button"
      :aria-label="open ? 'Collapse analytics' : 'Expand analytics'"
      :aria-expanded="open"
      @click="open = !open"
    >
      <BarChart3 v-if="!open" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <div v-if="open" class="drawer-body">
      <header class="drawer-head">
        <BarChart3 :size="15" />
        <h3>Analytics</h3>
      </header>

      <section class="card">
        <p class="card-title">This frame</p>
        <div class="stat-row">
          <span class="stat-label">Vehicles</span>
          <span class="stat-value tnum">{{ simulatorState.featureCount ?? 0 }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Captures</span>
          <span class="stat-value tnum">{{ simulatorState.count ?? 0 }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Time</span>
          <span class="stat-value tnum">{{ fmt(simulatorState.currentTime) }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Session</span>
          <span class="stat-value session">{{ sessionLabel }}</span>
        </div>
      </section>

      <section class="card">
        <p class="card-title">Playback</p>
        <div class="stat-row">
          <span class="stat-label">Speed</span>
          <span class="stat-value tnum">{{ simulatorState.speed }}×</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Road smoothing</span>
          <span class="stat-value">
            <template v-if="simulatorState.smoothing">{{ smoothPct }}%</template>
            <template v-else>{{ simulatorState.smooth ? 'on' : 'off' }}</template>
          </span>
        </div>
      </section>

      <!-- Phase 2b: backed by an analytics API (trend / anomaly / regions). -->
      <section class="card placeholder">
        <p class="card-title">
          <TriangleAlert :size="13" /> Trends &amp; anomalies
        </p>
        <p class="placeholder-note">
          趨勢、異常偵測與受影響區域需後端統計 API(Phase 2b)。待定義「異常」規則後接入。
        </p>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.drawer {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: var(--z-drawer, 30);
  width: 260px;
  max-height: calc(100% - 160px);
  display: flex;
  flex-direction: column;
}

.drawer.collapsed {
  width: auto;
}

.drawer-handle {
  align-self: flex-end;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: rgb(13 20 33 / 92%);
  color: var(--text);
  cursor: pointer;
}

.drawer-handle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.drawer-body {
  margin-top: 8px;
  display: grid;
  gap: 10px;
  overflow-y: auto;
  padding: 12px;
  border-radius: 12px;
  background: rgb(13 20 33 / 92%);
  border: 1px solid var(--line);
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
}

.drawer-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
}

.drawer-head h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
}

.card {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-2);
  border: 1px solid var(--line);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 2px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-dim);
}

.stat-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-dim);
}

.stat-value {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}

.stat-value.session {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  text-align: right;
}

.placeholder {
  border-style: dashed;
}

.placeholder-note {
  margin: 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text-dim);
}
</style>
