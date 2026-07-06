<script setup>
import { computed } from 'vue'
import { Pause, Play, SkipBack, SkipForward } from 'lucide-vue-next'

const props = defineProps({
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
  routePlanRoutes: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select-dataset', 'set-time', 'toggle-play', 'set-speed', 'step', 'toggle-smooth', 'select-segment', 'simulate-route-plan', 'stop'])

const isRoutePlanMode = computed(() => props.simulatorState.mode === 'route-plan')

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

const fmtRange = (from, to) => `${fmtShort(from)} – ${fmtShort(to)}`

const sliderStep = computed(() => Math.max(1000, (Number(props.simulatorState.intervalSeconds) || 60) * 1000))
const hasRange = computed(() => props.simulatorState.from != null && props.simulatorState.to != null)

const playFrom = computed(() => props.simulatorState.playFrom ?? props.simulatorState.from)
const playTo = computed(() => props.simulatorState.playTo ?? props.simulatorState.to)
const segments = computed(() => props.simulatorState.segments ?? [])

const smoothDone = computed(() => props.simulatorState.smoothProgress?.done ?? 0)
const smoothTotal = computed(() => props.simulatorState.smoothProgress?.total ?? 0)
const smoothPct = computed(() => (smoothTotal.value ? Math.round((smoothDone.value / smoothTotal.value) * 100) : 0))

const onSliderInput = (event) => {
  emit('set-time', Number(event.target.value))
}
</script>

<template>
  <section class="sim-panel">
    <div class="sim-section">
      <p class="sim-label">即時資料集</p>
      <div class="sim-dataset-list">
        <button
          v-for="candidate in simulatorCandidates"
          :key="candidate.key"
          class="sim-dataset-btn"
          :class="{ active: simulatorState.dataId === candidate.dataId }"
          type="button"
          @click="emit('select-dataset', candidate.dataId)"
        >
          {{ candidate.label }}
        </button>
        <p v-if="!simulatorCandidates.length" class="sim-empty">目前沒有可播放的即時資料集。</p>
      </div>
    </div>

    <div class="sim-section">
      <p class="sim-label">路線規劃結果</p>
      <button
        v-if="routePlanRoutes.length"
        class="sim-dataset-btn"
        :class="{ active: isRoutePlanMode }"
        type="button"
        @click="emit('simulate-route-plan')"
      >
        模擬垃圾車路線（{{ routePlanRoutes.length }} 台車）
      </button>
      <p v-else class="sim-empty">尚無路線結果，請先在「路線」頁求解。</p>
    </div>

    <p v-if="simulatorState.error" class="sim-error">{{ simulatorState.error }}</p>

    <div v-if="simulatorState.active && hasRange" class="sim-section">
      <div v-if="segments.length > 1" class="sim-sessions">
        <p class="sim-label">錄製區段</p>
        <div class="sim-session-list">
          <button
            class="sim-session-btn"
            :class="{ active: simulatorState.selectedSegmentIndex === -1 }"
            type="button"
            @click="emit('select-segment', -1)"
          >
            全部
          </button>
          <button
            v-for="(segment, index) in segments"
            :key="segment.from"
            class="sim-session-btn"
            :class="{ active: simulatorState.selectedSegmentIndex === index }"
            type="button"
            @click="emit('select-segment', index)"
          >
            {{ fmtRange(segment.from, segment.to) }}
          </button>
        </div>
      </div>

      <div class="sim-time-row">
        <span class="sim-time-current tnum">{{ fmt(simulatorState.currentTime) }}</span>
        <span v-if="simulatorState.loading" class="sim-status">載入中...</span>
      </div>

      <input
        class="sim-slider"
        type="range"
        :min="playFrom"
        :max="playTo"
        :step="sliderStep"
        :value="simulatorState.currentTime ?? playTo"
        @input="onSliderInput"
      />

      <div class="sim-bounds">
        <span>{{ fmt(playFrom) }}</span>
        <span>{{ fmt(playTo) }}</span>
      </div>

      <div class="sim-transport">
        <button class="sim-ctrl" type="button" aria-label="上一格" @click="emit('step', -1)">
          <SkipBack :size="16" />
        </button>
        <button class="sim-ctrl play" type="button" :aria-label="simulatorState.playing ? '暫停' : '播放'" @click="emit('toggle-play')">
          <Pause v-if="simulatorState.playing" :size="18" />
          <Play v-else :size="18" />
        </button>
        <button class="sim-ctrl" type="button" aria-label="下一格" @click="emit('step', 1)">
          <SkipForward :size="16" />
        </button>
      </div>

      <div class="sim-speeds">
        <button
          v-for="speed in simulatorSpeeds"
          :key="speed"
          class="sim-speed-btn"
          :class="{ active: simulatorState.speed === speed }"
          type="button"
          @click="emit('set-speed', speed)"
        >
          {{ speed }}×
        </button>
      </div>

      <button
        v-if="!isRoutePlanMode"
        class="sim-smooth"
        :class="{ active: simulatorState.smooth }"
        type="button"
        @click="emit('toggle-smooth')"
      >
        {{ simulatorState.smooth ? '✓ ' : '' }}道路平滑化 (OSRM)
      </button>

      <div v-if="simulatorState.smoothing" class="sim-smooth-progress">
        <div class="sim-progress-track">
          <div
            class="sim-progress-fill"
            :class="{ indeterminate: !smoothTotal }"
            :style="smoothTotal ? { width: smoothPct + '%' } : null"
          ></div>
        </div>
        <span class="sim-progress-label">
          道路平滑化中... 計算道路路徑<template v-if="smoothTotal"> · {{ smoothDone }}/{{ smoothTotal }} ({{ smoothPct }}%)</template>
        </span>
      </div>

      <div class="sim-meta">
        <span>{{ simulatorState.featureCount }} 點位</span>
        <span>{{ simulatorState.count }} 筆擷取</span>
      </div>

      <button class="sim-exit" type="button" @click="emit('stop')">結束播放</button>
    </div>
  </section>
</template>

<style scoped>
.sim-panel {
  display: grid;
  gap: 12px;
}

.sim-section {
  display: grid;
  gap: 8px;
}

.sim-label {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #dce8ff;
}

.sim-dataset-list {
  display: grid;
  gap: 6px;
}

.sim-dataset-btn {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #bfd3f2;
  font-size: 11px;
  font-weight: 600;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
}

.sim-dataset-btn.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-empty,
.sim-status {
  margin: 0;
  font-size: 10px;
  color: #9fb7da;
}

.sim-error {
  margin: 0;
  font-size: 11px;
  color: #ffb3ad;
}

.sim-time-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.sim-time-current {
  font-size: 13px;
  font-weight: 700;
  color: #f4e3a5;
}

.sim-slider {
  width: 100%;
  accent-color: #5fa3e3;
}

.sim-bounds,
.sim-meta {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #9fb7da;
}

.sim-transport {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.sim-ctrl {
  display: grid;
  place-items: center;
  width: 34px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #d6e6ff;
  cursor: pointer;
}

.sim-ctrl.play {
  width: 44px;
  height: 34px;
  background: #2a4d7a;
  border-color: #5fa3e3;
  color: #eaf4ff;
}

.sim-speeds {
  display: flex;
  gap: 6px;
  justify-content: center;
}

.sim-speed-btn {
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 9px;
  cursor: pointer;
}

.sim-speed-btn.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-smooth {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #bfd3f2;
  font-size: 11px;
  font-weight: 600;
  padding: 7px 10px;
  cursor: pointer;
}

.sim-smooth.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-sessions {
  display: grid;
  gap: 6px;
}

.sim-session-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sim-session-btn {
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 8px;
  cursor: pointer;
}

.sim-session-btn.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-smooth-progress {
  display: grid;
  gap: 4px;
}

.sim-progress-track {
  height: 6px;
  border-radius: 4px;
  background: #1a2940;
  overflow: hidden;
}

.sim-progress-fill {
  height: 100%;
  border-radius: 4px;
  background: #5fa3e3;
  transition: width 0.2s ease;
}

.sim-progress-fill.indeterminate {
  width: 40%;
  animation: sim-indeterminate 1.1s ease-in-out infinite;
}

@keyframes sim-indeterminate {
  0% { margin-left: -40%; }
  100% { margin-left: 100%; }
}

.sim-progress-label {
  font-size: 10px;
  color: #9fb7da;
}

.sim-exit {
  border-radius: 8px;
  border: 1px solid #5a3540;
  background: #2a1a22;
  color: #ffb3ad;
  font-size: 11px;
  font-weight: 600;
  padding: 7px 10px;
  cursor: pointer;
}

.sim-exit:hover {
  background: #3a2530;
}
</style>
