const isFiniteNumber = (value) => Number.isFinite(value)

const mergeFeatureProperties = (feature, style, derivedFields) => {
  const baseProperties = feature.properties && typeof feature.properties === 'object' ? feature.properties : {}
  const nextProperties = {
    ...baseProperties,
    ...(derivedFields || {})
  }

  if (style?.pointColor) nextProperties.__style_pointColor = style.pointColor
  if (isFiniteNumber(style?.pointSize)) nextProperties.__style_pointSize = style.pointSize
  if (isFiniteNumber(style?.heatWeight)) nextProperties.__style_heatWeight = style.heatWeight

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
