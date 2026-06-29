import { onBeforeUnmount } from 'vue'
import { getDueDynamicLayerKeys, isDynamicLayer } from './dataLayerQueries'

// Polls active dynamic layers on a 1s tick, refreshing only the ones whose poll
// interval is due (and never the layer currently driven by the Simulator). Owns
// the interval timer + in-flight guard; the data layers composable wires in
// shared state and the refresh/sync functions. Cleans up on unmount.
export const useDataLayerPolling = ({
  dataLayerState,
  dataLayerRuntime,
  simulatorLayerKey,
  syncLayerRuntimeState,
  refreshDataLayers
}) => {
  let dynamicPollingTimer = null
  let dynamicPollingBusy = false

  const clearDynamicPolling = () => {
    if (!dynamicPollingTimer) return
    clearInterval(dynamicPollingTimer)
    dynamicPollingTimer = null
  }

  const setupDynamicPolling = () => {
    clearDynamicPolling()
    syncLayerRuntimeState()

    const hasActiveDynamic = Object.values(dataLayerState.value).some((layer) => layer.active && isDynamicLayer(layer))
    if (!hasActiveDynamic) return

    dynamicPollingTimer = setInterval(() => {
      if (dynamicPollingBusy) return
      const dueKeys = getDueDynamicLayerKeys(dataLayerState.value, dataLayerRuntime.value, {
        simulatorLayerKey: simulatorLayerKey.value
      })
      if (!dueKeys.length) return

      dynamicPollingBusy = true
      refreshDataLayers({ refreshAggregate: true, layerKeys: dueKeys })
        .catch((error) => {
          console.error(error)
        })
        .finally(() => {
          dynamicPollingBusy = false
        })
    }, 1000)
  }

  onBeforeUnmount(clearDynamicPolling)

  return { clearDynamicPolling, setupDynamicPolling }
}
