import { ref } from 'vue'
import { createLayerState } from './layerState'

export const useLayers = (apiBaseUrl) => {
  const layerState = ref(createLayerState(apiBaseUrl))

  const toggleLayer = (key) => {
    const entry = layerState.value[key]
    if (!entry) return
    entry.active = !entry.active
  }

  return {
    layerState,
    toggleLayer
  }
}
