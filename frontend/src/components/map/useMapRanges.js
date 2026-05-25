const rangeGeoJsonSourceId = 'range-geojson-source'
const rangeFillLayerId = 'range-fill'
const rangeLineLayerId = 'range-line'

export const rangeLayerIds = [rangeFillLayerId, rangeLineLayerId]

export const useMapRanges = (mapRef, selectedRangeGeoJsonRef) => {
  const addRangeLayers = () => {
    const map = mapRef.value
    if (!map) return

    if (!map.getSource(rangeGeoJsonSourceId)) {
      map.addSource(rangeGeoJsonSourceId, {
        type: 'geojson',
        data: selectedRangeGeoJsonRef.value
      })
    }

    if (!map.getLayer(rangeFillLayerId)) {
      map.addLayer({
        id: rangeFillLayerId,
        type: 'fill',
        source: rangeGeoJsonSourceId,
        paint: {
          'fill-color': ['coalesce', ['get', 'rangeColor'], '#57a6f5'],
          'fill-opacity': 0.32
        }
      })
    }

    if (!map.getLayer(rangeLineLayerId)) {
      map.addLayer({
        id: rangeLineLayerId,
        type: 'line',
        source: rangeGeoJsonSourceId,
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#eaf4ff',
          'line-width': ['interpolate', ['linear'], ['zoom'], 5, 1.4, 10, 2.0, 16, 2.8],
          'line-opacity': 0.95
        }
      })
    }
  }

  const updateRangeGeoJson = () => {
    const map = mapRef.value
    if (!map) return

    const source = map.getSource(rangeGeoJsonSourceId)
    if (!source) return

    source.setData(selectedRangeGeoJsonRef.value)
  }

  return {
    addRangeLayers,
    updateRangeGeoJson
  }
}
