const getLineWidthExpression = (key) => {
  if (key === 'county') {
    return ['interpolate', ['linear'], ['zoom'], 5, 2.2, 9, 2.0, 12, 1.8, 16, 1.6, 20, 1.4]
  }
  if (key === 'township') {
    return ['interpolate', ['linear'], ['zoom'], 8, 1.6, 12, 1.4, 16, 1.1, 20, 0.9]
  }
  return ['interpolate', ['linear'], ['zoom'], 12, 1.2, 14, 1.0, 16, 0.8, 20, 0.6]
}

export const getBoundaryLayerIds = (layerState) =>
  [
    layerState.village?.layerId,
    layerState.township?.layerId,
    layerState.county?.layerId
  ].filter(Boolean)

export const useMapLayers = (mapRef, layerStateRef) => {
  const updateLayerVisibility = (key) => {
    const map = mapRef.value
    if (!map) return

    const entry = layerStateRef.value[key]
    if (!entry || !map.getLayer(entry.layerId)) return
    map.setLayoutProperty(entry.layerId, 'visibility', entry.active ? 'visible' : 'none')
  }

  const addBoundaryLayer = (key) => {
    const map = mapRef.value
    if (!map) return

    const entry = layerStateRef.value[key]
    if (!entry) return
    if (map.getSource(entry.sourceId) || map.getLayer(entry.layerId)) return

    map.addSource(entry.sourceId, {
      type: 'vector',
      tiles: [entry.url],
      minzoom: 0,
      maxzoom: entry.maxNativeZoom
    })

    map.addLayer({
      id: entry.layerId,
      type: 'line',
      source: entry.sourceId,
      'source-layer': entry.sourceLayer,
      minzoom: entry.minVisibleZoom,
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
        visibility: entry.active ? 'visible' : 'none'
      },
      paint: {
        'line-color': entry.color,
        'line-width': getLineWidthExpression(key),
        'line-opacity': 0.9
      }
    })
  }

  const addBoundaryLayers = () => {
    Object.keys(layerStateRef.value).forEach(addBoundaryLayer)
  }

  const updateAllLayerVisibility = () => {
    Object.keys(layerStateRef.value).forEach(updateLayerVisibility)
  }

  return {
    addBoundaryLayers,
    updateAllLayerVisibility
  }
}
