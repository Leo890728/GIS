import { computed, onMounted, ref, watch } from 'vue'
import { createDataLayerState } from './dataLayerState'
import { emptyFeatureCollection, fetchDataAggregate, fetchDataPoints } from './dataApi'
import {
  buildAggregatePayload,
  buildPointQueryPayload,
  getDynamicPollInterval,
  hasRangeRequestCodes,
  isDynamicLayer
} from './dataLayerQueries'
import { useDataLayerPolling } from './useDataLayerPolling'
import { useSimulatorLayerBridge } from './useSimulatorLayerBridge'
import { applyDataStyleHandler } from './styleHandlers'

const createDefaultAggregateState = () => ({
  loading: false,
  error: '',
  layerKey: '',
  layerLabel: '',
  config: {},
  summary: { count: 0 }
})

const pickAggregateLayerEntry = (layerState) => {
  const entries = Object.entries(layerState || {})
  if (!entries.length) return null

  const activeEntries = entries.filter(([, layer]) => layer.active)
  if (!activeEntries.length) {
    return entries[0]
  }

  activeEntries.sort((a, b) => {
    const aPriority = Number(a?.[1]?.aggregate?.priority || 0)
    const bPriority = Number(b?.[1]?.aggregate?.priority || 0)
    return bPriority - aPriority
  })
  return activeEntries[0]
}

const createLayerRuntimeState = (layer) => ({
  isFetching: false,
  lastError: '',
  lastSuccessAt: null,
  nextRefreshAt: null,
  isDynamic: isDynamicLayer(layer),
  pollIntervalMs: getDynamicPollInterval(layer)
})

const buildInitialRuntimeMap = (layerState) =>
  Object.fromEntries(Object.entries(layerState || {}).map(([key, layer]) => [key, createLayerRuntimeState(layer)]))

export const useDataLayers = (apiBaseUrl, selectedRangeGeoJsonRef, selectedRangeRequestRef = null) => {
  const dataLayerState = ref(createDataLayerState(apiBaseUrl))
  const rangePointFilterEnabled = ref(false)
  const dataLayerGeoJson = ref(
    Object.fromEntries(Object.keys(dataLayerState.value).map((key) => [key, emptyFeatureCollection()]))
  )
  const dataLayerRuntime = ref(buildInitialRuntimeMap(dataLayerState.value))
  const dataAggregate = ref(createDefaultAggregateState())

  // Always replace the dict instead of mutating a key: the simulator feeds a
  // new FeatureCollection every rendered frame, and a deep watch over every
  // layer's features (the alternative for catching key mutations) costs a full
  // reactive traversal of all loaded data per frame. Identity replacement lets
  // consumers watch shallowly and lets the map skip layers whose value is
  // unchanged.
  const setLayerGeoJson = (key, geojson) => {
    const next = { ...dataLayerGeoJson.value, [key]: geojson || emptyFeatureCollection() }
    // Dev guard for the replace-don't-mutate invariant: a direct
    // `dataLayerGeoJson.value[k] = x` would bypass the shallow watch and the
    // map would silently never update — freeze the dict so it throws instead.
    dataLayerGeoJson.value = import.meta.env.DEV ? Object.freeze(next) : next
  }

  const activeDataLayerCount = computed(() =>
    Object.values(dataLayerState.value).filter((layer) => layer.active).length
  )

  let aggregateRequestSequence = 0
  const layerRequestSequence = new Map()

  // Simulator bridge owns `simulatorLayerKey`; fetching and polling read it to
  // skip the layer the Simulator is driving. refreshDataLayerByKey is deferred
  // (defined below) so the bridge can call it without a definition cycle.
  const {
    simulatorLayerKey,
    getSimulatorCandidates,
    enterSimulator,
    exitSimulator,
    setSimulatorGeoJson
  } = useSimulatorLayerBridge({
    dataLayerState,
    setLayerGeoJson,
    refreshDataLayerByKey: (key) => refreshDataLayerByKey(key)
  })

  const pointQueryPayloadFor = (layer) =>
    buildPointQueryPayload(layer, {
      rangePointFilterEnabled: rangePointFilterEnabled.value,
      selectedRangeGeoJson: selectedRangeGeoJsonRef?.value,
      selectedRangeRequest: selectedRangeRequestRef?.value
    })

  const syncLayerRuntimeState = () => {
    const layerKeys = new Set(Object.keys(dataLayerState.value))

    for (const key of Object.keys(dataLayerRuntime.value)) {
      if (!layerKeys.has(key)) {
        delete dataLayerRuntime.value[key]
      }
    }

    for (const [key, layer] of Object.entries(dataLayerState.value)) {
      const runtime = dataLayerRuntime.value[key] || createLayerRuntimeState(layer)
      runtime.isDynamic = isDynamicLayer(layer)
      runtime.pollIntervalMs = getDynamicPollInterval(layer)
      if (!runtime.isDynamic) {
        runtime.nextRefreshAt = null
      } else if (runtime.nextRefreshAt == null && runtime.lastSuccessAt) {
        runtime.nextRefreshAt = runtime.lastSuccessAt + runtime.pollIntervalMs
      }
      dataLayerRuntime.value[key] = runtime
    }
  }

  const markLayerFetched = (key) => {
    const runtime = dataLayerRuntime.value[key]
    if (!runtime) return
    const now = Date.now()
    runtime.lastSuccessAt = now
    runtime.lastError = ''
    runtime.nextRefreshAt = runtime.isDynamic ? now + runtime.pollIntervalMs : null
  }

  const fetchLayerGeoJson = async (key, layer) => {
    const runtime = dataLayerRuntime.value[key]
    if (!runtime) return false

    // While a layer is driven by the Simulator, its GeoJSON is supplied from
    // history playback; skip live fetches so they do not overwrite it.
    if (simulatorLayerKey.value === key) {
      runtime.isFetching = false
      return false
    }

    if (layer?.query?.disabled === true) {
      setLayerGeoJson(key, emptyFeatureCollection())
      markLayerFetched(key)
      runtime.isFetching = false
      runtime.lastError = ''
      return true
    }

    const selectedRangeRequest = selectedRangeRequestRef?.value
    if (
      rangePointFilterEnabled.value === true &&
      layer?.query?.useRangeRequest === true &&
      !hasRangeRequestCodes(selectedRangeRequest)
    ) {
      setLayerGeoJson(key, emptyFeatureCollection())
      markLayerFetched(key)
      runtime.isFetching = false
      runtime.lastError = ''
      return true
    }

    const nextSequence = (layerRequestSequence.get(key) || 0) + 1
    layerRequestSequence.set(key, nextSequence)
    runtime.isFetching = true
    runtime.lastError = ''

    try {
      const queryEndpoint = layer?.query?.endpoint || '/data/query'
      const geojson = await fetchDataPoints(apiBaseUrl, pointQueryPayloadFor(layer), queryEndpoint)
      const styledGeojson = applyDataStyleHandler(geojson, layer)
      if (layerRequestSequence.get(key) !== nextSequence) return false
      setLayerGeoJson(key, styledGeojson)
      markLayerFetched(key)
      return true
    } catch (error) {
      if (layerRequestSequence.get(key) !== nextSequence) return false
      runtime.lastError = error?.message || '資料點查詢失敗'
      setLayerGeoJson(key, emptyFeatureCollection())
      return false
    } finally {
      if (layerRequestSequence.get(key) === nextSequence) {
        runtime.isFetching = false
      }
    }
  }

  const refreshDataAggregate = async () => {
    const requestId = ++aggregateRequestSequence
    const selectedRange = selectedRangeGeoJsonRef?.value
    const selectedRangeRequest = selectedRangeRequestRef?.value
    const aggregateEntry = pickAggregateLayerEntry(dataLayerState.value)

    if (!aggregateEntry) {
      dataAggregate.value = createDefaultAggregateState()
      return
    }

    const [layerKey, layer] = aggregateEntry
    const selectedRangeRequestHasCodes = hasRangeRequestCodes(selectedRangeRequest)
    if (
      rangePointFilterEnabled.value === true &&
      layer?.aggregate?.useRangeRequest === true &&
      !selectedRangeRequestHasCodes
    ) {
      dataAggregate.value = {
        loading: false,
        error: '',
        layerKey,
        layerLabel: layer.label || layerKey,
        config: layer.aggregate?.summary || {},
        summary: { count: 0 }
      }
      return
    }

    const payload = buildAggregatePayload(
      layer,
      selectedRange,
      selectedRangeRequest,
      rangePointFilterEnabled.value
    )
    const aggregateEndpoint = layer.aggregate?.endpoint || '/data/aggregate'

    dataAggregate.value = {
      ...dataAggregate.value,
      loading: true,
      error: '',
      layerKey,
      layerLabel: layer.label || layerKey,
      config: layer.aggregate?.summary || {}
    }

    try {
      const summary = await fetchDataAggregate(apiBaseUrl, payload, aggregateEndpoint)
      if (requestId === aggregateRequestSequence) {
        dataAggregate.value = {
          loading: false,
          error: '',
          layerKey,
          layerLabel: layer.label || layerKey,
          config: layer.aggregate?.summary || {},
          summary
        }
      }
    } catch (error) {
      console.error(error)
      if (requestId === aggregateRequestSequence) {
        dataAggregate.value = {
          loading: false,
          error: '統計資料暫時無法取得',
          layerKey,
          layerLabel: layer.label || layerKey,
          config: layer.aggregate?.summary || {},
          summary: { count: 0 }
        }
      }
    }
  }

  const refreshDataLayers = async ({ refreshAggregate = true, onlyDynamic = false, layerKeys = null } = {}) => {
    syncLayerRuntimeState()
    let entries = Object.entries(dataLayerState.value)

    if (Array.isArray(layerKeys) && layerKeys.length) {
      const keySet = new Set(layerKeys)
      entries = entries.filter(([key]) => keySet.has(key))
    } else {
      entries = entries.filter(([, layer]) => layer.active)
    }
    if (onlyDynamic) {
      entries = entries.filter(([, layer]) => isDynamicLayer(layer))
    }

    await Promise.all(entries.map(([key, layer]) => fetchLayerGeoJson(key, layer)))

    if (refreshAggregate) {
      await refreshDataAggregate()
    }
  }

  const refreshDataLayerByKey = async (key) => {
    if (!dataLayerState.value[key]) return
    await refreshDataLayers({ refreshAggregate: true, layerKeys: [key] })
  }

  const { setupDynamicPolling } = useDataLayerPolling({
    dataLayerState,
    dataLayerRuntime,
    simulatorLayerKey,
    syncLayerRuntimeState,
    refreshDataLayers
  })

  const toggleDataLayer = (key) => {
    const layer = dataLayerState.value[key]
    if (!layer) return
    layer.active = !layer.active
    if (layer.active) {
      refreshDataLayers({ refreshAggregate: true, layerKeys: [key] }).catch((error) => {
        console.error(error)
      })
    } else {
      setLayerGeoJson(key, emptyFeatureCollection())
      refreshDataAggregate().catch((error) => {
        console.error(error)
      })
    }
  }

  const setDataLayerMode = ({ key, mode }) => {
    const layer = dataLayerState.value[key]
    if (!layer || !['points', 'heatmap'].includes(mode)) return
    const supportedModes = Array.isArray(layer.supportedModes) ? layer.supportedModes : ['points', 'heatmap']
    if (!supportedModes.includes(mode)) return
    layer.style.mode = mode
  }

  const setRangePointFilterEnabled = (enabled) => {
    rangePointFilterEnabled.value = enabled === true
    refreshDataLayers({ refreshAggregate: true }).catch((error) => {
      console.error(error)
    })
  }

  onMounted(() => {
    refreshDataLayers()
    setupDynamicPolling()
  })

  watch(
    () => selectedRangeGeoJsonRef?.value,
    () => {
      if (rangePointFilterEnabled.value) {
        refreshDataLayers({ refreshAggregate: false }).catch((error) => {
          console.error(error)
        })
      }
      refreshDataAggregate()
    },
    { deep: true }
  )

  watch(
    () => selectedRangeRequestRef?.value,
    () => {
      refreshDataAggregate()
    },
    { deep: true }
  )

  watch(
    () => dataLayerState.value,
    () => {
      syncLayerRuntimeState()
      setupDynamicPolling()
    },
    { deep: true }
  )

  return {
    dataLayerState,
    rangePointFilterEnabled,
    dataLayerGeoJson,
    dataLayerRuntime,
    dataAggregate,
    activeDataLayerCount,
    refreshDataLayers,
    refreshDataLayerByKey,
    refreshDataAggregate,
    toggleDataLayer,
    setDataLayerMode,
    setRangePointFilterEnabled,
    getSimulatorCandidates,
    enterSimulator,
    exitSimulator,
    setSimulatorGeoJson
  }
}
