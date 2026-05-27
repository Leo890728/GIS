import { ref } from 'vue'
import { createLayerState } from './layerState'

export const useLayers = (apiBaseUrl) => {
  const layerState = ref(createLayerState(apiBaseUrl))

  const toggleLayer = (key) => {
    const entry = layerState.value[key]
    if (!entry) return
    entry.active = !entry.active
  }

  const updateLayerStyle = ({ key, color, lineWidthScale }) => {
    const entry = layerState.value[key]
    if (!entry) return

    if (typeof color === 'string' && color.trim()) {
      entry.color = color.trim()
    }

    if (lineWidthScale !== undefined) {
      const nextScale = Number(lineWidthScale)
      if (Number.isFinite(nextScale)) {
        entry.lineWidthScale = Math.min(3, Math.max(0.4, nextScale))
      }
    }
  }

  return {
    layerState,
    toggleLayer,
    updateLayerStyle
  }
}
