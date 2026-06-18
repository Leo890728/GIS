import { computed, onBeforeUnmount, reactive } from 'vue'
import { applyDataStyleHandler } from '../data/styleHandlers'
import { fetchHistoryAt, fetchHistoryFrames, fetchHistoryRange, fetchHistoryTrack } from './simulatorApi'

const SMOOTH_RENDER_INTERVAL_MS = 40

const SPEED_PRESETS = [1, 10, 30, 60]
const DEFAULT_SPEED = 30

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
  featureCount: 0,
  playing: false,
  speed: DEFAULT_SPEED,
  smooth: false,
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

  const stopRaf = () => {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    lastTickReal = null
  }

  const nearestFrameMs = (ms) => {
    if (!state.frames.length) return ms
    let lo = state.frames[0]
    for (const frame of state.frames) {
      if (frame <= ms) lo = frame
      else break
    }
    return lo
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
    const target = nearestFrameMs(state.currentTime)
    if (!force && target === activeFrameMs) return
    activeFrameMs = target
    showFrame(target)
    prefetchNext(target)
  }

  // --- Smooth (OSRM road-following) playback ---------------------------------

  const interpolateAt = (path, ms) => {
    if (!path.length) return null
    if (ms <= path[0].tMs) return [path[0].lng, path[0].lat]
    const last = path[path.length - 1]
    if (ms >= last.tMs) return [last.lng, last.lat]
    for (let i = 0; i < path.length - 1; i += 1) {
      const a = path[i]
      const b = path[i + 1]
      if (ms >= a.tMs && ms <= b.tMs) {
        const span = b.tMs - a.tMs
        const f = span > 0 ? (ms - a.tMs) / span : 0
        return [a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f]
      }
    }
    return [last.lng, last.lat]
  }

  const activePropertiesAt = (samples, ms) => {
    if (!samples || !samples.length) return {}
    let chosen = samples[0].properties
    for (const sample of samples) {
      if (sample.tMs <= ms) chosen = sample.properties
      else break
    }
    return chosen
  }

  const renderSmooth = (ms) => {
    if (!smoothTracks.length) return
    const features = []
    for (const track of smoothTracks) {
      const position = interpolateAt(track.path, ms)
      if (!position) continue
      features.push({
        type: 'Feature',
        properties: activePropertiesAt(track.samples, ms),
        geometry: { type: 'Point', coordinates: position }
      })
    }
    const styled = applyDataStyleHandler({ type: 'FeatureCollection', features }, layerEntry)
    dataLayers.setSimulatorGeoJson(styled)
    state.featureCount = features.length
  }

  const loadTracks = async () => {
    if (!state.dataId) return
    state.loading = true
    try {
      const response = await fetchHistoryTrack(apiBaseUrl, state.dataId, state.from, state.to)
      smoothTracks = (response?.tracks || [])
        .map((track) => ({
          key: track.key,
          properties: track.properties || {},
          path: (track.path || [])
            .map((point) => ({ tMs: new Date(point.t).getTime(), lng: point.lng, lat: point.lat }))
            .filter((point) => Number.isFinite(point.tMs)),
          samples: (track.samples || [])
            .map((sample) => ({ tMs: new Date(sample.t).getTime(), properties: sample.properties || {} }))
            .filter((sample) => Number.isFinite(sample.tMs))
        }))
        .filter((track) => track.path.length > 0)
      renderSmooth(state.currentTime)
      state.error = ''
    } catch (error) {
      console.error(error)
      state.error = 'Failed to load smooth tracks.'
    } finally {
      state.loading = false
    }
  }

  const renderCurrent = (force = false) => {
    if (state.smooth && smoothTracks.length) renderSmooth(state.currentTime)
    else applyActiveFrame(force)
  }

  const setSmooth = async (enabled) => {
    state.smooth = enabled === true
    if (state.smooth) {
      await loadTracks()
    } else {
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
    if (next >= state.to) {
      state.currentTime = state.to
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
    rafId = requestAnimationFrame(tick)
  }

  const play = () => {
    if (!state.active || state.currentTime == null) return
    if (state.currentTime >= state.to) state.currentTime = state.from
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
    if (!state.frames.length) return
    let index = state.frames.indexOf(activeFrameMs)
    if (index < 0) index = state.frames.findIndex((frame) => frame >= state.currentTime)
    if (index < 0) index = state.frames.length - 1
    index = Math.min(state.frames.length - 1, Math.max(0, index + (direction >= 0 ? 1 : -1)))
    state.currentTime = state.frames[index]
    renderCurrent(true)
  }

  const setTime = (ms) => {
    if (!state.active || state.from == null || state.to == null) return
    pause()
    const clamped = Math.min(state.to, Math.max(state.from, Number(ms)))
    state.currentTime = clamped
    if (state.smooth && smoothTracks.length) {
      renderSmooth(clamped)
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => applyActiveFrame(), 80)
  }

  const selectDataset = async (dataId) => {
    if (!dataId) return
    pause()
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
      state.currentTime = state.to
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
    if (debounceTimer) clearTimeout(debounceTimer)
    frameSequence += 1
    frameCache = new Map()
    activeFrameMs = null
    smoothTracks = []
    dataLayers.exitSimulator()
    layerEntry = null
    Object.assign(state, createState())
  }

  onBeforeUnmount(() => {
    stopRaf()
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
    stopSimulator: stop
  }
}
