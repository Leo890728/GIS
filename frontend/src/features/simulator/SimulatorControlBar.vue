<script setup>
import { computed, ref } from 'vue'
import { ChevronLeft, ChevronRight, Pause, Play, Radio, SkipBack, SkipForward, X } from 'lucide-vue-next'

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

const emit = defineEmits(['set-time', 'toggle-play', 'set-speed', 'step', 'toggle-smooth', 'select-segment', 'set-window', 'toggle-live', 'stop'])

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

// --- Custom timeline track (session bands + draggable scrubber) ------------
const trackEl = ref(null)
const dragging = ref(false)
const hoverTime = ref(null)

const span = computed(() => Math.max(1, playTo.value - playFrom.value))
const pctOf = (ms) => {
  if (ms == null) return 0
  return Math.min(100, Math.max(0, ((ms - playFrom.value) / span.value) * 100))
}
const scrubberPct = computed(() => pctOf(props.simulatorState.currentTime ?? playTo.value))

// Recording sessions render as solid bands; the hatched rail between them = gaps.
// Bands outside the (possibly zoomed) window are dropped.
const bands = computed(() =>
  segments.value
    .map((seg, index) => ({
      index,
      from: seg.from,
      to: seg.to,
      left: pctOf(seg.from),
      width: Math.max(0.5, pctOf(seg.to) - pctOf(seg.from)),
      active: props.simulatorState.selectedSegmentIndex === index
    }))
    .filter((b) => b.to >= playFrom.value && b.from <= playTo.value)
)

const timeFromClientX = (clientX) => {
  const el = trackEl.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
  return Math.round(playFrom.value + ratio * span.value)
}

const seekTo = (clientX) => {
  const ms = timeFromClientX(clientX)
  if (ms != null) emit('set-time', ms)
}

const panning = ref(false)
let panStartX = 0
let panFrom = 0
let panTo = 0

const onTrackPointerDown = (event) => {
  trackEl.value?.setPointerCapture?.(event.pointerId)
  if (event.shiftKey) {
    panning.value = true
    panStartX = event.clientX
    panFrom = playFrom.value
    panTo = playTo.value
    return
  }
  dragging.value = true
  seekTo(event.clientX)
}
const onTrackPointerMove = (event) => {
  if (panning.value) {
    const el = trackEl.value
    if (!el) return
    const rect = el.getBoundingClientRect()
    const span = panTo - panFrom
    const dt = ((event.clientX - panStartX) / rect.width) * span
    const dataFrom = props.simulatorState.from
    const dataTo = props.simulatorState.to
    let lo = panFrom - dt
    let hi = panTo - dt
    if (lo < dataFrom) {
      lo = dataFrom
      hi = lo + span
    }
    if (hi > dataTo) {
      hi = dataTo
      lo = hi - span
    }
    emit('set-window', { from: lo, to: hi })
    return
  }
  if (dragging.value) seekTo(event.clientX)
  else hoverTime.value = timeFromClientX(event.clientX)
}
const onTrackPointerUp = (event) => {
  dragging.value = false
  panning.value = false
  trackEl.value?.releasePointerCapture?.(event.pointerId)
}

const onTrackWheel = (event) => {
  const focus = timeFromClientX(event.clientX)
  if (focus == null) return
  const factor = event.deltaY < 0 ? 0.8 : 1.25 // scroll up = zoom in
  let lo = focus - (focus - playFrom.value) * factor
  let hi = focus + (playTo.value - focus) * factor
  lo = Math.max(props.simulatorState.from, lo)
  hi = Math.min(props.simulatorState.to, hi)
  emit('set-window', { from: lo, to: hi })
}
const onTrackLeave = () => {
  hoverTime.value = null
}

const nudge = (steps) => {
  const cur = props.simulatorState.currentTime ?? playFrom.value
  const next = Math.min(playTo.value, Math.max(playFrom.value, cur + steps * sliderStep.value))
  emit('set-time', next)
}
const onTrackKeydown = (event) => {
  switch (event.key) {
    case 'ArrowLeft':
    case 'ArrowDown':
      nudge(-1)
      break
    case 'ArrowRight':
    case 'ArrowUp':
      nudge(1)
      break
    case 'PageDown':
      nudge(-10)
      break
    case 'PageUp':
      nudge(10)
      break
    case 'Home':
      emit('set-time', playFrom.value)
      break
    case 'End':
      emit('set-time', playTo.value)
      break
    default:
      return
  }
  event.preventDefault()
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
      <span class="sim-bar-time tnum">{{ fmt(simulatorState.currentTime) }}</span>
      <div
        ref="trackEl"
        class="sim-track"
        role="slider"
        tabindex="0"
        aria-label="Playback timeline (scroll to zoom, shift-drag to pan)"
        :aria-valuemin="playFrom"
        :aria-valuemax="playTo"
        :aria-valuenow="simulatorState.currentTime ?? playTo"
        :aria-valuetext="fmt(simulatorState.currentTime)"
        title="Scroll to zoom · Shift-drag to pan"
        @pointerdown="onTrackPointerDown"
        @pointermove="onTrackPointerMove"
        @pointerup="onTrackPointerUp"
        @pointerleave="onTrackLeave"
        @keydown="onTrackKeydown"
        @wheel.prevent="onTrackWheel"
      >
        <div class="sim-track-rail"></div>
        <div
          v-for="band in bands"
          :key="band.index"
          class="sim-track-band"
          :class="{ active: band.active }"
          :style="{ left: band.left + '%', width: band.width + '%' }"
        ></div>
        <div class="sim-track-fill" :style="{ width: scrubberPct + '%' }"></div>
        <div class="sim-track-thumb" :style="{ left: scrubberPct + '%' }"></div>
        <div
          v-if="hoverTime != null && !dragging"
          class="sim-track-preview tnum"
          :style="{ left: pctOf(hoverTime) + '%' }"
        >
          {{ fmt(hoverTime) }}
        </div>
      </div>
      <span class="sim-bar-bound tnum">{{ fmt(playTo) }}</span>
    </div>

    <div class="sim-bar-right">
      <button
        class="sim-bar-btn live"
        :class="{ active: simulatorState.mode === 'live' }"
        type="button"
        :aria-pressed="simulatorState.mode === 'live'"
        title="Live mode"
        @click="emit('toggle-live')"
      >
        <Radio :size="15" />
      </button>
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
  width: min(920px, calc(100% - 48px));
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 14px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgb(13 20 33 / 92%);
  border: 1px solid #2d4161;
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
  z-index: 5;
}

/* Keep each control cluster intact; only the timeline flexes/wraps so buttons
   never get squeezed into one another when the bar runs out of width. */
.sim-bar-controls,
.sim-bar-session,
.sim-bar-right {
  flex-shrink: 0;
}

.sim-bar-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-bar-btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #d6e6ff;
  cursor: pointer;
}

.sim-bar-btn.play {
  width: 48px;
  height: 38px;
  background: #2a4d7a;
  border-color: #5fa3e3;
  color: #eaf4ff;
}

.sim-bar-btn.active {
  border-color: var(--accent);
  background: var(--accent-strong);
  color: #eaf4ff;
}

.sim-bar-btn.live.active {
  border-color: var(--alert);
  background: #3a1a22;
  color: #ffb3ad;
}

.sim-bar button:focus-visible,
.sim-track:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
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
  flex: 1 1 300px;
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

/* Custom timeline track */
.sim-track {
  position: relative;
  flex: 1;
  min-width: 0;
  height: 26px;
  cursor: pointer;
  touch-action: none;
  border-radius: 6px;
}

.sim-track-rail {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 8px;
  border-radius: 6px;
  border: 1px solid var(--line);
  /* hatched = recording gap (no data) */
  background: repeating-linear-gradient(90deg, #16233a 0 6px, #1f2f49 6px 12px);
}

.sim-track-band {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  height: 8px;
  border-radius: 3px;
  background: #29456c; /* recording session (has data) */
}

.sim-track-band.active {
  background: var(--accent);
}

.sim-track-fill {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 8px;
  border-radius: 6px 0 0 6px;
  background: rgb(95 163 227 / 32%); /* played portion */
  pointer-events: none;
}

.sim-track-thumb {
  position: absolute;
  top: 50%;
  width: 4px;
  height: 18px;
  transform: translate(-50%, -50%);
  border-radius: 3px;
  background: #f4e3a5;
  box-shadow: 0 0 6px rgb(0 0 0 / 50%);
  pointer-events: none;
}

.sim-track-preview {
  position: absolute;
  bottom: 130%;
  transform: translateX(-50%);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  white-space: nowrap;
  background: #0b1220;
  border: 1px solid var(--line);
  color: var(--text);
  pointer-events: none;
}

.sim-bar-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  color: #9fb7da;
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
