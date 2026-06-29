import { ref } from 'vue'
import { emptyFeatureCollection } from './dataApi'
import { isDynamicLayer } from './dataLayerQueries'

// The Simulator (history playback) takes over an existing dynamic data layer:
// it pauses live polling for that layer (via the shared `simulatorLayerKey`) and
// feeds reconstructed GeoJSON so the dataset's icons / heatmap / tooltips are
// reused as-is. Owns the simulator key + prior-active bookkeeping; the data
// layers composable wires in shared state and the per-key refresh.
export const useSimulatorLayerBridge = ({ dataLayerState, dataLayerGeoJson, refreshDataLayerByKey }) => {
  const simulatorLayerKey = ref(null)
  const simulatorPriorActive = new Map()

  const findLayerKeyByDataId = (dataId) =>
    Object.keys(dataLayerState.value).find(
      (key) => (dataLayerState.value[key].query?.dataId || dataLayerState.value[key].dataId) === dataId
    )

  const getSimulatorCandidates = () =>
    Object.entries(dataLayerState.value)
      .filter(([, layer]) => isDynamicLayer(layer))
      .map(([key, layer]) => ({ key, dataId: layer.query?.dataId || layer.dataId, label: layer.label || key }))

  const exitSimulator = () => {
    const key = simulatorLayerKey.value
    simulatorLayerKey.value = null
    if (!key || !dataLayerState.value[key]) return
    if (simulatorPriorActive.has(key)) {
      dataLayerState.value[key].active = simulatorPriorActive.get(key)
      simulatorPriorActive.delete(key)
    }
    if (dataLayerState.value[key].active) {
      refreshDataLayerByKey(key).catch((error) => console.error(error))
    } else {
      dataLayerGeoJson.value[key] = emptyFeatureCollection()
    }
  }

  const enterSimulator = (dataId) => {
    const key = findLayerKeyByDataId(dataId)
    if (!key) return null
    if (simulatorLayerKey.value && simulatorLayerKey.value !== key) {
      exitSimulator()
    }
    const layer = dataLayerState.value[key]
    if (!simulatorPriorActive.has(key)) {
      simulatorPriorActive.set(key, layer.active)
    }
    simulatorLayerKey.value = key
    layer.active = true
    dataLayerGeoJson.value[key] = emptyFeatureCollection()
    return layer
  }

  const setSimulatorGeoJson = (geojson) => {
    const key = simulatorLayerKey.value
    if (!key) return
    dataLayerGeoJson.value[key] = geojson || emptyFeatureCollection()
  }

  return {
    simulatorLayerKey,
    getSimulatorCandidates,
    enterSimulator,
    exitSimulator,
    setSimulatorGeoJson
  }
}
