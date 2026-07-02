import { computed, ref } from 'vue'
import { solveGarbageRoute } from './routeApi'

const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })
const VEHICLE_COLOR_PALETTE = [
  '#f97316',
  '#22c55e',
  '#3b82f6',
  '#eab308',
  '#ef4444',
  '#14b8a6',
  '#a855f7',
  '#f43f5e',
  '#0ea5e9',
  '#84cc16'
]

const hasFeatures = (geojson) =>
  geojson?.type === 'FeatureCollection' && Array.isArray(geojson.features) && geojson.features.length > 0

const parseJsonObject = (value, fieldName) => {
  const trimmed = String(value || '').trim()
  if (!trimmed) return {}
  try {
    const parsed = JSON.parse(trimmed)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error()
    }
    return parsed
  } catch {
    throw new Error(`${fieldName}必須是有效的 JSON 物件`)
  }
}

const createInitialForm = () => ({
  nodeSourceMode: 'preset',
  preset: 'stat_zone_population_points',
  datasetDataId: 'custom_nodes',
  demandField: 'P_CNT',
  demandMultiplierKg: 1.36,
  nodeFiltersText: '',
  nodeLimit: 5000,
  startCoord: null,
  endCoord: null,
  vehicleCount: 2,
  vehicleCapacityKg: 3000,
  disposalDataId: 'moenv_incinerators',
  disposalFiltersText: '',
  aggregationEnabled: true,
  aggregationCellMeters: 300,
  aggregationThreshold: 500,
  snapToRoadEnabled: true,
  snapToRoadMaxDistanceMeters: 200,
  costMetric: 'duration',
  costProfile: 'driving',
  osrmBaseUrl: import.meta.env.VITE_OSRM_BASE_URL || 'http://localhost:5001',
  solverTimeLimitSec: 15,
  solverRandomSeed: 1
})

const getVehicleColor = (index) => VEHICLE_COLOR_PALETTE[index % VEHICLE_COLOR_PALETTE.length]

const buildRouteGeoJson = (result) => {
  const routeFeatures = []
  const stopFeatures = []
  for (const [routeIndex, route] of (result?.routes || []).entries()) {
    const vehicleColor = getVehicleColor(routeIndex)
    if (route?.geometry?.type === 'LineString' && Array.isArray(route?.geometry?.coordinates)) {
      routeFeatures.push({
        type: 'Feature',
        geometry: route.geometry,
        properties: {
          vehicleId: route.vehicle_id,
          vehicleColor,
          distanceM: route.distance_m || 0,
          durationS: route.duration_s || 0
        }
      })
    }

    for (const [stopIndex, stop] of (route?.stops || []).entries()) {
      stopFeatures.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [stop.lng, stop.lat]
        },
        properties: {
          vehicleId: route.vehicle_id,
          vehicleColor,
          stopIndex,
          stopOrder: stopIndex + 1,
          stopOrderLabel: `${stopIndex + 1}`,
          type: stop.type,
          name: stop.name || stop.location_id,
          loadKg: stop.load_kg || 0,
          memberCount: stop.memberCount || 1,
          legFromPrevDistanceM:
            typeof stop.legFromPrevDistanceM === 'number' ? stop.legFromPrevDistanceM : null,
          legFromPrevDurationS:
            typeof stop.legFromPrevDurationS === 'number' ? stop.legFromPrevDurationS : null
        }
      })
    }
  }

  for (const dropped of result?.droppedNodes || []) {
    stopFeatures.push({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [dropped.lng, dropped.lat]
      },
      properties: {
        vehicleId: 'dropped',
        vehicleColor: '#ef4444',
        stopIndex: -1,
        stopOrder: null,
        stopOrderLabel: '',
        type: 'dropped',
        name: dropped.name || dropped.id,
        loadKg: dropped.demandKg || 0,
        memberCount: dropped.memberCount || 1
      }
    })
  }

  return {
    routeLines: { type: 'FeatureCollection', features: routeFeatures },
    routeStops: { type: 'FeatureCollection', features: stopFeatures }
  }
}

export const useRoutePlanner = (apiBaseUrl, selectedRangeRequestRef, selectedRangeGeoJsonRef) => {
  const routeForm = ref(createInitialForm())
  const routeRuntime = ref({
    loading: false,
    error: '',
    solvedAt: null
  })
  const routeLayerVisibility = ref({
    line: true,
    stops: true,
    anchors: true,
    vehicles: {}
  })
  const routeResult = ref(null)
  const routeLineGeoJson = ref(emptyFeatureCollection())
  const routeStopGeoJson = ref(emptyFeatureCollection())
  const pickMode = ref('')

  const routeSummary = computed(() => routeResult.value?.summary || {})
  const routeRows = computed(() => routeResult.value?.routes || [])
  const droppedRows = computed(() => routeResult.value?.droppedNodes || [])

  const routeAnchorGeoJson = computed(() => {
    const features = []
    if (Array.isArray(routeForm.value.startCoord)) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: routeForm.value.startCoord },
        properties: { type: 'start', name: '起點場站' }
      })
    }
    if (Array.isArray(routeForm.value.endCoord)) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: routeForm.value.endCoord },
        properties: { type: 'end', name: '終點場站' }
      })
    }
    return { type: 'FeatureCollection', features }
  })

  const setPickMode = (mode) => {
    if (!['start', 'end', ''].includes(mode)) return
    pickMode.value = mode
  }

  const setDepotCoord = (mode, coordinate) => {
    if (!Array.isArray(coordinate) || coordinate.length !== 2) return
    if (mode === 'start') {
      routeForm.value.startCoord = coordinate
      pickMode.value = ''
    } else if (mode === 'end') {
      routeForm.value.endCoord = coordinate
      pickMode.value = ''
    }
  }

  const clearResult = () => {
    routeResult.value = null
    routeLineGeoJson.value = emptyFeatureCollection()
    routeStopGeoJson.value = emptyFeatureCollection()
    routeLayerVisibility.value = {
      ...routeLayerVisibility.value,
      vehicles: {}
    }
  }

  const toggleRouteLayerVisibility = (layerKey) => {
    if (!['line', 'stops', 'anchors'].includes(layerKey)) return
    const currentEnabled = routeLayerVisibility.value[layerKey] !== false
    routeLayerVisibility.value = {
      ...routeLayerVisibility.value,
      [layerKey]: !currentEnabled
    }
  }

  const toggleRouteVehicleVisibility = (vehicleId) => {
    if (!vehicleId) return
    const currentVehicles = routeLayerVisibility.value.vehicles || {}
    const currentEnabled = currentVehicles[vehicleId] !== false
    routeLayerVisibility.value = {
      ...routeLayerVisibility.value,
      vehicles: {
        ...currentVehicles,
        [vehicleId]: !currentEnabled
      }
    }
  }

  const syncRouteVehicleVisibility = (result) => {
    const previousVehicles = routeLayerVisibility.value.vehicles || {}
    const nextVehicles = {}
    for (const route of result?.routes || []) {
      const vehicleId = route?.vehicle_id
      if (!vehicleId) continue
      nextVehicles[vehicleId] = previousVehicles[vehicleId] !== false
    }
    routeLayerVisibility.value = {
      ...routeLayerVisibility.value,
      vehicles: nextVehicles
    }
  }

  const solveRoute = async () => {
    routeRuntime.value = {
      ...routeRuntime.value,
      loading: true,
      error: ''
    }
    try {
      if (!Array.isArray(routeForm.value.startCoord) || !Array.isArray(routeForm.value.endCoord)) {
        throw new Error('請在地圖上選取起點與終點場站')
      }

      const nodeFilters = parseJsonObject(routeForm.value.nodeFiltersText, '節點篩選條件')
      const disposalFilters = parseJsonObject(routeForm.value.disposalFiltersText, '處理場篩選條件')
      const selectedRangeRequest = selectedRangeRequestRef?.value || {}
      const rangePayload = {
        countyCodes: selectedRangeRequest.countyCodes || [],
        townCodes: selectedRangeRequest.townCodes || [],
        villageCodes: selectedRangeRequest.villageCodes || [],
        statZone2Codes: selectedRangeRequest.statZone2Codes || [],
        statZone1Codes: selectedRangeRequest.statZone1Codes || [],
        statZoneCodes: selectedRangeRequest.statZoneCodes || []
      }
      if (hasFeatures(selectedRangeGeoJsonRef?.value)) {
        rangePayload.geojson = selectedRangeGeoJsonRef.value
      }

      const nodeSource = {
        mode: routeForm.value.nodeSourceMode,
        demandField: routeForm.value.demandField,
        demandMultiplierKg: Number(routeForm.value.demandMultiplierKg),
        limit: Number(routeForm.value.nodeLimit)
      }
      if (Object.keys(nodeFilters).length) {
        nodeSource.filters = nodeFilters
      }
      if (routeForm.value.nodeSourceMode === 'preset') {
        nodeSource.preset = routeForm.value.preset
      } else {
        nodeSource.dataId = routeForm.value.datasetDataId
      }

      const payload = {
        nodeSource,
        range: rangePayload,
        depot: {
          start: routeForm.value.startCoord,
          end: routeForm.value.endCoord
        },
        vehicles: {
          count: Number(routeForm.value.vehicleCount),
          capacityKg: Number(routeForm.value.vehicleCapacityKg)
        },
        disposal: {
          sourceDataId: routeForm.value.disposalDataId,
          policy: 'nearest_auto',
          filters: disposalFilters
        },
        aggregation: {
          enabled: routeForm.value.aggregationEnabled === true,
          cellMeters: Number(routeForm.value.aggregationCellMeters),
          maxNodesBeforeAggregate: Number(routeForm.value.aggregationThreshold),
          snapToRoad: {
            enabled: routeForm.value.snapToRoadEnabled === true,
            maxDistanceMeters: Number(routeForm.value.snapToRoadMaxDistanceMeters)
          }
        },
        cost: {
          mode: 'osrm',
          metric: routeForm.value.costMetric,
          profile: routeForm.value.costProfile,
          osrmBaseUrl: routeForm.value.osrmBaseUrl
        },
        solver: {
          timeLimitSec: Number(routeForm.value.solverTimeLimitSec),
          randomSeed: Number(routeForm.value.solverRandomSeed)
        }
      }

      const result = await solveGarbageRoute(apiBaseUrl, payload)
      routeResult.value = result
      syncRouteVehicleVisibility(result)
      const geojson = buildRouteGeoJson(result)
      routeLineGeoJson.value = geojson.routeLines
      routeStopGeoJson.value = geojson.routeStops
      routeRuntime.value = {
        loading: false,
        error: '',
        solvedAt: Date.now()
      }
    } catch (error) {
      routeRuntime.value = {
        ...routeRuntime.value,
        loading: false,
        error: error?.message || '路線求解失敗'
      }
      clearResult()
    }
  }

  return {
    routeForm,
    routeRuntime,
    routeResult,
    routeSummary,
    routeRows,
    droppedRows,
    routeLayerVisibility,
    routeLineGeoJson,
    routeStopGeoJson,
    routeAnchorGeoJson,
    pickMode,
    setPickMode,
    setDepotCoord,
    clearResult,
    toggleRouteLayerVisibility,
    toggleRouteVehicleVisibility,
    solveRoute
  }
}
