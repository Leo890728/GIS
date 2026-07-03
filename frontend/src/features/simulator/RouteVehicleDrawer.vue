<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { LocateFixed, X } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  },
  vehicle: {
    type: Object,
    required: true
  },
  capacityKg: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['close', 'seek', 'toggle-follow'])

const stops = computed(() => props.vehicle?.stops || [])
const isFollowing = computed(() => props.simulatorState.autoFollow === true)

// `state.currentTime` advances on every rAF (60–120Hz); re-rendering the drawer
// at that rate is wasted work while it competes with the map's render loop.
// Mirror the clock into a ~10Hz trailing-throttled ref and derive everything
// time-dependent from it, so the drawer settles on the latest value after
// seeks/pauses without ticking at full rAF rate.
const displayTime = ref(props.simulatorState.currentTime ?? 0)
let displayTimer = null
watch(
  () => props.simulatorState.currentTime,
  () => {
    if (displayTimer) return
    displayTimer = setTimeout(() => {
      displayTimer = null
      displayTime.value = props.simulatorState.currentTime ?? 0
    }, 100)
  }
)
onBeforeUnmount(() => {
  if (displayTimer) clearTimeout(displayTimer)
})

// Index of the last stop already reached at the playback clock (-1 = still en
// route to the first stop). Load is a step function of this index.
const reachedIndex = computed(() => {
  const now = displayTime.value
  let index = -1
  for (const [i, stop] of stops.value.entries()) {
    if (stop.tMs <= now) index = i
    else break
  }
  return index
})

const currentLoadKg = computed(() => {
  const index = reachedIndex.value
  return index >= 0 ? Number(stops.value[index].loadKg) || 0 : 0
})

const loadPct = computed(() => {
  if (!(props.capacityKg > 0)) return 0
  return Math.min(100, Math.round((currentLoadKg.value / props.capacityKg) * 100))
})

const typeLabels = {
  start: '起點',
  end: '終點',
  depot: '場站',
  pickup: '收運點',
  disposal: '清潔隊'
}
const typeLabel = (value) => typeLabels[value] || value || ''

const fmtTime = (ms) => {
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

const fmtMeters = (meters) => {
  if (typeof meters !== 'number' || !Number.isFinite(meters)) return ''
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`
}

// 後端把每段 leg 的指示掛在「終點站」上（stops[i].instructions = 上一站->本站）。
// 時間軸要呈現「從本站出發往下一站怎麼走」，所以在 stop[index] 底下顯示下一段
// （stops[index+1]）的指示，並濾掉「抵達目的地」。只在切換車輛時算一次，
// 避免播放中每個 tick 重新 filter 出新陣列。
const nextSteps = computed(() =>
  stops.value.map((_, index) =>
    (stops.value[index + 1]?.instructions || []).filter((step) => step.type !== 'arrive')
  )
)

// 目前正在行駛的 step：車輛剛通過 reachedIndex 這一站、正往下一站前進，因此高亮
// 落在該站底下顯示的那段 leg。段內時間與道路距離成正比（見
// routePlanTracks.timedPathFromGeometry），故依累積距離比例對應目前時刻。
const activeStep = computed(() => {
  const now = displayTime.value
  const list = stops.value
  const originIndex = reachedIndex.value
  if (originIndex < 0 || originIndex + 1 >= list.length) return { originIndex: -1, stepIndex: -1 }

  const steps = nextSteps.value[originIndex] || []
  if (!steps.length) return { originIndex, stepIndex: -1 }

  const t0 = list[originIndex].tMs
  const t1 = list[originIndex + 1].tMs
  const span = t1 - t0
  if (!(span > 0)) return { originIndex, stepIndex: 0 }

  const total = steps.reduce((sum, step) => sum + (Number(step.distance_m) || 0), 0)
  const elapsedFrac = Math.min(1, Math.max(0, (now - t0) / span))
  if (!(total > 0)) {
    // 無距離資料時退回依 step 數平均切分。
    return { originIndex, stepIndex: Math.min(steps.length - 1, Math.floor(elapsedFrac * steps.length)) }
  }

  const targetDist = elapsedFrac * total
  let cumulative = 0
  for (let k = 0; k < steps.length; k += 1) {
    cumulative += Number(steps[k].distance_m) || 0
    if (targetDist <= cumulative) return { originIndex, stepIndex: k }
  }
  return { originIndex, stepIndex: steps.length - 1 }
})

const isActiveStep = (index, stepIndex) =>
  activeStep.value.originIndex === index && activeStep.value.stepIndex === stepIndex

// 時間軸捲動容器；每當目前停靠點改變（播放推進或使用者拖動）就把該行捲到正中央。
const timelineEl = ref(null)

watch(
  reachedIndex,
  async () => {
    await nextTick()
    const container = timelineEl.value
    if (!container) return
    const row = container.querySelector('.tl-row.current')
    if (!row) return
    const containerRect = container.getBoundingClientRect()
    const rowRect = row.getBoundingClientRect()
    const delta = rowRect.top - containerRect.top - (container.clientHeight - row.clientHeight) / 2
    container.scrollTo({ top: container.scrollTop + delta, behavior: 'smooth' })
  },
  { immediate: true }
)
</script>

<template>
  <aside class="veh-drawer">
    <header class="veh-head">
      <span class="veh-dot" :style="{ backgroundColor: vehicle.vehicleColor }"></span>
      <h3>{{ vehicle.vehicleId }}</h3>
      <button
        class="follow-btn"
        :class="{ active: isFollowing }"
        type="button"
        :aria-pressed="isFollowing"
        :title="isFollowing ? '停止跟隨' : '視角跟隨此車輛'"
        @click="emit('toggle-follow')"
      >
        <LocateFixed :size="13" />
        <span>{{ isFollowing ? '跟隨中' : '跟隨' }}</span>
      </button>
      <button class="icon-btn" type="button" aria-label="關閉車輛面板" @click="emit('close')">
        <X :size="14" />
      </button>
    </header>

    <section class="card">
      <p class="card-title">目前垃圾量</p>
      <p class="load-value tnum">
        {{ Math.round(currentLoadKg) }} kg<span v-if="capacityKg > 0" class="load-cap"> / {{ capacityKg }} kg</span>
      </p>
      <div v-if="capacityKg > 0" class="load-track">
        <div class="load-fill" :class="{ full: loadPct >= 100 }" :style="{ width: loadPct + '%' }"></div>
      </div>
    </section>

    <section class="card timeline-card">
      <p class="card-title">停靠時間軸</p>
      <ol v-if="stops.length" ref="timelineEl" class="timeline">
        <li
          v-for="(stop, index) in stops"
          :key="`${stop.tMs}-${index}`"
          class="tl-row"
          :class="{ done: index < reachedIndex, current: index === reachedIndex }"
        >
          <button class="tl-btn" type="button" :title="'跳至 ' + fmtTime(stop.tMs)" @click="emit('seek', stop.tMs)">
            <span class="tl-dot"></span>
            <span class="tl-time tnum">{{ fmtTime(stop.tMs) }}</span>
            <span class="tl-name">{{ stop.name || typeLabel(stop.type) }}</span>
            <span class="tl-load tnum">{{ Math.round(stop.loadKg || 0) }} kg</span>
          </button>
          <ol v-if="nextSteps[index].length" class="tl-nav-list">
            <li
              v-for="(step, stepIdx) in nextSteps[index]"
              :key="stepIdx"
              class="tl-nav-step"
              :class="{ active: isActiveStep(index, stepIdx) }"
            >
              <span class="tl-nav-text">{{ step.text }}</span>
              <span v-if="fmtMeters(step.distance_m)" class="tl-nav-dist tnum">{{ fmtMeters(step.distance_m) }}</span>
            </li>
          </ol>
        </li>
      </ol>
      <p v-else class="tl-empty">此路線沒有停靠時間資料。</p>
    </section>
  </aside>
</template>

<style scoped>
.veh-drawer {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: var(--z-drawer, 30);
  width: 280px;
  max-height: calc(100% - 160px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgb(13 20 33 / 92%);
  border: 1px solid var(--line, #2d4161);
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
  overflow: hidden;
}

.veh-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text, #eaf1ff);
}

.veh-head h3 {
  flex: 1;
  margin: 0;
  font-size: 13px;
  font-weight: 700;
}

.veh-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  border: 2px solid #ffffff;
  flex-shrink: 0;
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1px solid var(--line, #2d4161);
  background: transparent;
  color: var(--text-dim, #9fb7da);
  cursor: pointer;
}

.follow-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: 6px;
  border: 1px solid var(--line, #2d4161);
  background: var(--surface-2, #16233a);
  color: var(--text-dim, #9fb7da);
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  white-space: nowrap;
  cursor: pointer;
}

.follow-btn.active {
  border-color: var(--accent, #5fa3e3);
  background: var(--accent-strong, #2a4d7a);
  color: #eaf4ff;
}

.icon-btn:hover {
  color: var(--text, #eaf1ff);
}

.card {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 8px;
  background: var(--surface-2, #16233a);
  border: 1px solid var(--line, #2d4161);
}

.card-title {
  margin: 0 0 2px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-dim, #9fb7da);
}

.load-value {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #f4e3a5;
}

.load-cap {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-dim, #9fb7da);
}

.load-track {
  height: 8px;
  border-radius: 6px;
  background: #0f1b2d;
  border: 1px solid var(--line, #2d4161);
  overflow: hidden;
}

.load-fill {
  height: 100%;
  border-radius: 6px;
  background: #5fa3e3;
  transition: width 0.2s ease;
}

.load-fill.full {
  background: #eb5757;
}

.timeline-card {
  min-height: 0;
  overflow: hidden;
}

.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 2px;
  overflow-y: auto;
}

.tl-btn {
  display: grid;
  grid-template-columns: 10px auto minmax(0, 1fr) auto;
  align-items: center;
  column-gap: 8px;
  width: 100%;
  padding: 5px 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-dim, #9fb7da);
  font-size: 11px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}

.tl-btn:hover {
  background: rgb(95 163 227 / 12%);
}

.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #35527c;
  justify-self: center;
}

.tl-row.done .tl-dot {
  background: #5fa3e3;
}

.tl-row.current .tl-btn {
  background: rgb(95 163 227 / 18%);
  color: #eaf4ff;
}

.tl-row.current .tl-dot {
  background: #f4e3a5;
  box-shadow: 0 0 6px rgb(244 227 165 / 70%);
}

.tl-time {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.tl-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tl-load {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.tl-nav-list {
  margin: 1px 0 4px 26px;
  padding-left: 14px;
  display: grid;
  gap: 1px;
  list-style: decimal;
  border-left: 1px solid var(--line, #2d4161);
}

.tl-nav-step {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 0 4px;
  border-radius: 4px;
  color: var(--text-dim, #9fb7da);
  font-size: 10px;
  line-height: 1.5;
}

.tl-nav-step.active {
  background: rgb(244 227 165 / 16%);
  color: #f4e3a5;
  font-weight: 700;
}

.tl-nav-dist {
  flex: none;
  color: #7f9dc0;
}

.tl-nav-step.active .tl-nav-dist {
  color: #f4e3a5;
}

.tl-empty {
  margin: 0;
  font-size: 10px;
  color: var(--text-dim, #9fb7da);
}
</style>
