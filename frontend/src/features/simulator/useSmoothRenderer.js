import { applyDataStyleHandler } from '../data/styleHandlers'
import { streamHistoryTrack } from './simulatorApi'
import { activePropertiesAt, interpolateSegmentsAt, isWithinTrackSegment, normalizeSmoothTracks } from './trackInterpolation'

// ~60fps cap for the between-capture interpolated render during continuous play.
const SMOOTH_RENDER_INTERVAL_MS = 16

// Smooth (OSRM road-following) rendering strategy: streams per-entity tracks
// once, then interpolates each entity's position at the clock instant. Owns the
// loaded tracks, the in-flight stream's AbortController, and the play-loop
// throttle clock. Reads/writes the shared playback `state`.
export const useSmoothRenderer = ({ apiBaseUrl, state, dataLayers, getLayerEntry, syncSelectedPosition }) => {
  let smoothTracks = []
  let smoothAbort = null
  let lastSmoothRenderReal = 0
  // Time window the loaded tracks cover. Tracks are only built for the active
  // playback window (selected session/day), not the whole recording, so large
  // datasets smooth just the part being watched.
  let loadedFrom = null
  let loadedTo = null

  const hasTracks = () => smoothTracks.length > 0
  const getTracks = () => smoothTracks
  const coversWindow = (lo, hi) =>
    smoothTracks.length > 0 && loadedFrom != null && loadedTo != null && lo >= loadedFrom && hi <= loadedTo
  const reset = () => {
    smoothTracks = []
    loadedFrom = null
    loadedTo = null
  }

  const abortLoad = () => {
    if (smoothAbort) {
      smoothAbort.abort()
      smoothAbort = null
    }
  }

  // Turn smoothing fully off: abort any in-flight stream, drop loaded tracks,
  // and clear every smooth-related flag. This is the ONE place that knows the
  // full checklist — callers (smooth toggle, live mode, simulator teardown)
  // must not reach into the individual fields themselves.
  const disable = () => {
    abortLoad()
    state.smooth = false
    state.smoothing = false
    state.smoothProgress = { done: 0, total: 0 }
    reset()
  }

  const renderSmooth = (ms) => {
    if (!smoothTracks.length) return
    const features = []
    for (const track of smoothTracks) {
      // Only render an entity when the clock is inside one of its recorded
      // segments; outside its lifetime and during between-session gaps it is
      // absent, never frozen at a stale (e.g. previous-day) position.
      if (!isWithinTrackSegment(track.segments, ms)) continue
      const position = interpolateSegmentsAt(track.segments, ms)
      if (!position) continue
      features.push({
        type: 'Feature',
        properties: { ...activePropertiesAt(track.samples, ms), __trackKey: track.key },
        geometry: { type: 'Point', coordinates: position }
      })
    }
    const styled = applyDataStyleHandler({ type: 'FeatureCollection', features }, getLayerEntry())
    dataLayers.setSimulatorGeoJson(styled)
    if (state.featureCount !== features.length) state.featureCount = features.length
    syncSelectedPosition(features)
  }

  // Play-loop render: when `realNow` is given, cap to SMOOTH_RENDER_INTERVAL_MS;
  // a null `realNow` renders immediately (seeks, single steps).
  const renderTick = (ms, realNow = null) => {
    if (realNow != null) {
      if (realNow - lastSmoothRenderReal < SMOOTH_RENDER_INTERVAL_MS) return
      lastSmoothRenderReal = realNow
    }
    renderSmooth(ms)
  }

  const loadTracks = async () => {
    if (!state.dataId) return
    abortLoad()
    smoothAbort = new AbortController()
    const controller = smoothAbort
    // Smooth only the active playback window (the selected recording session),
    // not the dataset's full range.
    const from = state.playFrom ?? state.from
    const to = state.playTo ?? state.to
    state.loading = true
    state.smoothing = true
    state.smoothProgress = { done: 0, total: 0 }
    try {
      const response = await streamHistoryTrack(apiBaseUrl, state.dataId, from, to, {
        signal: controller.signal,
        onProgress: ({ done, total }) => {
          state.smoothProgress = { done: Number(done) || 0, total: Number(total) || 0 }
        }
      })
      smoothTracks = normalizeSmoothTracks(response?.tracks)
      loadedFrom = from
      loadedTo = to
      renderSmooth(state.currentTime)
      state.error = ''
    } catch (error) {
      if (error?.name === 'AbortError' || controller.signal.aborted) return
      console.error(error)
      state.error = '載入道路平滑軌跡失敗。'
    } finally {
      if (smoothAbort === controller) smoothAbort = null
      // Once this is the abandoned-latest load (no newer load replaced it),
      // clear the smooth-specific flag even on abort so the UI never sticks.
      // `loading` is shared with frame loads, so only clear it on success to
      // avoid clobbering a frame fetch that an abort path may have started.
      if (smoothAbort === null) {
        state.smoothing = false
      }
      if (!controller.signal.aborted) {
        state.loading = false
      }
    }
  }

  return { renderSmooth, renderTick, loadTracks, abortLoad, disable, hasTracks, getTracks, coversWindow, reset }
}
