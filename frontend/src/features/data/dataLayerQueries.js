// Pure query/payload builders and layer-shape predicates for the data layers.
// No Vue reactivity lives here: callers pass plain values (unwrapped refs), so
// every function is deterministic and unit-testable in isolation.

import { emptyFeatureCollection } from './dataApi'

export const hasRangeFeatures = (geojson) =>
  geojson?.type === 'FeatureCollection' && Array.isArray(geojson.features) && geojson.features.length > 0

export const hasRangeRequestCodes = (request) => {
  if (!request || typeof request !== 'object') return false
  return ['countyCodes', 'townCodes', 'villageCodes', 'statZone2Codes', 'statZone1Codes', 'statZoneCodes'].some((key) => {
    const value = request[key]
    return Array.isArray(value) && value.length > 0
  })
}

export const isDynamicLayer = (layer) => layer?.dynamic?.enabled === true

// A dynamic layer whose history the backend records; only these can be replayed
// in the simulator. Live-only layers (no backend `history`) are excluded so the
// simulator doesn't offer a dataset that has no recorded frames to play back.
export const isReplayableLayer = (layer) =>
  isDynamicLayer(layer) && layer?.dynamic?.recorded === true

export const getDynamicPollInterval = (layer) => {
  const interval = Number(layer?.dynamic?.pollIntervalMs)
  if (!Number.isFinite(interval) || interval <= 0) return 60000
  return Math.max(5000, interval)
}

// Build the /data/query payload for a point layer. Range filtering is applied
// only when enabled: a range request (codes) takes precedence, otherwise the
// selected range GeoJSON is sent (or an empty collection when none is drawn).
export const buildPointQueryPayload = (
  layer,
  { rangePointFilterEnabled, selectedRangeGeoJson, selectedRangeRequest } = {}
) => {
  const query = layer.query || {}
  const payload = { ...query }
  delete payload.endpoint
  delete payload.useRangeRequest
  if (
    rangePointFilterEnabled === true &&
    query.useRangeRequest &&
    selectedRangeRequest &&
    typeof selectedRangeRequest === 'object'
  ) {
    Object.assign(payload, selectedRangeRequest)
  }
  if (!rangePointFilterEnabled) {
    return payload
  }
  if (hasRangeFeatures(selectedRangeGeoJson)) {
    payload.range = selectedRangeGeoJson
  } else {
    payload.range = emptyFeatureCollection()
  }
  return payload
}

// Build the /data/aggregate payload for an aggregate layer, applying the same
// range-filtering precedence as point queries.
export const buildAggregatePayload = (
  layer,
  selectedRangeGeoJson,
  selectedRangeRequest,
  rangePointFilterEnabled
) => {
  const query = layer.query || {}
  const aggregate = layer.aggregate || {}
  const payload = {
    dataId: query.dataId || layer.dataId,
    metrics: aggregate.metrics || ['count'],
    ...(aggregate.groupBy ? { groupBy: aggregate.groupBy } : {}),
    ...(query.filters ? { filters: query.filters } : {}),
    ...(query.bbox ? { bbox: query.bbox } : {}),
    ...(query.sinceTimestamp ? { sinceTimestamp: query.sinceTimestamp } : {})
  }

  if (
    rangePointFilterEnabled === true &&
    aggregate.useRangeRequest &&
    selectedRangeRequest &&
    typeof selectedRangeRequest === 'object'
  ) {
    Object.assign(payload, selectedRangeRequest)
  } else if (rangePointFilterEnabled === true) {
    payload.range = hasRangeFeatures(selectedRangeGeoJson) ? selectedRangeGeoJson : emptyFeatureCollection()
  } else if (query.range) {
    payload.range = query.range
  }

  if (aggregate.query && typeof aggregate.query === 'object') {
    Object.assign(payload, aggregate.query)
  }

  return payload
}

// Active dynamic layers whose poll interval is due at `now` (excluding the layer
// currently driven by the Simulator). Returns the list of layer keys to refresh.
export const getDueDynamicLayerKeys = (
  layerState,
  runtimeMap,
  { simulatorLayerKey = null, now = Date.now() } = {}
) =>
  Object.entries(layerState || {})
    .filter(([key, layer]) => layer.active && isDynamicLayer(layer) && runtimeMap[key])
    .filter(([key]) => key !== simulatorLayerKey)
    .filter(([key]) => {
      const runtime = runtimeMap[key]
      return runtime.nextRefreshAt == null || runtime.nextRefreshAt <= now
    })
    .map(([key]) => key)
