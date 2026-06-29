import { applyDataStyleHandler } from '../data/styleHandlers'
import { fetchHistoryAt } from './simulatorApi'
import { nearestFrame } from './playbackTimeline'

// Frame-based rendering strategy: shows the captured GeoJSON at the nearest
// frame, advancing only when the clock crosses into a new capture. Owns the
// per-frame cache, the currently-shown frame, and a request sequence guard so a
// slow fetch can't overwrite a newer one. Reads the shared playback `state` and
// pushes the styled frame through `dataLayers.setSimulatorGeoJson`.
export const useFrameRenderer = ({ apiBaseUrl, state, dataLayers, getLayerEntry, syncSelectedPosition }) => {
  let frameCache = new Map()
  let activeFrameMs = null
  let frameSequence = 0

  const getFrame = async (ms) => {
    if (frameCache.has(ms)) return frameCache.get(ms)
    const geojson = await fetchHistoryAt(apiBaseUrl, state.dataId, ms)
    const styled = applyDataStyleHandler(geojson, getLayerEntry())
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

  // Drop the cache and the "shown" marker (e.g. when switching datasets).
  const reset = () => {
    frameCache = new Map()
    activeFrameMs = null
  }

  // Invalidate any in-flight showFrame so it won't apply after teardown.
  const invalidate = () => {
    frameSequence += 1
  }

  const getActiveFrameMs = () => activeFrameMs

  return { applyActiveFrame, reset, invalidate, getActiveFrameMs }
}
