import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { fetchHistoryFrames, fetchHistoryRange } from './simulatorApi'
import { deriveSessionSegments, toMs } from './playbackTimeline'
import { bearingToTruckIconSuffix, buildRouteHeatGeoJson, buildRoutePlanTracks, pathBearingAt } from './routePlanTracks'
import { activePropertiesAt, interpolateSegmentsAt, pathIndexAt, remainingCoords, traveledCoords } from './trackInterpolation'
import { getVehicleColor } from '../route/useRoutePlanner'
import { useFrameRenderer } from './useFrameRenderer'
import { useSmoothRenderer } from './useSmoothRenderer'
import { useSelectedTrack } from './useSelectedTrack'
import { useLiveMode } from './useLiveMode'
import { useSimulatorShortcuts } from './useSimulatorShortcuts'

const SPEED_PRESETS = [1, 10, 30, 60]
const DEFAULT_SPEED = 30

// Shared playback blackboard. Fields are grouped by domain, and each group has
// ONE owning writer (other modules read only) — keep it that way:
const createState = () => ({
  // Dataset identity + timeline (writer: selectDataset/activate, live poll).
  active: false,
  dataId: '', // 'route-plan' is the sentinel for solved-route playback
  from: null,
  to: null,
  count: 0,
  intervalSeconds: 60,
  frames: [],
  segments: [],
  // Transport / virtual clock (writer: the clock + window/segment setters; all
  // setters pause() first — during play `currentTime` is a ~10Hz mirror of the
  // precise clock, see tick()).
  currentTime: null,
  playFrom: null,
  playTo: null,
  playing: false,
  speed: DEFAULT_SPEED,
  selectedSegmentIndex: -1,
  mode: 'history', // 'history' | 'live' | 'route-plan'
  // Selection + camera follow (writer: useSelectedTrack / selectRouteVehicle).
  selected: null,
  selectedPos: null,
  autoFollow: false,
  followCenter: null,
  // Selected-entity trajectory overlay (writer: useSelectedTrack).
  trackGeoJson: null,
  trackTraveledGeoJson: null,
  trackEndpointsGeoJson: null,
  trackLoading: false,
  trackError: '',
  // Render/progress channels — single-writer each: `loading` belongs to the
  // frame renderer (and dataset activation), `smoothing`/`smoothProgress` to
  // the smooth renderer.
  featureCount: 0,
  routeHeatmap: false,
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

  // Route-plan playback: synthetic tracks built from a solved VRP result instead
  // of recorded history. Rendered into its own GeoJSON ref (a dedicated map
  // layer), so no live data layer is taken over.
  let routePlanTracks = []
  let lastRoutePlanRenderReal = 0
  const routeSimGeoJson = ref({ type: 'FeatureCollection', features: [] })
  // Per-frame route split: the already-traveled portion (drawn translucent) and
  // the remaining portion (solid), both colored per vehicle.
  const routeSimTraveledGeoJson = ref({ type: 'FeatureCollection', features: [] })
  const routeSimRemainingGeoJson = ref({ type: 'FeatureCollection', features: [] })
  // Pickup stops weighted by collected garbage, for the toggleable heatmap view.
  const routeSimHeatGeoJson = ref({ type: 'FeatureCollection', features: [] })
  // Per-vehicle playback progress `{ [vehicleId]: { visitedStops } }` consumed
  // by the map to fade already-served stops.
  const routeSimProgress = ref({})

  const isRoutePlanMode = () => state.mode === 'route-plan'

  const clearRoutePlan = () => {
    routePlanTracks = []
    routeSimGeoJson.value = { type: 'FeatureCollection', features: [] }
    routeSimTraveledGeoJson.value = { type: 'FeatureCollection', features: [] }
    routeSimRemainingGeoJson.value = { type: 'FeatureCollection', features: [] }
    routeSimHeatGeoJson.value = { type: 'FeatureCollection', features: [] }
    routeSimProgress.value = {}
  }

  // The traveled/remaining split lines carry the full road geometry, so every
  // reassignment costs a MapLibre setData (reparse + GPU upload) of thousands
  // of vertices per vehicle. Their shape only changes when some vehicle crosses
  // a geometry vertex, so rebuilds are gated on that signature; the interpolated
  // vehicle points still move every frame. `forceLines` (seeks, selection,
  // periodic refresh) bypasses the gate so the line tips re-attach to the trucks.
  let lastLineSignature = null

  const renderRoutePlan = (ms, forceLines = true) => {
    const features = []
    let lineSignature = ''
    for (const track of routePlanTracks) {
      // Clamp to the endpoints so vehicles wait at the depot before departure
      // and rest at the end depot after finishing, instead of disappearing.
      const position = interpolateSegmentsAt(track.segments, ms)
      if (!position) continue
      const path = track.segments[0].path
      features.push({
        type: 'Feature',
        properties: {
          ...track.properties,
          ...activePropertiesAt(track.samples, ms),
          __trackKey: track.key,
          truckIconId: `tcg-v2-garbage-${bearingToTruckIconSuffix(pathBearingAt(path, ms))}`
        },
        geometry: { type: 'Point', coordinates: position }
      })
      lineSignature += `${track.key}:${pathIndexAt(path, ms)}|`
    }
    routeSimGeoJson.value = { type: 'FeatureCollection', features }
    if (state.featureCount !== features.length) state.featureCount = features.length

    if (forceLines || lineSignature !== lastLineSignature) {
      lastLineSignature = lineSignature
      const traveledFeatures = []
      const remainingFeatures = []
      const progress = {}
      for (const track of routePlanTracks) {
        const path = track.segments[0]?.path || []
        const traveled = traveledCoords(path, ms)
        if (traveled.length >= 2) {
          traveledFeatures.push({
            type: 'Feature',
            properties: { ...track.properties },
            geometry: { type: 'LineString', coordinates: traveled }
          })
        }
        const remaining = remainingCoords(path, ms)
        if (remaining.length >= 2) {
          remainingFeatures.push({
            type: 'Feature',
            properties: { ...track.properties },
            geometry: { type: 'LineString', coordinates: remaining }
          })
        }
        progress[track.properties.vehicleId] = {
          visitedStops: track.stopTimesMs.filter((tMs) => tMs <= ms).length
        }
      }
      routeSimTraveledGeoJson.value = { type: 'FeatureCollection', features: traveledFeatures }
      routeSimRemainingGeoJson.value = { type: 'FeatureCollection', features: remainingFeatures }
      routeSimProgress.value = progress
    }
    // Keep the selection ring pinned to the selected vehicle as it moves, and
    // recenter the camera when auto-follow is on.
    if (state.selected?.key != null) {
      const match = features.find((feature) => feature.properties.__trackKey === state.selected.key)
      state.selectedPos = match ? match.geometry.coordinates : null
      if (state.autoFollow && state.selectedPos) state.followCenter = state.selectedPos
    }
  }

  // Selecting a simulated vehicle drives the right-hand vehicle drawer
  // (timeline + current load); no history-track fetch is involved.
  const selectRouteVehicle = (payload) => {
    if (!payload || payload.key == null || payload.key === '') {
      state.selected = null
      state.selectedPos = null
      state.autoFollow = false
      state.followCenter = null
      return
    }
    state.selected = { key: String(payload.key), properties: payload.properties || {} }
    renderRoutePlan(state.currentTime)
  }

  const selectedRouteVehicle = computed(() => {
    if (state.mode !== 'route-plan' || !state.selected) return null
    const track = routePlanTracks.find((candidate) => candidate.key === state.selected.key)
    if (!track) return null
    return {
      key: track.key,
      vehicleId: track.properties.vehicleId,
      vehicleColor: track.properties.vehicleColor,
      stops: track.samples.map((sample) => ({
        tMs: sample.tMs,
        name: sample.properties.stopName,
        type: sample.properties.stopType,
        loadKg: sample.properties.loadKg,
        instructions: sample.properties.instructions || []
      }))
    }
  })

  // Same ~60fps cap the smooth renderer uses during continuous play. During
  // play the heavy split lines only rebuild on vertex crossings (see
  // renderRoutePlan), plus a ~5Hz forced refresh so the line tips never trail
  // visibly on long straight segments with sparse vertices.
  let lastLineForceReal = 0
  const renderRoutePlanTick = (ms, realNow = null) => {
    if (realNow != null) {
      if (realNow - lastRoutePlanRenderReal < 16) return
      lastRoutePlanRenderReal = realNow
      const forceLines = realNow - lastLineForceReal >= 200
      if (forceLines) lastLineForceReal = realNow
      renderRoutePlan(ms, forceLines)
      return
    }
    renderRoutePlan(ms)
  }

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
    if (isRoutePlanMode()) {
      renderRoutePlanTick(ms, realNow)
      return
    }
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

  // The map renders straight from the precise clock (`clockMs`, a plain
  // variable), while the reactive mirror `state.currentTime` — which re-renders
  // every component showing the clock (control bar, panel, drawer) — is only
  // written ~10x/s during play. Seeks/pauses write it directly, and the tick
  // resyncs `clockMs` whenever an external write is detected, so paused reads
  // are always exact.
  let clockMs = null
  let lastWrittenClock = null
  let lastClockWriteReal = 0

  const tick = (nowReal) => {
    if (!state.playing) {
      stopRaf()
      return
    }
    if (lastTickReal == null) lastTickReal = nowReal
    const deltaReal = nowReal - lastTickReal
    lastTickReal = nowReal

    // A seek during play (control bar, shortcuts) wrote state.currentTime
    // directly; adopt it as the new clock origin. Also mark it as "written" so
    // the next tick doesn't re-adopt the same value and discard the progress
    // made since (the mirror lags the precise clock by up to one write window).
    if (state.currentTime !== lastWrittenClock) {
      clockMs = state.currentTime
      lastWrittenClock = state.currentTime
    }

    const next = clockMs + deltaReal * state.speed
    if (next >= state.playTo) {
      clockMs = state.playTo
      lastWrittenClock = state.playTo
      state.currentTime = state.playTo
      renderCurrent()
      pause()
      return
    }
    clockMs = next
    renderAt(next, { realNow: nowReal })
    if (nowReal - lastClockWriteReal >= 100) {
      lastClockWriteReal = nowReal
      lastWrittenClock = next
      state.currentTime = next
    }
    rafId = requestAnimationFrame(tick)
  }

  const play = () => {
    if (!state.active || state.currentTime == null) return
    live.exitLive()
    if (state.currentTime >= state.playTo) state.currentTime = state.playFrom
    clockMs = state.currentTime
    lastWrittenClock = state.currentTime
    state.playing = true
    lastTickReal = null
    rafId = requestAnimationFrame(tick)
  }

  const pause = () => {
    // Flush the precise clock so anything reading currentTime while paused
    // (step buttons, drawer, control bar) sees exactly where playback stopped.
    if (state.playing && clockMs != null && state.currentTime !== clockMs) {
      lastWrittenClock = clockMs
      state.currentTime = clockMs
    }
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
    if (isRoutePlanMode()) {
      renderRoutePlan(clamped)
      return
    }
    selectedTrack.updateTrackProgress()
    if (state.smooth && smooth.hasTracks()) {
      smooth.renderSmooth(clamped)
      return
    }
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => frame.applyActiveFrame(), 80)
  }

  // --- Smooth playback toggle ------------------------------------------------

  // After the playback window changes: if smoothing is on but the loaded
  // tracks don't cover the new window, rebuild them for it (smoothing is
  // window-scoped so big datasets only smooth the session being watched).
  const reloadSmoothForWindow = () => {
    if (!state.smooth) return
    const lo = state.playFrom ?? state.from
    const hi = state.playTo ?? state.to
    if (lo == null || hi == null || smooth.coversWindow(lo, hi)) return
    smooth.loadTracks().catch((error) => console.error(error))
  }

  const setSmooth = async (enabled) => {
    // Route-plan tracks already follow the road geometry; OSRM smoothing is a
    // history-playback concept and would fetch a nonexistent dataset.
    if (isRoutePlanMode()) return
    if (enabled === true) {
      state.smooth = true
      await smooth.loadTracks()
    } else {
      smooth.disable()
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
    reloadSmoothForWindow()
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
    reloadSmoothForWindow()
    renderCurrent(true)
  }

  const selectDataset = async (dataId) => {
    if (!dataId) return
    pause()
    live.exitLive()
    clearRoutePlan()
    if (isRoutePlanMode()) state.mode = 'history'
    selectedTrack.clearSelection()
    state.loading = true
    state.error = ''
    try {
      const range = await fetchHistoryRange(apiBaseUrl, dataId)
      if (!range || !range.count || !range.from) {
        state.error = '這個資料集尚未記錄歷史資料。'
        state.active = false
        state.dataId = ''
        return
      }
      const entry = dataLayers.enterSimulator(dataId)
      if (!entry) {
        state.error = '找不到此資料集對應的地圖圖層。'
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
      state.error = '載入歷史資料失敗。'
    } finally {
      state.loading = false
    }
  }

  const stop = () => {
    pause()
    smooth.disable()
    live.stopLive()
    if (debounceTimer) clearTimeout(debounceTimer)
    frame.invalidate()
    frame.reset()
    selectedTrack.reset()
    clearRoutePlan()
    dataLayers.exitSimulator()
    layerEntry = null
    Object.assign(state, createState())
  }

  // Play back a solved garbage-route result: all vehicles depart "now" and
  // follow their route geometry, pinned to the solver's per-leg travel times.
  const startRouteSimulation = (routeResult) => {
    const built = buildRoutePlanTracks(routeResult, Date.now(), getVehicleColor)
    if (!built.tracks.length) {
      state.error = '目前沒有可模擬的路線，請先在「路線」頁求解。'
      return
    }
    stop()
    routePlanTracks = built.tracks
    routeSimHeatGeoJson.value = buildRouteHeatGeoJson(routeResult)
    state.active = true
    state.mode = 'route-plan'
    state.dataId = 'route-plan'
    state.from = built.fromMs
    state.to = built.toMs
    state.count = built.frames.length
    state.intervalSeconds = 1
    state.frames = built.frames
    state.segments = []
    state.selectedSegmentIndex = -1
    state.playFrom = state.from
    state.playTo = state.to
    state.currentTime = state.from
    renderRoutePlan(state.currentTime)
    play()
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
    routeSimGeoJson,
    routeSimTraveledGeoJson,
    routeSimRemainingGeoJson,
    routeSimHeatGeoJson,
    routeSimProgress,
    selectedRouteVehicle,
    startRouteSimulation,
    toggleRouteHeatmap: () => {
      if (isRoutePlanMode()) state.routeHeatmap = !state.routeHeatmap
    },
    selectSimulatorDataset: selectDataset,
    setSimulatorTime: setTime,
    toggleSimulatorPlay: togglePlay,
    setSimulatorSpeed: setSpeed,
    stepSimulatorFrame: stepFrame,
    toggleSimulatorSmooth: toggleSmooth,
    selectSimulatorSegment: selectSegment,
    setSimulatorWindow: setWindow,
    toggleSimulatorLive: () => {
      if (!isRoutePlanMode()) live.toggleLive()
    },
    toggleSimulatorAutoFollow: selectedTrack.toggleAutoFollow,
    selectSimulatorFeature: (payload) => {
      if (isRoutePlanMode()) selectRouteVehicle(payload)
      else selectedTrack.selectFeature(payload)
    },
    clearSimulatorSelection: () => {
      if (isRoutePlanMode()) selectRouteVehicle(null)
      else selectedTrack.clearSelection()
    },
    toggleSimulatorTrack: selectedTrack.toggleSelectedTrack,
    stopSimulator: stop
  }
}
