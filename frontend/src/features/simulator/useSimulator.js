import { computed, onBeforeUnmount, reactive } from 'vue'
import { applyDataStyleHandler } from '../data/styleHandlers'
import { fetchHistoryAt, fetchHistoryFrames, fetchHistoryRange, streamHistoryTrack } from './simulatorApi'
import {
  activePropertiesAt,
  interpolateSegmentsAt,
  normalizeSmoothTracks
} from './trackInterpolation'
import { deriveSessionSegments, nearestFrame } from './playbackTimeline'
import { useSelectedTrack } from './useSelectedTrack'
import { useSimulatorShortcuts } from './useSimulatorShortcuts'

const SMOOTH_RENDER_INTERVAL_MS = 40

const SPEED_PRESETS = [1, 10, 30, 60]
const DEFAULT_SPEED = 30

// A gap between captures longer than this many poll cycles is treated as a
// recording interruption that splits the timeline into separate sessions.
const GLOBAL_GAP_FACTOR = 4

const toMs = (iso) => {
  if (!iso) return null
  const ms = new Date(iso).getTime()
  return Number.isFinite(ms) ? ms : null
}

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
 * Playback advances a virtual clock with requestAnimationFrame; the rendered
 * GeoJSON only changes when the clock crosses into a new capture (frame), so
 * the network cost is one request per capture (cached + prefetched), not per
 * animation tick. Smooth between-capture motion is Phase 5 (OSRM tracks).
 *
 * @param apiBaseUrl backend base URL
 * @param dataLayers subset of useDataLayers: { getSimulatorCandidates, enterSimulator, exitSimulator, setSimulatorGeoJson }
 */
export const useSimulator = (apiBaseUrl, dataLayers) => {
  const state = reactive(createState())
  const candidates = computed(() => dataLayers.getSimulatorCandidates())

  let layerEntry = null
  let frameSequence = 0
  let frameCache = new Map()
  let activeFrameMs = null
  let rafId = null
  let lastTickReal = null
  let debounceTimer = null
  let smoothTracks = []
  let lastSmoothRenderReal = 0
  let smoothAbort = null
  let liveTimer = null

  // Selected entity + trajectory overlay + auto-follow. Created early so its
  // syncSelectedPosition/updateTrackProgress/clearSelection are available to the
  // frame, smooth, clock, and live functions defined below.
  const {
    updateTrackProgress,
    clearSelection,
    selectFeature,
    syncSelectedPosition,
    toggleSelectedTrack,
    toggleAutoFollow,
    reset: resetSelectedTrack
  } = useSelectedTrack({ apiBaseUrl, state, getSmoothTracks: () => smoothTracks })

  const stopLive = () => {
    if (liveTimer) {
      clearInterval(liveTimer)
      liveTimer = null
    }
  }

  const exitLive = () => {
    if (state.mode === 'live') {
      state.mode = 'history'
      stopLive()
    }
  }

  const abortSmoothLoad = () => {
    if (smoothAbort) {
      smoothAbort.abort()
      smoothAbort = null
    }
  }

  const stopRaf = () => {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    lastTickReal = null
  }

  const getFrame = async (ms) => {
    if (frameCache.has(ms)) return frameCache.get(ms)
    const geojson = await fetchHistoryAt(apiBaseUrl, state.dataId, ms)
    const styled = applyDataStyleHandler(geojson, layerEntry)
    frameCache.set(ms, styled)
    return styled
  }

  const prefetchNext = (ms) => {
    const index = state.frames.indexOf(ms)
    if (index >= 0 && index + 1 < state.frames.length) {
      const next = state.frames[index + 1]
      if (!frameCache.has(next)) getFrame(next).catch(() => {})
    }
  }

  const showFrame = async (ms) => {
    const sequence = ++frameSequence
    state.loading = true
    try {
      const styled = await getFrame(ms)
      if (sequence !== frameSequence) return
      dataLayers.setSimulatorGeoJson(styled)
      state.featureCount = Array.isArray(styled?.features) ? styled.features.length : 0
      syncSelectedPosition(styled?.features)
      state.error = ''
    } catch (error) {
      if (sequence !== frameSequence) return
      console.error(error)
      state.error = 'Failed to load frame.'
    } finally {
      if (sequence === frameSequence) state.loading = false
    }
  }

  const applyActiveFrame = (force = false) => {
    const target = nearestFrame(state.frames, state.currentTime)
    if (!force && target === activeFrameMs) return
    activeFrameMs = target
    showFrame(target)
    prefetchNext(target)
  }

  // --- Smooth (OSRM road-following) playback ---------------------------------

  const renderSmooth = (ms) => {
    if (!smoothTracks.length) return
    const features = []
    for (const track of smoothTracks) {
      const position = interpolateSegmentsAt(track.segments, ms)
      if (!position) continue
      features.push({
        type: 'Feature',
        properties: { ...activePropertiesAt(track.samples, ms), __trackKey: track.key },
        geometry: { type: 'Point', coordinates: position }
      })
    }
    const styled = applyDataStyleHandler({ type: 'FeatureCollection', features }, layerEntry)
    dataLayers.setSimulatorGeoJson(styled)
    state.featureCount = features.length
    syncSelectedPosition(features)
  }

  const loadTracks = async () => {
    if (!state.dataId) return
    abortSmoothLoad()
    smoothAbort = new AbortController()
    const controller = smoothAbort
    state.loading = true
    state.smoothing = true
    state.smoothProgress = { done: 0, total: 0 }
    try {
      const response = await streamHistoryTrack(apiBaseUrl, state.dataId, state.from, state.to, {
        signal: controller.signal,
        onProgress: ({ done, total }) => {
          state.smoothProgress = { done: Number(done) || 0, total: Number(total) || 0 }
        }
      })
      smoothTracks = normalizeSmoothTracks(response?.tracks)
      renderSmooth(state.currentTime)
      state.error = ''
    } catch (error) {
      if (error?.name === 'AbortError' || controller.signal.aborted) return
      console.error(error)
      state.error = 'Failed to load smooth tracks.'
    } finally {
      if (smoothAbort === controller) smoothAbort = null
      if (!controller.signal.aborted) {
        state.smoothing = false
        state.loading = false
      }
    }
  }

  const renderCurrent = (force = false) => {
    if (state.smooth && smoothTracks.length) renderSmooth(state.currentTime)
    else applyActiveFrame(force)
    updateTrackProgress()
  }

  const setSmooth = async (enabled) => {
    state.smooth = enabled === true
    if (state.smooth) {
      await loadTracks()
    } else {
      abortSmoothLoad()
      state.smoothing = false
      smoothTracks = []
      applyActiveFrame(true)
    }
  }

  const toggleSmooth = () => setSmooth(!state.smooth)

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
    if (state.smooth && smoothTracks.length) {
      if (nowReal - lastSmoothRenderReal >= SMOOTH_RENDER_INTERVAL_MS) {
        lastSmoothRenderReal = nowReal
        renderSmooth(state.currentTime)
      }
    } else {
      applyActiveFrame()
    }
    updateTrackProgress()
    rafId = requestAnimationFrame(tick)
  }

  const play = () => {
    if (!state.active || state.currentTime == null) return
    exitLive()
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
    exitLive()
    const lo = state.playFrom ?? state.from
    const hi = state.playTo ?? state.to
    const frames = state.frames.filter((frame) => frame >= lo && frame <= hi)
    if (!frames.length) return
    let index = frames.indexOf(activeFrameMs)
    if (index < 0) index = frames.findIndex((frame) => frame >= state.currentTime)
    if (index < 0) index = frames.length - 1
    index = Math.min(frames.length - 1, Math.max(0, index + (direction >= 0 ? 1 : -1)))
    state.currentTime = frames[index]
    renderCurrent(true)
  }

  const setTime = (ms) => {
    if (!state.active || state.playFrom == null || state.playTo == null) return
    pause()
    exitLive()
    const clamped = Math.min(state.playTo, Math.max(state.playFrom, Number(ms)))
    state.currentTime = clamped
    updateTrackProgress()
    if (state.smooth && smoothTracks.length) {
      renderSmooth(clamped)
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => applyActiveFrame(), 80)
  }

  // Split the capture timeline into recording sessions on large gaps.
  const deriveSegments = () => deriveSessionSegments(state.frames, state.intervalSeconds, GLOBAL_GAP_FACTOR)

  const selectSegment = (index) => {
    if (!state.active) return
    pause()
    exitLive()
    clearSelection()
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

  // --- Live mode -------------------------------------------------------------
  // Pins the clock to the leading edge and polls for newly recorded captures.
  const pollLive = async () => {
    if (state.mode !== 'live' || !state.dataId) return
    try {
      const range = await fetchHistoryRange(apiBaseUrl, state.dataId)
      const newTo = toMs(range?.to)
      if (newTo == null) return
      if (newTo > state.to) {
        state.to = newTo
        state.count = Number(range.count) || state.count
        const framesResponse = await fetchHistoryFrames(apiBaseUrl, state.dataId)
        if (Array.isArray(framesResponse?.frames)) {
          state.frames = framesResponse.frames.map(toMs).filter((value) => value != null)
        }
        state.segments = deriveSegments()
      }
      // Keep the clock pinned to "now".
      state.playFrom = state.from
      state.playTo = state.to
      state.currentTime = state.to
      applyActiveFrame(true)
    } catch (error) {
      console.error(error)
    }
  }

  const startLive = () => {
    stopLive()
    const everyMs = Math.max(15000, (Number(state.intervalSeconds) || 60) * 1000)
    liveTimer = setInterval(pollLive, everyMs)
  }

  const toggleLive = () => {
    if (state.mode === 'live') {
      exitLive()
      return
    }
    pause()
    // Live follows the leading edge as frames; smooth tracks would be stale.
    abortSmoothLoad()
    state.smoothing = false
    state.smooth = false
    smoothTracks = []
    state.selectedSegmentIndex = -1
    clearSelection()
    state.mode = 'live'
    state.playFrom = state.from
    state.playTo = state.to
    state.currentTime = state.to
    applyActiveFrame(true)
    pollLive()
    startLive()
  }

  // Zoom/pan the visible playback window. Sessions remain quick-jump presets;
  // any custom window clears the active session highlight.
  const setWindow = (fromMs, toMs) => {
    if (!state.active || state.from == null || state.to == null) return
    pause()
    exitLive()
    clearSelection()
    const minSpan = Math.max((Number(state.intervalSeconds) || 60) * 1000 * 2, 1000)
    let lo = Math.max(state.from, Math.min(Number(fromMs), Number(toMs)))
    let hi = Math.min(state.to, Math.max(Number(fromMs), Number(toMs)))
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
    exitLive()
    clearSelection()
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
      frameCache = new Map()
      activeFrameMs = null
      smoothTracks = []

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
        await loadTracks()
      } else {
        applyActiveFrame(true)
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
    abortSmoothLoad()
    stopLive()
    if (debounceTimer) clearTimeout(debounceTimer)
    frameSequence += 1
    frameCache = new Map()
    activeFrameMs = null
    smoothTracks = []
    resetSelectedTrack()
    dataLayers.exitSimulator()
    layerEntry = null
    Object.assign(state, createState())
  }

  // Global transport shortcuts (active only during playback; ignored while a
  // form control or the timeline slider has focus so it doesn't double-fire).
  useSimulatorShortcuts({
    isActive: () => state.active,
    togglePlay,
    stepFrame,
    seekStart: () => setTime(state.playFrom),
    seekEnd: () => setTime(state.playTo)
  })

  onBeforeUnmount(() => {
    stopRaf()
    abortSmoothLoad()
    stopLive()
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
    toggleSimulatorLive: toggleLive,
    toggleSimulatorAutoFollow: toggleAutoFollow,
    selectSimulatorFeature: selectFeature,
    clearSimulatorSelection: clearSelection,
    toggleSimulatorTrack: toggleSelectedTrack,
    stopSimulator: stop
  }
}
