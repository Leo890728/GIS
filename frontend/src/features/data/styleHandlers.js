const isFiniteNumber = (value) => Number.isFinite(value)

// The single place that encodes a handler's per-feature `style` into the
// `__style_*` properties MapLibre reads. All style outputs (incl. iconId) go
// through `result.style`; `derivedFields` is reserved for display data only.
const mergeFeatureProperties = (feature, style, derivedFields) => {
  const baseProperties = feature.properties && typeof feature.properties === 'object' ? feature.properties : {}
  const nextProperties = {
    ...baseProperties,
    ...(derivedFields || {})
  }

  const s = style || {}
  if (typeof s.color === 'string' && s.color) nextProperties.__style_color = s.color
  if (typeof s.iconId === 'string' && s.iconId) nextProperties.__style_iconId = s.iconId
  if (isFiniteNumber(s.pointSize)) nextProperties.__style_pointSize = s.pointSize
  if (isFiniteNumber(s.heatWeight)) nextProperties.__style_heatWeight = s.heatWeight

  return {
    ...feature,
    properties: nextProperties
  }
}

const applyHandlerToFeature = (feature, layerEntry) => {
  if (!feature || feature.type !== 'Feature') return feature
  const handlerConfig = layerEntry?.styleHandler
  if (!handlerConfig) return feature

  const handler = typeof handlerConfig.handler === 'function' ? handlerConfig.handler : null
  if (!handler) return feature

  const ctx = {
    feature,
    geometry: feature.geometry || null,
    properties: feature.properties || {},
    sourceConfig: layerEntry
  }

  const result = handler(ctx, handlerConfig.params || {})
  if (!result || typeof result !== 'object') return feature
  return mergeFeatureProperties(feature, result.style, result.derivedFields)
}

export const applyDataStyleHandler = (geojson, layerEntry) => {
  if (!geojson || geojson.type !== 'FeatureCollection' || !Array.isArray(geojson.features)) {
    return geojson
  }
  return {
    ...geojson,
    features: geojson.features.map((feature) => applyHandlerToFeature(feature, layerEntry))
  }
}
