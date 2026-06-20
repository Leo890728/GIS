<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, Pause, Play, SkipBack, SkipForward, X } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  },
  simulatorSpeeds: {
    type: Array,
    default: () => [1, 10, 30, 60]
  }
})

const emit = defineEmits(['set-time', 'toggle-play', 'set-speed', 'step', 'toggle-smooth', 'select-segment', 'stop'])

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

const sliderStep = computed(() => Math.max(1000, (Number(props.simulatorState.intervalSeconds) || 60) * 1000))

const smoothDone = computed(() => props.simulatorState.smoothProgress?.done ?? 0)
const smoothTotal = computed(() => props.simulatorState.smoothProgress?.total ?? 0)
const smoothPct = computed(() => (smoothTotal.value ? Math.round((smoothDone.value / smoothTotal.value) * 100) : 0))

const playFrom = computed(() => props.simulatorState.playFrom ?? props.simulatorState.from)
const playTo = computed(() => props.simulatorState.playTo ?? props.simulatorState.to)
const segments = computed(() => props.simulatorState.segments ?? [])

// Session stepper cycles through: All (-1), then each session 0..n-1.
const sessionOrder = computed(() => [-1, ...segments.value.map((_, i) => i)])
const sessionLabel = computed(() => {
  const index = props.simulatorState.selectedSegmentIndex
  return index === -1 ? 'All' : `${index + 1}/${segments.value.length}`
})
const stepSession = (direction) => {
  const order = sessionOrder.value
  const pos = order.indexOf(props.simulatorState.selectedSegmentIndex)
  const next = Math.min(order.length - 1, Math.max(0, pos + direction))
  emit('select-segment', order[next])
}
</script>

<template>
  <div class="sim-bar">
    <div class="sim-bar-controls">
      <button class="sim-bar-btn" type="button" aria-label="Previous frame" @click="emit('step', -1)">
        <SkipBack :size="16" />
      </button>
      <button
        class="sim-bar-btn play"
        type="button"
        :aria-label="simulatorState.playing ? 'Pause' : 'Play'"
        @click="emit('toggle-play')"
      >
        <Pause v-if="simulatorState.playing" :size="18" />
        <Play v-else :size="18" />
      </button>
      <button class="sim-bar-btn" type="button" aria-label="Next frame" @click="emit('step', 1)">
        <SkipForward :size="16" />
      </button>
    </div>

    <div v-if="segments.length > 1" class="sim-bar-session">
      <button class="sim-bar-btn" type="button" aria-label="Previous session" @click="stepSession(-1)">
        <ChevronLeft :size="16" />
      </button>
      <span class="sim-bar-session-label" title="Recording session">{{ sessionLabel }}</span>
      <button class="sim-bar-btn" type="button" aria-label="Next session" @click="stepSession(1)">
        <ChevronRight :size="16" />
      </button>
    </div>

    <div class="sim-bar-timeline">
      <span class="sim-bar-time">{{ fmt(simulatorState.currentTime) }}</span>
      <input
        class="sim-bar-slider"
        type="range"
        :min="playFrom"
        :max="playTo"
        :step="sliderStep"
        :value="simulatorState.currentTime ?? playTo"
        @input="emit('set-time', Number($event.target.value))"
      />
      <span class="sim-bar-bound">{{ fmt(playTo) }}</span>
    </div>

    <div class="sim-bar-right">
      <div class="sim-bar-speeds">
        <button
          v-for="speed in simulatorSpeeds"
          :key="speed"
          class="sim-bar-speed"
          :class="{ active: simulatorState.speed === speed }"
          type="button"
          @click="emit('set-speed', speed)"
        >
          {{ speed }}×
        </button>
      </div>
      <button
        class="sim-bar-smooth"
        :class="{ active: simulatorState.smooth, busy: simulatorState.smoothing }"
        type="button"
        title="Road smoothing (OSRM)"
        @click="emit('toggle-smooth')"
      >
        <span
          v-if="simulatorState.smoothing"
          class="sim-bar-smooth-fill"
          :class="{ indeterminate: !smoothTotal }"
          :style="smoothTotal ? { width: smoothPct + '%' } : null"
        ></span>
        <span class="sim-bar-smooth-label">
          {{ simulatorState.smoothing && smoothTotal ? smoothPct + '%' : 'OSRM' }}
        </span>
      </button>
      <span v-if="simulatorState.loading && !simulatorState.smoothing" class="sim-bar-loading">…</span>
      <button class="sim-bar-exit" type="button" aria-label="Exit playback" @click="emit('stop')">
        <X :size="16" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.sim-bar {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(880px, calc(100% - 48px));
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgb(13 20 33 / 92%);
  border: 1px solid #2d4161;
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
  z-index: 5;
}

.sim-bar-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-bar-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #d6e6ff;
  cursor: pointer;
}

.sim-bar-btn.play {
  width: 40px;
  height: 32px;
  background: #2a4d7a;
  border-color: #5fa3e3;
  color: #eaf4ff;
}

.sim-bar-session {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sim-bar-session-label {
  min-width: 30px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: #cfe0fb;
  white-space: nowrap;
}

.sim-bar-timeline {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.sim-bar-time {
  font-size: 12px;
  font-weight: 700;
  color: #f4e3a5;
  white-space: nowrap;
}

.sim-bar-bound {
  font-size: 10px;
  color: #9fb7da;
  white-space: nowrap;
}

.sim-bar-slider {
  flex: 1;
  min-width: 0;
  accent-color: #5fa3e3;
}

.sim-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-bar-speeds {
  display: flex;
  gap: 4px;
}

.sim-bar-speed {
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 7px;
  cursor: pointer;
}

.sim-bar-speed.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-bar-smooth {
  position: relative;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  min-width: 44px;
  cursor: pointer;
}

.sim-bar-smooth.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-bar-smooth.busy {
  border-color: #5fa3e3;
}

.sim-bar-smooth-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: rgb(95 163 227 / 45%);
  transition: width 0.2s ease;
}

.sim-bar-smooth-fill.indeterminate {
  width: 40%;
  animation: sim-bar-indeterminate 1.1s ease-in-out infinite;
}

@keyframes sim-bar-indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(250%); }
}

.sim-bar-smooth-label {
  position: relative;
}

.sim-bar-loading {
  color: #88a4c8;
  font-size: 14px;
}

.sim-bar-exit {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #5a3540;
  background: #2a1a22;
  color: #ffb3ad;
  cursor: pointer;
}

@media (max-width: 720px) {
  .sim-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .sim-bar-timeline {
    order: 3;
    flex-basis: 100%;
  }
}
</style>
