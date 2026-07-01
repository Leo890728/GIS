import { computed, onBeforeUnmount, reactive } from 'vue'
import { fetchHistoryFrames, fetchHistoryRange } from './simulatorApi'
import { deriveSessionSegments, toMs } from './playbackTimeline'
import { useFrameRenderer } from './useFrameRenderer'
import { useSmoothRenderer } from './useSmoothRenderer'
import { useSelectedTrack } from './useSelectedTrack'
import { useLiveMode } from './useLiveMode'
import { useSimulatorShortcuts } from './useSimulatorShortcuts'

const SPEED_PRESETS = [1, 10, 30, 60]
const DEFAULT_SPEED = 30

const createState = () => ({
  active: false,
  dataId: '',
  from: null,
  to: null,
  count: 0,
  intervalSeconds: 60,
  currentTime: null,
  frames: [],
  segments: [],
  selectedSegmentIndex: -1,
  playFrom: null,
  playTo: null,
  mode: 'history',
  autoFollow: false,
  followCenter: null,
  selected: null,
  selectedPos: null,
  trackGeoJson: null,
  trackTraveledGeoJson: null,
  trackEndpointsGeoJson: null,
  trackLoading: false,
  trackError: '',
  featureCount: 0,
  playing: false,
  speed: DEFAULT_SPEED,
  smooth: false,
  smoothing: false,
  smoothProgress: { done: 0, total: 0 },
  loading: false,
  error: ''
})

/**
 * Drives history playback by taking over the matching live data layer.
 *
 * Architecture: the orchestrator owns the reactive `state` and a virtual clock
 * (requestAnimationFrame). Rendering is delegated to two interchangeable
 * strategies behind a single `renderAt(ms)` dispatch — `useFrameRenderer`
 * (per-capture GeoJSON, cached + prefetched) and `useSmoothRenderer` (OSRM
 * road-following interpolation). Selection/trajectory overlay, live mode, and
 * keyboard shortcuts are their own composables; this module wires them together
 * and exposes the public simulator API.
 *
 * @param apiBaseUrl backend base URL
 * @param dataLayers subset of useDataLayers: { getSimulatorCandidates, enterSimulator, exitSimulator, setSimulatorGeoJson }
 */
export const useSimulator = (apiBaseUrl, dataLayers) => {
  const state = reactive(createState())
  const candidates = computed(() => dataLayers.getSimulatorCandidates())

  // The live data layer the simulator is currently driving; both renderers style
  // their output with it.
  let layerEntry = null
  let rafId = null
  let lastTickReal = null
  let debounceTimer = null

  // --- Rendering strategies + selection overlay ------------------------------

  const selectedTrack = useSelectedTrack({
    apiBaseUrl,
    state,
    getSmoothTracks: () => smooth.getTracks()
  })

  const frame = useFrameRenderer({
    apiBaseUrl,
    state,
    dataLayers,
    getLayerEntry: () => layerEntry,
    syncSelectedPosition: selectedTrack.syncSelectedPosition
  })

  const smooth = useSmoothRenderer({
    apiBaseUrl,
    state,
    dataLayers,
    getLayerEntry: () => layerEntry,
    syncSelectedPosition: selectedTrack.syncSelectedPosition
  })

  // Single render dispatch: pick the active strategy, then advance the trajectory
  // overlay. `realNow` (a RAF timestamp) throttles smooth playback; omit it for
  // immediate renders. `force` re-applies the current frame even if unchanged.
  const renderAt = (ms, { force = false, realNow = null } = {}) => {
    if (state.smooth && smooth.hasTracks()) smooth.renderTick(ms, realNow)
    else frame.applyActiveFrame(force)
    selectedTrack.updateTrackProgress()
  }

  const renderCurrent = (force = false) => renderAt(state.currentTime, { force })

  // --- Virtual clock ---------------------------------------------------------

  const stopRaf = () => {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    lastTickReal = null
  }

  const tick = (nowReal) => {
    if (!state.playing) {
      stopRaf()
      return
    }
    if (lastTickReal == null) lastTickReal = nowReal
    const deltaReal = nowReal - lastTickReal
    lastTickReal = nowReal

    const next = state.currentTime + deltaReal * state.speed
    if (next >= state.playTo) {
      state.currentTime = state.playTo
      renderCurrent()
      pause()
      return
    }
    state.currentTime = next
    renderAt(state.currentTime, { realNow: nowReal })
    rafId = requestAnimationFrame(tick)
  }

  const play = () => {
    if (!state.active || state.currentTime == null) return
    live.exitLive()
    if (state.currentTime >= state.playTo) state.currentTime = state.playFrom
    state.playing = true
    lastTickReal = null
    rafId = requestAnimationFrame(tick)
  }

  const pause = () => {
    state.playing = false
    stopRaf()
  }

  const togglePlay = () => {
    if (state.playing) pause()
    else play()
  }

  const setSpeed = (multiplier) => {
    const value = Number(multiplier)
    if (Number.isFinite(value) && value > 0) state.speed = value
  }

  const stepFrame = (direction) => {
    pause()
    live.exitLive()
    const lo = state.playFrom ?? state.from
    const hi = state.playTo ?? state.to
    const frames = state.frames.filter((value) => value >= lo && value <= hi)
    if (!frames.length) return
    let index = frames.indexOf(frame.getActiveFrameMs())
    if (index < 0) index = frames.findIndex((value) => value >= state.currentTime)
    if (index < 0) index = frames.length - 1
    index = Math.min(frames.length - 1, Math.max(0, index + (direction >= 0 ? 1 : -1)))
    state.currentTime = frames[index]
    renderCurrent(true)
  }

  const setTime = (ms) => {
    if (!state.active || state.playFrom == null || state.playTo == null) return
    pause()
    live.exitLive()
    const clamped = Math.min(state.playTo, Math.max(state.playFrom, Number(ms)))
    state.currentTime = clamped
    selectedTrack.updateTrackProgress()
    if (state.smooth && smooth.hasTracks()) {
      smooth.renderSmooth(clamped)
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => frame.applyActiveFrame(), 80)
  }

  // --- Smooth playback toggle ------------------------------------------------

  const setSmooth = async (enabled) => {
    state.smooth = enabled === true
    if (state.smooth) {
      await smooth.loadTracks()
    } else {
      smooth.abortLoad()
      state.smoothing = false
      smooth.reset()
      frame.applyActiveFrame(true)
    }
  }

  const toggleSmooth = () => setSmooth(!state.smooth)

  // --- Sessions / live -------------------------------------------------------

  // Group the capture timeline into one recording session per calendar day.
  const deriveSegments = () => deriveSessionSegments(state.frames)

  const live = useLiveMode({
    apiBaseUrl,
    state,
    deriveSegments,
    applyActiveFrame: frame.applyActiveFrame,
    pausePlayback: () => pause(),
    smooth,
    clearSelection: selectedTrack.clearSelection
  })

  const selectSegment = (index) => {
    if (!state.active) return
    pause()
    live.exitLive()
    selectedTrack.clearSelection()
    const segment = state.segments[index]
    if (segment) {
      state.selectedSegmentIndex = index
      state.playFrom = segment.from
      state.playTo = segment.to
      state.currentTime = segment.from
    } else {
      state.selectedSegmentIndex = -1
      state.playFrom = state.from
      state.playTo = state.to
      state.currentTime = Math.min(state.to, Math.max(state.from, state.currentTime ?? state.from))
    }
    renderCurrent(true)
  }

  // Zoom/pan the visible playback window. Sessions remain quick-jump presets;
  // any custom window clears the active session highlight.
  const setWindow = (fromMs, toMsArg) => {
    if (!state.active || state.from == null || state.to == null) return
    pause()
    live.exitLive()
    selectedTrack.clearSelection()
    const minSpan = Math.max((Number(state.intervalSeconds) || 60) * 1000 * 2, 1000)
    let lo = Math.max(state.from, Math.min(Number(fromMs), Number(toMsArg)))
    let hi = Math.min(state.to, Math.max(Number(fromMs), Number(toMsArg)))
    if (hi - lo < minSpan) {
      const mid = (lo + hi) / 2
      lo = Math.max(state.from, mid - minSpan / 2)
      hi = Math.min(state.to, lo + minSpan)
      lo = Math.max(state.from, hi - minSpan)
    }
    state.playFrom = lo
    state.playTo = hi
    state.selectedSegmentIndex = -1
    state.currentTime = Math.min(hi, Math.max(lo, state.currentTime ?? hi))
    renderCurrent(true)
  }

  const selectDataset = async (dataId) => {
    if (!dataId) return
    pause()
    live.exitLive()
    selectedTrack.clearSelection()
    state.loading = true
    state.error = ''
    try {
      const range = await fetchHistoryRange(apiBaseUrl, dataId)
      if (!range || !range.count || !range.from) {
        state.error = 'No history has been recorded for this dataset yet.'
        state.active = false
        state.dataId = ''
        return
      }
      const entry = dataLayers.enterSimulator(dataId)
      if (!entry) {
        state.error = 'No matching map layer for this dataset.'
        return
      }
      layerEntry = entry
      frame.reset()
      smooth.reset()

      const framesResponse = await fetchHistoryFrames(apiBaseUrl, dataId)
      state.active = true
      state.dataId = dataId
      state.from = toMs(range.from)
      state.to = toMs(range.to)
      state.count = range.count
      state.intervalSeconds = Number(range.intervalSeconds) || 60
      state.frames = Array.isArray(framesResponse?.frames)
        ? framesResponse.frames.map(toMs).filter((value) => value != null)
        : []
      state.segments = deriveSegments()
      state.selectedSegmentIndex = -1
      state.playFrom = state.from
      state.playTo = state.to
      state.currentTime = state.to
      state.mode = 'history'
      if (state.smooth) {
        await smooth.loadTracks()
      } else {
        frame.applyActiveFrame(true)
      }
    } catch (error) {
      console.error(error)
      state.error = 'Failed to load history.'
    } finally {
      state.loading = false
    }
  }

  const stop = () => {
    pause()
    smooth.abortLoad()
    live.stopLive()
    if (debounceTimer) clearTimeout(debounceTimer)
    frame.invalidate()
    frame.reset()
    smooth.reset()
    selectedTrack.reset()
    dataLayers.exitSimulator()
    layerEntry = null
    Object.assign(state, createState())
  }

  // --- Global transport shortcuts --------------------------------------------

  useSimulatorShortcuts({
    isActive: () => state.active,
    togglePlay,
    stepFrame,
    seekStart: () => setTime(state.playFrom),
    seekEnd: () => setTime(state.playTo)
  })

  onBeforeUnmount(() => {
    stopRaf()
    smooth.abortLoad()
    live.stopLive()
    if (debounceTimer) clearTimeout(debounceTimer)
  })

  return {
    simulatorState: state,
    simulatorCandidates: candidates,
    simulatorSpeeds: SPEED_PRESETS,
    selectSimulatorDataset: selectDataset,
    setSimulatorTime: setTime,
    toggleSimulatorPlay: togglePlay,
    setSimulatorSpeed: setSpeed,
    stepSimulatorFrame: stepFrame,
    toggleSimulatorSmooth: toggleSmooth,
    selectSimulatorSegment: selectSegment,
    setSimulatorWindow: setWindow,
    toggleSimulatorLive: live.toggleLive,
    toggleSimulatorAutoFollow: selectedTrack.toggleAutoFollow,
    selectSimulatorFeature: selectedTrack.selectFeature,
    clearSimulatorSelection: selectedTrack.clearSelection,
    toggleSimulatorTrack: selectedTrack.toggleSelectedTrack,
    stopSimulator: stop
  }
}
