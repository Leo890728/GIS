import { fetchHistoryTrack } from './simulatorApi'
import {
  normalizeTrackSegments,
  segmentsToEndpointsGeoJson,
  segmentsToLineGeoJson,
  traveledCoords
} from './trackInterpolation'

// Manages the selected entity: selection state, its road-following trajectory
// overlay (base line + endpoints + the traveled portion that grows with the
// clock), and map auto-follow. Owns `selectedTrackSegments`; reads the shared
// playback `state` and a getter for already-loaded smooth tracks so an existing
// track can be reused instead of re-fetching from OSRM.
export const useSelectedTrack = ({ apiBaseUrl, state, getSmoothTracks }) => {
  // Normalized [{ path: [{ tMs, lng, lat }] }] of the drawn trajectory; used to
  // recolor the traveled portion as the clock advances.
  let selectedTrackSegments = null

  // The portion of each segment already traveled at the current instant.
  const updateTrackProgress = () => {
    if (!selectedTrackSegments) return
    const features = selectedTrackSegments
      .map((seg) => traveledCoords(seg.path, state.currentTime))
      .filter((coords) => coords.length >= 2)
      .map((coords) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } }))
    state.trackTraveledGeoJson = { type: 'FeatureCollection', features }
  }

  const showTrack = (track) => {
    const segments = normalizeTrackSegments(track)
    const baseLine = segmentsToLineGeoJson(segments)
    if (!baseLine) {
      state.trackError = 'No trajectory for this point.'
      return
    }
    selectedTrackSegments = segments
    state.trackGeoJson = baseLine
    state.trackEndpointsGeoJson = segmentsToEndpointsGeoJson(segments)
    updateTrackProgress()
  }

  const hideTrack = () => {
    selectedTrackSegments = null
    state.trackGeoJson = null
    state.trackTraveledGeoJson = null
    state.trackEndpointsGeoJson = null
  }

  const clearSelection = () => {
    state.selected = null
    state.selectedPos = null
    state.autoFollow = false
    state.trackError = ''
    hideTrack()
  }

  const selectFeature = (payload) => {
    if (!payload || payload.key == null) {
      clearSelection()
      return
    }
    // Selecting a different entity invalidates any drawn trajectory.
    if (state.selected?.key !== payload.key) hideTrack()
    state.selected = payload
    state.selectedPos = Array.isArray(payload.coordinates) ? payload.coordinates : null
    state.trackError = ''
  }

  // Keep the selection highlight on the selected entity as the clock moves:
  // pin the ring to its current-frame position (and recenter the map when
  // auto-follow is on), or hide it when the entity is absent from this frame.
  const syncSelectedPosition = (features) => {
    if (!state.selected) return
    const key = state.selected.key
    const match = (features || []).find((feature) => feature?.properties?.__trackKey === key)
    const coords = match?.geometry?.coordinates
    state.selectedPos = Array.isArray(coords) ? coords : null
    if (state.autoFollow && state.selectedPos) state.followCenter = state.selectedPos
  }

  // Toggle the selected entity's road-following trajectory overlay.
  const toggleSelectedTrack = async () => {
    if (!state.selected || !state.dataId) return
    if (state.trackGeoJson) {
      hideTrack()
      return
    }
    const key = state.selected.key
    const lo = state.playFrom ?? state.from
    const hi = state.playTo ?? state.to
    // Smooth tracks are streamed for the full from..to range; only reuse them
    // when the play window IS the full range. With a session/window selected,
    // fetch a window-bounded track so the overlay doesn't bleed into other
    // sessions.
    const isFullRange = lo === state.from && hi === state.to
    const cached = isFullRange ? getSmoothTracks().find((track) => track.key === key) : null
    if (cached) {
      showTrack(cached)
      return
    }
    state.trackLoading = true
    state.trackError = ''
    try {
      const response = await fetchHistoryTrack(apiBaseUrl, state.dataId, lo, hi)
      if (state.selected?.key !== key) return // selection changed mid-flight
      const track = (response?.tracks || []).find((entry) => entry.key === key)
      if (track) showTrack(track)
      else state.trackError = 'No trajectory for this point.'
    } catch (error) {
      console.error(error)
      state.trackError = 'Failed to load trajectory.'
    } finally {
      state.trackLoading = false
    }
  }

  // Auto-follow recenters the map on the *selected* entity as it moves; only
  // meaningful while a point is selected. Enabling it jumps to the selection's
  // current position right away.
  const toggleAutoFollow = () => {
    if (!state.selected) return
    state.autoFollow = !state.autoFollow
    if (state.autoFollow && Array.isArray(state.selectedPos)) {
      state.followCenter = [...state.selectedPos]
    }
  }

  // Drop the drawn trajectory without touching reactive state (used when the
  // whole simulator is torn down and `state` is reset separately).
  const reset = () => {
    selectedTrackSegments = null
  }

  return {
    updateTrackProgress,
    clearSelection,
    selectFeature,
    syncSelectedPosition,
    toggleSelectedTrack,
    toggleAutoFollow,
    reset
  }
}
