import { computed, ref } from 'vue'
import { bearingToTruckIconSuffix, pathBearingAt } from './routePlanTracks'
import {
  activePropertiesAt,
  countAtOrBefore,
  interpolateSegmentsAt,
  pathCumulativeDistances,
  pathProgressAt
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
  // Cumulative distances per track key, so per-frame progress stays O(log n).
  let cumulativeByKey = new Map()

  const pointsGeoJson = ref(emptyFeatureCollection())
  // Static per-vehicle route lines, uploaded to the map ONCE per simulation.
  // The traveled/remaining visual split is a per-frame line-progress fraction
  // (lineProgress) applied as a line-gradient paint property — rebuilding the
  // split as two LineStrings per tick re-parsed and re-uploaded the entire
  // road geometry and caused visible stutter on long routes.
  const linesGeoJson = ref(emptyFeatureCollection())
  // Per-vehicle traveled fraction `{ [vehicleId]: 0..1 }`, written every frame.
  const lineProgress = ref({})
  // Pickup stops weighted by collected garbage, for the toggleable heatmap view.
  const heatGeoJson = ref(emptyFeatureCollection())
  // Per-vehicle playback progress `{ [vehicleId]: { visitedStops } }` consumed
  // by the map to fade already-served stops. Only reassigned when a count
  // actually changes: its watcher recompiles stop-fade paint expressions over
  // every stop feature, which is far too heavy to run per frame.
  const progress = ref({})

  const hasTracks = () => tracks.length > 0

  // Adopt freshly built tracks (see buildRoutePlanTracks) + the heat overlay.
  const setTracks = (nextTracks, nextHeatGeoJson) => {
    tracks = nextTracks
    heatGeoJson.value = nextHeatGeoJson || emptyFeatureCollection()
    cumulativeByKey = new Map()
    const lineFeatures = []
    for (const track of tracks) {
      const path = track.segments[0]?.path || []
      cumulativeByKey.set(track.key, pathCumulativeDistances(path))
      if (path.length >= 2) {
        lineFeatures.push({
          type: 'Feature',
          properties: { ...track.properties },
          geometry: { type: 'LineString', coordinates: path.map((point) => [point.lng, point.lat]) }
        })
      }
    }
    linesGeoJson.value = { type: 'FeatureCollection', features: lineFeatures }
    lineProgress.value = {}
  }

  const clear = () => {
    tracks = []
    cumulativeByKey = new Map()
    pointsGeoJson.value = emptyFeatureCollection()
    linesGeoJson.value = emptyFeatureCollection()
    lineProgress.value = {}
    heatGeoJson.value = emptyFeatureCollection()
    progress.value = {}
  }

  const render = (ms) => {
    const features = []
    const nextLineProgress = {}
    const nextProgress = {}
    let progressChanged = false
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
      const vehicleId = track.properties.vehicleId
      nextLineProgress[vehicleId] = pathProgressAt(path, cumulativeByKey.get(track.key), ms)
      const visitedStops = countAtOrBefore(track.stopTimesMs, ms)
      nextProgress[vehicleId] = { visitedStops }
      if (progress.value[vehicleId]?.visitedStops !== visitedStops) progressChanged = true
    }
    pointsGeoJson.value = { type: 'FeatureCollection', features }
    lineProgress.value = nextLineProgress
    if (progressChanged || Object.keys(progress.value).length !== Object.keys(nextProgress).length) {
      progress.value = nextProgress
    }
    if (state.featureCount !== features.length) state.featureCount = features.length
    // Keep the selection ring pinned to the selected vehicle as it moves, and
    // recenter the camera when auto-follow is on.
    if (state.selected?.key != null) {
      const match = features.find((feature) => feature.properties.__trackKey === state.selected.key)
      state.selectedPos = match ? match.geometry.coordinates : null
      if (state.autoFollow && state.selectedPos) state.followCenter = state.selectedPos
    }
  }

  // Same ~60fps cap the smooth renderer uses during continuous play.
  const renderTick = (ms, realNow = null) => {
    if (realNow != null) {
      if (realNow - lastRenderReal < 16) return
      lastRenderReal = realNow
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
    linesGeoJson,
    lineProgress,
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
