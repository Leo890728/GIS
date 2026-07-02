const routeLineSourceId = 'route-line-source'
const routeLineLayerId = 'route-line-layer'
const routeStopSourceId = 'route-stop-source'
const routeStopLayerId = 'route-stop-layer'
const routeStopOrderLayerId = 'route-stop-order-layer'
const routeAnchorSourceId = 'route-anchor-source'
const routeAnchorLayerId = 'route-anchor-layer'

const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })
const alwaysMatchFilter = ['all']
// Expression form — a bare ['==', 1, 0] parses as a legacy filter and fails
// validation ("filter[1]: string expected, number found").
const neverMatchFilter = ['boolean', false]

const toVisibility = (enabled) => (enabled === false ? 'none' : 'visible')

const getRouteVisibility = (routeVisibilityRef) => {
  const state = routeVisibilityRef?.value || {}
  return {
    line: state.line !== false,
    stops: state.stops !== false,
    anchors: state.anchors !== false,
    vehicles: state.vehicles && typeof state.vehicles === 'object' ? state.vehicles : {}
  }
}

const getVehicleFilterState = (vehiclesVisibility) => {
  const entries = Object.entries(vehiclesVisibility || {}).filter(([vehicleId]) => !!vehicleId)
  if (!entries.length) {
    return { mode: 'all', vehicleIds: [] }
  }
  const visibleVehicleIds = entries
    .filter(([, enabled]) => enabled !== false)
    .map(([vehicleId]) => vehicleId)
  if (!visibleVehicleIds.length) {
    return { mode: 'none', vehicleIds: [] }
  }
  return { mode: 'partial', vehicleIds: visibleVehicleIds }
}

const buildLineFilter = (vehicleFilterState) => {
  if (vehicleFilterState.mode === 'all') return alwaysMatchFilter
  if (vehicleFilterState.mode === 'none') return neverMatchFilter
  return ['in', ['get', 'vehicleId'], ['literal', vehicleFilterState.vehicleIds]]
}

const buildStopFilter = (vehicleFilterState) => {
  if (vehicleFilterState.mode === 'all') return alwaysMatchFilter
  if (vehicleFilterState.mode === 'none') {
    return ['==', ['get', 'type'], 'dropped']
  }
  return [
    'any',
    ['==', ['get', 'type'], 'dropped'],
    ['in', ['get', 'vehicleId'], ['literal', vehicleFilterState.vehicleIds]]
  ]
}

const buildStopOrderFilter = (vehicleFilterState) => {
  if (vehicleFilterState.mode === 'all') {
    return ['>=', ['get', 'stopIndex'], 0]
  }
  if (vehicleFilterState.mode === 'none') {
    return neverMatchFilter
  }
  return [
    'all',
    ['>=', ['get', 'stopIndex'], 0],
    ['in', ['get', 'vehicleId'], ['literal', vehicleFilterState.vehicleIds]]
  ]
}

export const useMapRouteLayers = (
  mapRef,
  routeLineGeoJsonRef,
  routeStopGeoJsonRef,
  routeAnchorGeoJsonRef,
  routeVisibilityRef
) => {
  const addRouteLayers = () => {
    const map = mapRef.value
    if (!map) return
    const visibility = getRouteVisibility(routeVisibilityRef)
    const vehicleFilterState = getVehicleFilterState(visibility.vehicles)

    if (!map.getSource(routeLineSourceId)) {
      map.addSource(routeLineSourceId, {
        type: 'geojson',
        data: routeLineGeoJsonRef.value || emptyFeatureCollection()
      })
    }

    if (!map.getLayer(routeLineLayerId)) {
      map.addLayer({
        id: routeLineLayerId,
        type: 'line',
        source: routeLineSourceId,
        filter: buildLineFilter(vehicleFilterState),
        layout: {
          'line-join': 'round',
          'line-cap': 'round',
          visibility: toVisibility(visibility.line)
        },
        paint: {
          'line-color': ['get', 'vehicleColor'],
          'line-width': ['interpolate', ['linear'], ['zoom'], 6, 1.8, 11, 3.2, 16, 5.0],
          'line-opacity': 0.88
        }
      })
    }

    if (!map.getSource(routeStopSourceId)) {
      map.addSource(routeStopSourceId, {
        type: 'geojson',
        data: routeStopGeoJsonRef.value || emptyFeatureCollection()
      })
    }

    if (!map.getLayer(routeStopLayerId)) {
      map.addLayer({
        id: routeStopLayerId,
        type: 'circle',
        source: routeStopSourceId,
        filter: buildStopFilter(vehicleFilterState),
        layout: {
          visibility: toVisibility(visibility.stops)
        },
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 3.2, 12, 5, 16, 7],
          'circle-color': ['case', ['==', ['get', 'type'], 'dropped'], '#ef4444', ['get', 'vehicleColor']],
          'circle-stroke-color': '#0f1729',
          'circle-stroke-width': 1.2,
          'circle-opacity': 0.92
        }
      })
    }

    if (!map.getLayer(routeStopOrderLayerId)) {
      map.addLayer({
        id: routeStopOrderLayerId,
        type: 'symbol',
        source: routeStopSourceId,
        filter: buildStopOrderFilter(vehicleFilterState),
        layout: {
          visibility: toVisibility(visibility.stops),
          'text-field': ['get', 'stopOrderLabel'],
          'text-font': ['Open Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 9, 12, 11, 16, 13],
          'text-offset': [0, 0],
          'text-anchor': 'center',
          'text-allow-overlap': true,
          'text-ignore-placement': true
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': '#0f1729',
          'text-halo-width': 1.4
        }
      })
    }

    if (!map.getSource(routeAnchorSourceId)) {
      map.addSource(routeAnchorSourceId, {
        type: 'geojson',
        data: routeAnchorGeoJsonRef.value || emptyFeatureCollection()
      })
    }

    if (!map.getLayer(routeAnchorLayerId)) {
      map.addLayer({
        id: routeAnchorLayerId,
        type: 'circle',
        source: routeAnchorSourceId,
        layout: {
          visibility: toVisibility(visibility.anchors)
        },
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 5.5, 12, 8, 16, 10],
          'circle-color': [
            'match',
            ['get', 'type'],
            'start',
            '#22d3ee',
            'end',
            '#a78bfa',
            '#ffffff'
          ],
          'circle-stroke-color': '#eaf4ff',
          'circle-stroke-width': 1.8,
          'circle-opacity': 0.92
        }
      })
    }
  }

  const updateRouteGeoJson = () => {
    const map = mapRef.value
    if (!map) return

    const lineSource = map.getSource(routeLineSourceId)
    if (lineSource && typeof lineSource.setData === 'function') {
      lineSource.setData(routeLineGeoJsonRef.value || emptyFeatureCollection())
    }

    const stopSource = map.getSource(routeStopSourceId)
    if (stopSource && typeof stopSource.setData === 'function') {
      stopSource.setData(routeStopGeoJsonRef.value || emptyFeatureCollection())
    }

    const anchorSource = map.getSource(routeAnchorSourceId)
    if (anchorSource && typeof anchorSource.setData === 'function') {
      anchorSource.setData(routeAnchorGeoJsonRef.value || emptyFeatureCollection())
    }
  }

  const updateRouteVisibility = () => {
    const map = mapRef.value
    if (!map) return
    const visibility = getRouteVisibility(routeVisibilityRef)
    const vehicleFilterState = getVehicleFilterState(visibility.vehicles)

    if (map.getLayer(routeLineLayerId)) {
      map.setLayoutProperty(routeLineLayerId, 'visibility', toVisibility(visibility.line))
      map.setFilter(routeLineLayerId, buildLineFilter(vehicleFilterState))
    }
    if (map.getLayer(routeStopLayerId)) {
      map.setLayoutProperty(routeStopLayerId, 'visibility', toVisibility(visibility.stops))
      map.setFilter(routeStopLayerId, buildStopFilter(vehicleFilterState))
    }
    if (map.getLayer(routeStopOrderLayerId)) {
      map.setLayoutProperty(routeStopOrderLayerId, 'visibility', toVisibility(visibility.stops))
      map.setFilter(routeStopOrderLayerId, buildStopOrderFilter(vehicleFilterState))
    }
    if (map.getLayer(routeAnchorLayerId)) {
      map.setLayoutProperty(routeAnchorLayerId, 'visibility', toVisibility(visibility.anchors))
    }
  }

  return {
    addRouteLayers,
    updateRouteGeoJson,
    updateRouteVisibility
  }
}
