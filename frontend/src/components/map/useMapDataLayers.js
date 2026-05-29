import { ensureIcons } from '../../features/data/icons'

const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })

const getDataLayerSourceData = (dataLayerGeoJson, key) => dataLayerGeoJson?.[key] || emptyFeatureCollection()
const isVectorEntry = (entry) => entry?.sourceType === 'vector'

export const getDataLayerIds = (dataLayerState) =>
  Object.values(dataLayerState || {}).flatMap((entry) => {
    const supportedModes = Array.isArray(entry.supportedModes) && entry.supportedModes.length
      ? entry.supportedModes
      : ['points', 'heatmap']
    if (isVectorEntry(entry)) {
      const ids = []
      if (supportedModes.includes('heatmap')) {
        ids.push(`${entry.layerId}-heatmap-fill`, `${entry.layerId}-heatmap-line`)
      }
      return ids
    }
    const ids = []
    if (supportedModes.includes('heatmap')) ids.push(`${entry.layerId}-heatmap`)
    if (supportedModes.includes('points')) ids.push(`${entry.layerId}-points`)
    return ids
  })

export const getDataPointLayerIds = (dataLayerState) =>
  Object.values(dataLayerState || {}).flatMap((entry) => {
    if (isVectorEntry(entry)) return []
    const supportedModes = Array.isArray(entry.supportedModes) && entry.supportedModes.length
      ? entry.supportedModes
      : ['points', 'heatmap']
    return supportedModes.includes('points') ? [`${entry.layerId}-points`] : []
  })

export const getDataLayerEntryByPointLayerId = (dataLayerState, pointLayerId) =>
  Object.values(dataLayerState || {}).find((entry) => !isVectorEntry(entry) && `${entry.layerId}-points` === pointLayerId)

const ensureLayerIcon = async (map, entry) => {
  if (entry?.style?.forceCircle === true) return null

  const hasIconDefs = Array.isArray(entry?.icons) && entry.icons.length > 0
  const explicitIconId = typeof entry?.style?.iconId === 'string' && entry.style.iconId.trim() !== ''
  if (!hasIconDefs && !explicitIconId) return null

  await ensureIcons(map, entry.icons)
  const iconId = entry.style?.iconId || `${entry.layerId}-icon`
  return map.hasImage(iconId) ? iconId : null
}

const getVectorHeatmapColor = (entry) => [
  'interpolate',
  ['linear'],
  ['coalesce', ['to-number', ['get', entry.style?.weightProperty || 'P_CNT']], 0],
  0, '#f1f6ec',
  200, '#d7ebc7',
  500, '#afdaa3',
  1000, '#80c97f',
  2000, '#4ea65d',
  5000, '#2f7e49'
]

const getPointSizeExpr = (entry) => ['coalesce', ['get', '__style_pointSize'], entry.style?.pointSize || 6]

const getIconSizeExpr = (entry) => {
  if (entry?.style?.iconSize != null) {
    return entry.style.iconSize
  }
  const pointSizeExpr = getPointSizeExpr(entry)
  if (entry?.style?.scalePointWithZoom === false) {
    return ['/', pointSizeExpr, 10]
  }
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    6,
    0.35,
    12,
    ['/', pointSizeExpr, 10],
    16,
    ['/', ['+', pointSizeExpr, 2], 10]
  ]
}

const getCircleRadiusExpr = (entry) => {
  const pointSizeExpr = getPointSizeExpr(entry)
  if (entry?.style?.scalePointWithZoom === false) {
    return pointSizeExpr
  }
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    6,
    ['max', 2, ['*', pointSizeExpr, 0.7]],
    12,
    pointSizeExpr,
    16,
    ['+', pointSizeExpr, 4]
  ]
}

export const useMapDataLayers = (mapRef, dataLayerStateRef, dataLayerGeoJsonRef) => {
  const getLayerVisibility = (entry, mode) => (entry.active && entry.style?.mode === mode ? 'visible' : 'none')

  const addDataLayer = async (key) => {
    const map = mapRef.value
    if (!map) return

    const entry = dataLayerStateRef.value[key]
    if (!entry) return
    const supportedModes = Array.isArray(entry.supportedModes) && entry.supportedModes.length
      ? entry.supportedModes
      : ['points', 'heatmap']

    if (isVectorEntry(entry)) {
      if (!map.getSource(entry.sourceId)) {
        map.addSource(entry.sourceId, {
          type: 'vector',
          tiles: [entry.url],
          minzoom: 0,
          maxzoom: entry.maxNativeZoom || 14
        })
      }
      if (supportedModes.includes('heatmap') && !map.getLayer(`${entry.layerId}-heatmap-fill`)) {
        map.addLayer({
          id: `${entry.layerId}-heatmap-fill`,
          type: 'fill',
          source: entry.sourceId,
          'source-layer': entry.sourceLayer,
          minzoom: entry.minVisibleZoom || 0,
          layout: {
            visibility: getLayerVisibility(entry, 'heatmap')
          },
          paint: {
            'fill-color': getVectorHeatmapColor(entry),
            'fill-opacity': 0.56
          }
        })
      }
      if (supportedModes.includes('heatmap') && !map.getLayer(`${entry.layerId}-heatmap-line`)) {
        map.addLayer({
          id: `${entry.layerId}-heatmap-line`,
          type: 'line',
          source: entry.sourceId,
          'source-layer': entry.sourceLayer,
          minzoom: entry.minVisibleZoom || 0,
          layout: {
            visibility: getLayerVisibility(entry, 'heatmap')
          },
          paint: {
            'line-color': '#14311f',
            'line-width': ['interpolate', ['linear'], ['zoom'], 7, 0.2, 10, 0.35, 13, 0.55, 16, 0.8],
            'line-opacity': 0.55
          }
        })
      }
      return
    }

    if (!map.getSource(entry.sourceId)) {
      map.addSource(entry.sourceId, {
        type: 'geojson',
        data: getDataLayerSourceData(dataLayerGeoJsonRef.value, key)
      })
    }

    if (supportedModes.includes('heatmap') && !map.getLayer(`${entry.layerId}-heatmap`)) {
      map.addLayer({
        id: `${entry.layerId}-heatmap`,
        type: 'heatmap',
        source: entry.sourceId,
        layout: {
          visibility: getLayerVisibility(entry, 'heatmap')
        },
        paint: {
          'heatmap-weight': [
            'coalesce',
            ['to-number', ['get', '__style_heatWeight']],
            ['to-number', ['get', entry.style.weightProperty || 'weight']],
            1
          ],
          'heatmap-intensity': entry.style.heatmapIntensity || 1,
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 6, 8, 12, 18, 16, 28],
          'heatmap-opacity': 0.78,
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(23, 37, 60, 0)',
            0.25,
            '#5ec8f2',
            0.5,
            '#f2c94c',
            0.8,
            '#f2994a',
            1,
            '#eb5757'
          ]
        }
      })
    }

    const iconId = await ensureLayerIcon(map, entry)
    if (supportedModes.includes('points') && !map.getLayer(`${entry.layerId}-points`)) {
      if (iconId) {
        map.addLayer({
          id: `${entry.layerId}-points`,
          type: 'symbol',
          source: entry.sourceId,
          layout: {
            visibility: getLayerVisibility(entry, 'points'),
            'icon-image': ['case', ['has', '__style_iconId'], ['image', ['get', '__style_iconId']], ['image', iconId]],
            'icon-size': getIconSizeExpr(entry),
            'icon-allow-overlap': true
          },
          paint: {
            'icon-opacity': 0.92
          }
        })
      } else {
        map.addLayer({
          id: `${entry.layerId}-points`,
          type: 'circle',
          source: entry.sourceId,
          layout: {
            visibility: getLayerVisibility(entry, 'points')
          },
          paint: {
            'circle-color': ['coalesce', ['get', '__style_pointColor'], entry.style.color || '#f2c94c'],
            'circle-radius': getCircleRadiusExpr(entry),
            'circle-opacity': 0.82,
            'circle-stroke-color': '#0b1220',
            'circle-stroke-width': 1.2
          }
        })
      }
    }
  }

  const addDataLayers = () =>
    Promise.all(
      Object.keys(dataLayerStateRef.value).map((key) =>
        addDataLayer(key).catch((error) => {
          console.error(`[data-layer] failed to add ${key}`, error)
        })
      )
    )

  const updateDataLayerVisibility = (key) => {
    const map = mapRef.value
    if (!map) return

    const entry = dataLayerStateRef.value[key]
    if (!entry) return

    if (isVectorEntry(entry)) {
      const fillLayerId = `${entry.layerId}-heatmap-fill`
      const lineLayerId = `${entry.layerId}-heatmap-line`
      if (map.getLayer(fillLayerId)) {
        map.setLayoutProperty(fillLayerId, 'visibility', getLayerVisibility(entry, 'heatmap'))
      }
      if (map.getLayer(lineLayerId)) {
        map.setLayoutProperty(lineLayerId, 'visibility', getLayerVisibility(entry, 'heatmap'))
      }
      return
    }

    const heatmapLayerId = `${entry.layerId}-heatmap`
    const pointsLayerId = `${entry.layerId}-points`
    if (map.getLayer(heatmapLayerId)) {
      map.setLayoutProperty(heatmapLayerId, 'visibility', getLayerVisibility(entry, 'heatmap'))
    }
    if (map.getLayer(pointsLayerId)) {
      map.setLayoutProperty(pointsLayerId, 'visibility', getLayerVisibility(entry, 'points'))
    }
  }

  const updateDataLayerStyle = async (key) => {
    const map = mapRef.value
    if (!map) return

    const entry = dataLayerStateRef.value[key]
    if (!entry || isVectorEntry(entry)) return

    const pointsLayerId = `${entry.layerId}-points`
    const layer = map.getLayer(pointsLayerId)
    if (!layer) return

    if (layer.type === 'symbol') {
      const iconId = await ensureLayerIcon(map, entry)
      if (iconId) {
        map.setLayoutProperty(pointsLayerId, 'icon-image', ['case', ['has', '__style_iconId'], ['image', ['get', '__style_iconId']], ['image', iconId]])
      }
      map.setLayoutProperty(pointsLayerId, 'icon-size', getIconSizeExpr(entry))
      return
    }

    if (layer.type === 'circle') {
      map.setPaintProperty(pointsLayerId, 'circle-color', ['coalesce', ['get', '__style_pointColor'], entry.style.color || '#f2c94c'])
      map.setPaintProperty(pointsLayerId, 'circle-radius', getCircleRadiusExpr(entry))
    }
  }

  const updateAllDataLayerVisibility = () => {
    Object.keys(dataLayerStateRef.value).forEach((key) => {
      updateDataLayerVisibility(key)
      updateDataLayerStyle(key).catch((error) => {
        console.error(`[data-layer] failed to update style ${key}`, error)
      })
    })
  }

  const updateDataLayerGeoJson = () => {
    const map = mapRef.value
    if (!map) return

    for (const [key, entry] of Object.entries(dataLayerStateRef.value)) {
      if (isVectorEntry(entry)) continue
      const source = map.getSource(entry.sourceId)
      if (source && typeof source.setData === 'function') {
        source.setData(getDataLayerSourceData(dataLayerGeoJsonRef.value, key))
      }
    }
  }

  return {
    addDataLayers,
    updateAllDataLayerVisibility,
    updateDataLayerGeoJson
  }
}
