import { applyDataStyleHandler } from '../data/styleHandlers'
import { streamHistoryTrack } from './simulatorApi'
import { activePropertiesAt, interpolateSegmentsAt, normalizeSmoothTracks } from './trackInterpolation'

// ~25fps cap for the between-capture interpolated render during continuous play.
const SMOOTH_RENDER_INTERVAL_MS = 40

// Smooth (OSRM road-following) rendering strategy: streams per-entity tracks
// once, then interpolates each entity's position at the clock instant. Owns the
// loaded tracks, the in-flight stream's AbortController, and the play-loop
// throttle clock. Reads/writes the shared playback `state`.
export const useSmoothRenderer = ({ apiBaseUrl, state, dataLayers, getLayerEntry, syncSelectedPosition }) => {
  let smoothTracks = []
  let smoothAbort = null
  let lastSmoothRenderReal = 0

  const hasTracks = () => smoothTracks.length > 0
  const getTracks = () => smoothTracks
  const reset = () => {
    smoothTracks = []
  }

  const abortLoad = () => {
    if (smoothAbort) {
      smoothAbort.abort()
      smoothAbort = null
    }
  }

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
    const styled = applyDataStyleHandler({ type: 'FeatureCollection', features }, getLayerEntry())
    dataLayers.setSimulatorGeoJson(styled)
    state.featureCount = features.length
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

  return { renderSmooth, renderTick, loadTracks, abortLoad, hasTracks, getTracks, reset }
}
