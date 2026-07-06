import { computed, ref } from 'vue'
import { bearingToTruckIconSuffix, pathBearingAt } from './routePlanTracks'
import {
  activePropertiesAt,
  interpolateSegmentsAt,
  pathIndexAt,
  remainingCoords,
  traveledCoords
} from './trackInterpolation'

const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })

// Route-plan rendering strategy: plays back synthetic tracks built from a
// solved VRP result instead of recorded history. Renders into its own GeoJSON
// refs (dedicated map layers), so no live data layer is taken over. Same
// renderTick contract as the frame/smooth strategies; owns the route-plan
// tracks, the per-frame refs, and the vehicle selection that drives the
// vehicle drawer. Reads/writes the shared playback `state` (selection group +
// featureCount).
export const useRoutePlanRenderer = ({ state }) => {
  let tracks = []
  let lastRenderReal = 0

  const pointsGeoJson = ref(emptyFeatureCollection())
  // Per-frame route split: the already-traveled portion (drawn translucent) and
  // the remaining portion (solid), both colored per vehicle.
  const traveledGeoJson = ref(emptyFeatureCollection())
  const remainingGeoJson = ref(emptyFeatureCollection())
  // Pickup stops weighted by collected garbage, for the toggleable heatmap view.
  const heatGeoJson = ref(emptyFeatureCollection())
  // Per-vehicle playback progress `{ [vehicleId]: { visitedStops } }` consumed
  // by the map to fade already-served stops.
  const progress = ref({})

  const hasTracks = () => tracks.length > 0

  // Adopt freshly built tracks (see buildRoutePlanTracks) + the heat overlay.
  const setTracks = (nextTracks, nextHeatGeoJson) => {
    tracks = nextTracks
    heatGeoJson.value = nextHeatGeoJson || emptyFeatureCollection()
  }

  const clear = () => {
    tracks = []
    pointsGeoJson.value = emptyFeatureCollection()
    traveledGeoJson.value = emptyFeatureCollection()
    remainingGeoJson.value = emptyFeatureCollection()
    heatGeoJson.value = emptyFeatureCollection()
    progress.value = {}
  }

  // The traveled/remaining split lines carry the full road geometry, so every
  // reassignment costs a MapLibre setData (reparse + GPU upload) of thousands
  // of vertices per vehicle. Their shape only changes when some vehicle crosses
  // a geometry vertex, so rebuilds are gated on that signature; the interpolated
  // vehicle points still move every frame. `forceLines` (seeks, selection,
  // periodic refresh) bypasses the gate so the line tips re-attach to the trucks.
  let lastLineSignature = null

  const render = (ms, forceLines = true) => {
    const features = []
    let lineSignature = ''
    for (const track of tracks) {
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
    pointsGeoJson.value = { type: 'FeatureCollection', features }
    if (state.featureCount !== features.length) state.featureCount = features.length

    if (forceLines || lineSignature !== lastLineSignature) {
      lastLineSignature = lineSignature
      const traveledFeatures = []
      const remainingFeatures = []
      const nextProgress = {}
      for (const track of tracks) {
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
        nextProgress[track.properties.vehicleId] = {
          visitedStops: track.stopTimesMs.filter((tMs) => tMs <= ms).length
        }
      }
      traveledGeoJson.value = { type: 'FeatureCollection', features: traveledFeatures }
      remainingGeoJson.value = { type: 'FeatureCollection', features: remainingFeatures }
      progress.value = nextProgress
    }
    // Keep the selection ring pinned to the selected vehicle as it moves, and
    // recenter the camera when auto-follow is on.
    if (state.selected?.key != null) {
      const match = features.find((feature) => feature.properties.__trackKey === state.selected.key)
      state.selectedPos = match ? match.geometry.coordinates : null
      if (state.autoFollow && state.selectedPos) state.followCenter = state.selectedPos
    }
  }

  // Same ~60fps cap the smooth renderer uses during continuous play. During
  // play the heavy split lines only rebuild on vertex crossings (see render),
  // plus a ~5Hz forced refresh so the line tips never trail visibly on long
  // straight segments with sparse vertices.
  let lastLineForceReal = 0
  const renderTick = (ms, realNow = null) => {
    if (realNow != null) {
      if (realNow - lastRenderReal < 16) return
      lastRenderReal = realNow
      const forceLines = realNow - lastLineForceReal >= 200
      if (forceLines) lastLineForceReal = realNow
      render(ms, forceLines)
      return
    }
    render(ms)
  }

  // Selecting a simulated vehicle drives the right-hand vehicle drawer
  // (timeline + current load); no history-track fetch is involved.
  const selectVehicle = (payload) => {
    if (!payload || payload.key == null || payload.key === '') {
      state.selected = null
      state.selectedPos = null
      state.autoFollow = false
      state.followCenter = null
      return
    }
    state.selected = { key: String(payload.key), properties: payload.properties || {} }
    render(state.currentTime)
  }

  const selectedVehicle = computed(() => {
    if (state.mode !== 'route-plan' || !state.selected) return null
    const track = tracks.find((candidate) => candidate.key === state.selected.key)
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

  return {
    pointsGeoJson,
    traveledGeoJson,
    remainingGeoJson,
    heatGeoJson,
    progress,
    hasTracks,
    setTracks,
    clear,
    render,
    renderTick,
    selectVehicle,
    selectedVehicle
  }
}
