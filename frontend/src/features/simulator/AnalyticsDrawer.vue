<script setup>
import { computed, ref } from 'vue'
import { BarChart3, ChevronRight, TriangleAlert } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['seek'])

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

// --- Coverage trend + anomalies -------------------------------------------
const coverage = computed(() => props.simulatorState.coverage || {})
const series = computed(() => coverage.value.series || [])
const anomalies = computed(() => coverage.value.anomalies || [])
const totalRegions = computed(() => coverage.value.totalRegions || 0)
const regions = computed(() => coverage.value.regions || [])

const currentCoverage = computed(() => {
  const s = series.value
  if (!s.length) return null
  const t = props.simulatorState.currentTime
  let chosen = s[0]
  for (const p of s) {
    if (p.tMs <= t) chosen = p
    else break
  }
  return chosen
})

const currentPct = computed(() => (currentCoverage.value ? Math.round(currentCoverage.value.pct * 100) : null))

// Sparkline over a 100x100 viewBox (preserveAspectRatio none stretches it).
const sparkPoints = computed(() => {
  const s = series.value
  if (s.length < 2) return ''
  return s.map((p, i) => `${(i / (s.length - 1)) * 100},${100 - p.pct * 100}`).join(' ')
})

const progressX = computed(() => {
  const s = series.value
  if (s.length < 2) return 0
  const t0 = s[0].tMs
  const t1 = s[s.length - 1].tMs
  const span = t1 - t0 || 1
  return Math.min(100, Math.max(0, ((props.simulatorState.currentTime - t0) / span) * 100))
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

      <section class="card">
        <p class="card-title">Coverage</p>
        <div class="stat-row">
          <span class="stat-label">Serviced now</span>
          <span class="stat-value tnum">
            <template v-if="currentPct != null">{{ currentPct }}%</template>
            <template v-else>—</template>
          </span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Regions covered</span>
          <span class="stat-value tnum">
            <template v-if="currentCoverage">{{ currentCoverage.covered }}/{{ totalRegions }}</template>
            <template v-else>—</template>
          </span>
        </div>
        <svg
          v-if="sparkPoints"
          class="spark"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polyline class="spark-line" :points="sparkPoints" />
          <line class="spark-cursor" :x1="progressX" :y1="0" :x2="progressX" :y2="100" />
        </svg>
        <p v-else class="placeholder-note">計算覆蓋率中…</p>
      </section>

      <section class="card">
        <p class="card-title">
          <TriangleAlert :size="13" /> Anomalies
          <span class="badge" :class="{ alert: anomalies.length }">{{ anomalies.length }}</span>
        </p>
        <ul v-if="anomalies.length" class="anomaly-list">
          <li v-for="(a, i) in anomalies" :key="i">
            <button type="button" class="anomaly-btn" @click="emit('seek', a.tMs)">
              <span class="anomaly-time tnum">{{ fmt(a.tMs) }}</span>
              <span class="anomaly-tag">覆蓋率下降 {{ Math.round(a.pct * 100) }}%</span>
            </button>
          </li>
        </ul>
        <p v-else class="placeholder-note">目前視窗無覆蓋率異常。</p>
      </section>

      <section v-if="regions.length" class="card">
        <p class="card-title">
          Affected regions
          <span class="badge">{{ regions.length }}</span>
        </p>
        <ul class="region-list">
          <li v-for="r in regions" :key="r.code" class="region-row">
            <span class="region-name">{{ r.name }}</span>
            <span class="region-seen tnum">{{ fmtShort(r.lastSeen) }}</span>
          </li>
        </ul>
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

.placeholder-note {
  margin: 0;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text-dim);
}

.spark {
  width: 100%;
  height: 40px;
  margin-top: 4px;
}

.spark-line {
  fill: none;
  stroke: var(--accent);
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.spark-cursor {
  stroke: #f4e3a5;
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.badge {
  margin-left: auto;
  min-width: 18px;
  padding: 0 5px;
  border-radius: 9px;
  text-align: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-dim);
  background: var(--surface-1);
  border: 1px solid var(--line);
}

.badge.alert {
  color: #1a1010;
  background: var(--alert);
  border-color: var(--alert);
}

.anomaly-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
  max-height: 140px;
  overflow-y: auto;
}

.anomaly-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface-1);
  color: var(--text);
  cursor: pointer;
}

.anomaly-btn:hover {
  border-color: var(--alert);
}

.anomaly-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.anomaly-time {
  font-size: 10px;
}

.anomaly-tag {
  font-size: 10px;
  color: var(--alert);
  font-weight: 600;
}

.region-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 3px;
  max-height: 160px;
  overflow-y: auto;
}

.region-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}

.region-name {
  color: var(--text);
}

.region-seen {
  color: var(--text-dim);
  font-size: 10px;
}
</style>
