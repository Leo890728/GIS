<script setup>
import { computed, ref } from 'vue'
import { BarChart3, ChevronRight, LocateFixed, Route, X } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle-track', 'toggle-follow', 'clear-selection'])

const open = ref(true)

const selected = computed(() => props.simulatorState.selected)
const hasTrack = computed(() => !!props.simulatorState.trackGeoJson)
const isFollowing = computed(() => !!props.simulatorState.autoFollow)
const propertyLabelMap = {
  car_licence: '車號',
  car_no: '車號',
  cartype: '車種',
  dt: '時間',
  caption: '位置',
  status: '狀態',
  direct: '方向',
  OverSpeedText: '是否超速',
  SpeedBand: '速度級距',
  CODEBASE: '統計區代碼',
  VILLAGE_CODE: '村里代碼',
  P_CNT: '人口數',
  icnrtname: '焚化廠名稱',
  budadd: '地址',
  locaepb: '主管環保局',
  oprtdept: '操作單位',
  weptype: '營運型態',
  icnrtnum: '爐數',
  dsnprcqt: '設計處理量',
  dsneleqt: '發電機組裝置容量',
  dsnhv: '設計熱值'
}

// Show the clicked entity's data fields, hiding internal/style helper keys.
const selectedRows = computed(() => {
  const entries = Object.entries(selected.value?.properties ?? {})
  return entries
    .filter(([key, value]) => !key.startsWith('__') && value != null && value !== '')
    .map(([key, value]) => ({ key, label: propertyLabelMap[key] || key, value: String(value) }))
})

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
  if (index === -1 || !segments.value.length) return '全部區段'
  const seg = segments.value[index]
  return seg ? `${fmtShort(seg.from)} – ${fmtShort(seg.to)}` : '全部區段'
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
      :aria-label="open ? '收合分析面板' : '展開分析面板'"
      :aria-expanded="open"
      @click="open = !open"
    >
      <BarChart3 v-if="!open" :size="16" />
      <ChevronRight v-else :size="16" />
    </button>

    <div v-if="open" class="drawer-body">
      <header class="drawer-head">
        <BarChart3 :size="15" />
        <h3>分析</h3>
      </header>

      <section v-if="selected" class="card selected">
        <div class="selected-head">
          <p class="card-title">已選點位</p>
          <button class="icon-btn" type="button" aria-label="清除選取" @click="emit('clear-selection')">
            <X :size="13" />
          </button>
        </div>
        <div v-if="selectedRows.length" class="selected-props">
          <div v-for="row in selectedRows" :key="row.key" class="stat-row">
            <span class="stat-label">{{ row.label }}</span>
            <span class="stat-value prop">{{ row.value }}</span>
          </div>
        </div>
        <p v-else class="selected-empty">此點位沒有屬性。</p>

        <div class="selected-actions">
          <button
            class="track-btn"
            :class="{ active: hasTrack }"
            type="button"
            :disabled="simulatorState.trackLoading"
            @click="emit('toggle-track')"
          >
            <Route :size="13" />
            <span v-if="simulatorState.trackLoading">建立中...</span>
            <span v-else>{{ hasTrack ? '隱藏軌跡' : '繪製軌跡' }}</span>
          </button>
          <button
            class="follow-btn"
            :class="{ active: isFollowing }"
            type="button"
            :aria-pressed="isFollowing"
            :title="isFollowing ? '停止跟隨' : '跟隨此點位'"
            @click="emit('toggle-follow')"
          >
            <LocateFixed :size="13" />
            <span>{{ isFollowing ? '跟隨中' : '跟隨' }}</span>
          </button>
        </div>
        <p v-if="simulatorState.trackError" class="selected-error">{{ simulatorState.trackError }}</p>
      </section>

      <section class="card">
        <p class="card-title">目前影格</p>
        <div class="stat-row">
          <span class="stat-label">車輛</span>
          <span class="stat-value tnum">{{ simulatorState.featureCount ?? 0 }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">擷取紀錄</span>
          <span class="stat-value tnum">{{ simulatorState.count ?? 0 }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">時間</span>
          <span class="stat-value tnum">{{ fmt(simulatorState.currentTime) }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">區段</span>
          <span class="stat-value session">{{ sessionLabel }}</span>
        </div>
      </section>

      <section class="card">
        <p class="card-title">播放</p>
        <div class="stat-row">
          <span class="stat-label">模式</span>
          <span class="stat-value" :class="{ live: simulatorState.mode === 'live' }">
            {{ simulatorState.mode === 'live' ? '● 即時' : '歷史' }}
          </span>
        </div>
        <div class="stat-row">
          <span class="stat-label">速度</span>
          <span class="stat-value tnum">{{ simulatorState.speed }}×</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">道路平滑化</span>
          <span class="stat-value">
            <template v-if="simulatorState.smoothing">{{ smoothPct }}%</template>
            <template v-else>{{ simulatorState.smooth ? '開' : '關' }}</template>
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

.card.selected {
  border-color: #6b5a2a;
  background: rgb(38 32 18 / 60%);
}

.selected-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
}

.icon-btn:hover {
  color: var(--text);
}

.selected-props {
  display: grid;
  gap: 5px;
  max-height: 220px;
  overflow-y: auto;
}

.stat-value.prop {
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.selected-empty,
.selected-error {
  margin: 0;
  font-size: 10px;
  color: #9fb7da;
}

.selected-error {
  color: #ffb3ad;
}

.selected-actions {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px;
  margin-top: 2px;
}

.track-btn,
.follow-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  padding: 7px 10px;
  cursor: pointer;
}

.track-btn {
  border: 1px solid #b9912f;
  background: #2a2310;
  color: #f4c95d;
}

.track-btn.active {
  background: #4a3c14;
  color: #ffe7a3;
}

.track-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.follow-btn {
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--text-dim);
}

.follow-btn.active {
  border-color: var(--accent);
  background: var(--accent-strong);
  color: #eaf4ff;
}
</style>
