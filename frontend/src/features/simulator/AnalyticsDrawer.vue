<script setup>
import { computed, ref } from 'vue'
import { BarChart3, ChevronRight, Columns2 } from 'lucide-vue-next'

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

const isCompare = computed(() => props.simulatorState.mode === 'compare')
const compareCounts = computed(() => {
  let a = 0
  let b = 0
  for (const f of props.simulatorState.compareGeoJson?.features || []) {
    if (f.properties?.__cmp === 'B') b += 1
    else a += 1
  }
  return { a, b, delta: b - a }
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

      <section v-if="isCompare" class="card">
        <p class="card-title">
          <Columns2 :size="13" /> Compare A vs B
        </p>
        <div class="stat-row">
          <span class="stat-label"><span class="dot a"></span>A · {{ fmtShort(simulatorState.compare.aTime) }}</span>
          <span class="stat-value tnum">{{ compareCounts.a }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label"><span class="dot b"></span>B · {{ fmtShort(simulatorState.compare.bTime) }}</span>
          <span class="stat-value tnum">{{ compareCounts.b }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Δ vehicles</span>
          <span
            class="stat-value tnum"
            :class="{ up: compareCounts.delta > 0, down: compareCounts.delta < 0 }"
          >
            {{ compareCounts.delta > 0 ? '+' : '' }}{{ compareCounts.delta }}
          </span>
        </div>
      </section>

      <section v-if="!isCompare" class="card">
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
          <span class="stat-label">Mode</span>
          <span class="stat-value" :class="{ live: simulatorState.mode === 'live' }">
            {{ simulatorState.mode === 'live' ? '● LIVE' : 'History' }}
          </span>
        </div>
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

.stat-value.live {
  color: var(--alert);
}

.stat-value.up {
  color: var(--ok);
}

.stat-value.down {
  color: var(--alert);
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 5px;
}

.dot.a {
  background: #5fa3e3;
}

.dot.b {
  background: #f2994a;
}
</style>
