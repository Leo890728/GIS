import { statZonePopulationStyle, taichungGarbageVehicle } from './style-handlers'
import { buildTruckIcon } from './icons'

/**
 * Data source registry guide
 *
 * Use createDataSourceRegistry() to register each dataset shown in Data Panel.
 * Each top-level key is a local UI key (e.g. taichungGarbageDynamic), and
 * dataId must match backend /datasets entries.
 *
 * Minimal example:
 * {
 *   sampleSource: {
 *     label: 'Sample Source',
 *     detail: 'sample_data_id',
 *     dataId: 'sample_data_id',
 *     sourceId: 'data-sample-source',
 *     layerId: 'data-sample-points',
 *     active: true,
 *     query: { filters: {}, limit: 1000 },
 *     aggregate: {
 *       metrics: ['count'],
 *       groupBy: 'groupField',
 *       summary: {
 *         sumField: 'value',
 *         sumLabel: 'Value Sum',
 *         avgField: 'value',
 *         avgLabel: 'Value Avg'
 *       }
 *     },
 *     dynamic: { enabled: false, pollIntervalMs: 60000 },
 *     supportedModes: ['points', 'heatmap'],
 *     icons: [
 *       { id: 'sample-normal', builder: buildTruckIcon, options: { color: '#4ade80' } },
 *       { id: 'sample-from-url', src: 'https://example.com/icon.png' }
 *     ],
 *     styleHandler: {
 *       handler: customHandlerFunction,
 *       params: { fieldName: 'valueField' }
 *     },
 *     tooltip: {
 *       enabled: true,
 *       titleField: 'name',
 *       items: [
 *         { label: 'Name', field: 'name' },
 *         { label: 'Value', field: 'value', format: 'number', digits: 1 }
 *       ]
 *     },
 *     style: {
 *       mode: 'points',
 *       color: '#4ade80',
 *       iconId: 'sample-normal',
 *       pointSize: 6,
 *       heatmapIntensity: 1,
 *       weightProperty: 'value'
 *     }
 *   }
 * }
 *
 * Notes:
 * - sourceId/layerId must be unique across all data sources.
 * - supportedModes controls what the UI and map are allowed to render.
 * - icons is optional and defines point symbols this data source can use.
 * - styleHandler is optional and runs per feature before map rendering.
 * - styleHandler.handler can be a direct function reference.
 * - Conditional icon example:
 *   styleHandler: {
 *     handler: taichungGarbageVehicle,
 *     params: {
 *       iconIds: {
 *         normal: 'sample-normal',
 *         medium: 'sample-medium',
 *         fast: 'sample-fast',
 *         overSpeed: 'sample-overspeed'
 *       },
 *       iconByField: {
 *         cartype: {
 *           R: 'sample-recycle',
 *           N: 'sample-normal'
 *         }
 *       }
 *     }
 *   }
 *   // Priority: iconByField > iconIds(speed band) > style.iconId
 * - tooltip items support formatters: text, number, datetime, enumMap, booleanMap.
 */
const createDataSourceRegistry = (apiBaseUrl) => ({
  taichungGarbageDynamic: {
    label: 'Taichung Garbage & Recycling Trucks',
    detail: 'taichung_garbage_recycling_dynamic',
    dataId: 'taichung_garbage_recycling_dynamic',
    sourceId: 'data-live-points-source',
    layerId: 'data-live-points',
    active: true,
    query: {
      filters: {},
      limit: 5000
    },
    aggregate: {
      metrics: ['count', 'sum:SpeedValue', 'avg:SpeedValue'],
      groupBy: 'lineid',
      summary: {
        sumField: 'SpeedValue',
        sumLabel: 'Speed Sum',
        avgField: 'SpeedValue',
        avgLabel: 'Avg speed'
      }
    },
    dynamic: {
      enabled: true,
      pollIntervalMs: 600000
    },
    supportedModes: ['points', 'heatmap'],
    icons: [
      { id: 'tcg-v1-normal', builder: buildTruckIcon, options: { color: '#4ade80' } },
      { id: 'tcg-v1-medium', builder: buildTruckIcon, options: { color: '#facc15' } },
      { id: 'tcg-v1-fast', builder: buildTruckIcon, options: { color: '#fb923c' } },
      { id: 'tcg-v1-overspeed', builder: buildTruckIcon, options: { color: '#ef4444' } }
    ],
    styleHandler: {
      handler: taichungGarbageVehicle,
      params: {
        speedField: 'SpeedValue',
        overSpeedField: 'OverSpeed',
        normalColor: '#4ade80',
        mediumColor: '#facc15',
        fastColor: '#fb923c',
        overSpeedColor: '#ef4444',
        iconIds: {
          normal: 'tcg-v1-normal',
          medium: 'tcg-v1-medium',
          fast: 'tcg-v1-fast',
          overSpeed: 'tcg-v1-overspeed'
        },
        heatWeightBase: 1
      }
    },
    tooltip: {
      enabled: true,
      titleField: 'car',
      items: [
        { label: 'Line', field: 'lineid' },
        { label: 'Time', field: 'time', format: 'datetime' },
        { label: 'Location', field: 'location' },
        { label: 'Speed', field: 'SpeedValue', format: 'number', digits: 1, unit: 'km/h' },
        { label: 'Over Speed', field: 'OverSpeedText' },
        { label: 'Speed Band', field: 'SpeedBand' }
      ]
    },
    style: {
      mode: 'points',
      color: '#f2c94c',
      iconId: 'tcg-v1-normal',
      pointSize: 6,
      heatmapIntensity: 1,
      weightProperty: 'SpeedValue'
    }
  },
  taichungGarbageDynamicV2: {
    label: 'Taichung Garbage & Recycling Trucks (V2)',
    detail: 'taichung_garbage_recycling_dynamic_V2',
    dataId: 'taichung_garbage_recycling_dynamic_V2',
    sourceId: 'data-live-points-source-v2',
    layerId: 'data-live-points-v2',
    active: false,
    query: {
      filters: {},
      limit: 5000
    },
    aggregate: {
      metrics: ['count', 'avg:status'],
      groupBy: 'car_no',
      summary: {
        sumField: '',
        sumLabel: 'Sum',
        avgField: 'status',
        avgLabel: 'Avg status'
      }
    },
    dynamic: {
      enabled: true,
      pollIntervalMs: 60000
    },
    supportedModes: ['points'],
    icons: [
      { id: 'tcg-v2-fallback', builder: buildTruckIcon, options: { color: '#5ec8f2' } },
      { id: 'tcg-v2-garbage-o01', src: '/icons/tcg-v2/noGarbage_truck_o01.png' },
      { id: 'tcg-v2-garbage-o02', src: '/icons/tcg-v2/noGarbage_truck_o02.png' },
      { id: 'tcg-v2-garbage-o03', src: '/icons/tcg-v2/noGarbage_truck_o03.png' },
      { id: 'tcg-v2-garbage-o04', src: '/icons/tcg-v2/noGarbage_truck_o04.png' },
      { id: 'tcg-v2-garbage-o05', src: '/icons/tcg-v2/noGarbage_truck_o05.png' },
      { id: 'tcg-v2-garbage-o06', src: '/icons/tcg-v2/noGarbage_truck_o06.png' },
      { id: 'tcg-v2-garbage-o07', src: '/icons/tcg-v2/noGarbage_truck_o07.png' },
      { id: 'tcg-v2-garbage-o08', src: '/icons/tcg-v2/noGarbage_truck_o08.png' },
      { id: 'tcg-v2-recycle-o01', src: '/icons/tcg-v2/recycle_o01.png' },
      { id: 'tcg-v2-recycle-o02', src: '/icons/tcg-v2/recycle_o02.png' },
      { id: 'tcg-v2-recycle-o03', src: '/icons/tcg-v2/recycle_o03.png' },
      { id: 'tcg-v2-recycle-o04', src: '/icons/tcg-v2/recycle_o04.png' },
      { id: 'tcg-v2-recycle-o05', src: '/icons/tcg-v2/recycle_o05.png' },
      { id: 'tcg-v2-recycle-o06', src: '/icons/tcg-v2/recycle_o06.png' },
      { id: 'tcg-v2-recycle-o07', src: '/icons/tcg-v2/recycle_o07.png' },
      { id: 'tcg-v2-recycle-o08', src: '/icons/tcg-v2/recycle_o08.png' }
    ],
    styleHandler: {
      handler: taichungGarbageVehicle,
      params: {
        speedField: 'status',
        overSpeedField: '',
        normalColor: '#5ec8f2',
        mediumColor: '#79d48a',
        fastColor: '#f2994a',
        overSpeedColor: '#eb5757',
        iconIds: {
          normal: 'tcg-v2-fallback',
          medium: 'tcg-v2-fallback',
          fast: 'tcg-v2-fallback',
          overSpeed: 'tcg-v2-fallback'
        },
        directionalIcons: {
          directionField: 'direct',
          vehicleField: 'cartype',
          vehiclePrefixMap: {
            N: 'tcg-v2-garbage',
            R: 'tcg-v2-recycle'
          },
          defaultVehiclePrefix: 'tcg-v2-garbage',
          directionMap: {
            '\u2191': 'o01',
            '\u2197': 'o02',
            '\u2192': 'o03',
            '\u2198': 'o04',
            '\u2193': 'o05',
            '\u2199': 'o06',
            '\u2190': 'o07',
            '\u2196': 'o08'
          }
        },
        heatWeightBase: 1
      }
    },
    tooltip: {
      enabled: true,
      titleField: 'car_licence',
      items: [
        { label: 'Car', field: 'car_licence' },
        { label: 'Time', field: 'dt', format: 'datetime' },
        { label: 'Location', field: 'caption' },
        { label: 'Status', field: 'status', format: 'number', digits: 0 },
        { label: 'Direction', field: 'direct' }
      ]
    },
    style: {
      mode: 'points',
      color: '#5ec8f2',
      iconId: 'tcg-v2-fallback',
      pointSize: 6,
      heatmapIntensity: 1,
      weightProperty: 'status'
    }
  },
  statZonePopulation: {
    label: 'Stat Zone Population',
    detail: 'stat_zone_min_113 (P_CNT)',
    dataId: 'stat_zone_population_points',
    sourceId: 'data-stat-zone-population-source',
    layerId: 'data-stat-zone-population',
    active: false,
    query: {
      endpoint: '/data/admin/stat-zone-points',
      useRangeRequest: true,
      filters: {},
      limit: 200000
    },
    aggregate: {
      endpoint: '/data/admin/aggregate',
      useRangeRequest: true,
      metrics: ['count', 'sum:P_CNT'],
      summary: {
        sumField: 'P_CNT',
        sumLabel: 'Population',
        avgField: '',
        avgLabel: '',
        sumDigits: 0
      },
      priority: 100
    },
    dynamic: {
      enabled: false
    },
    supportedModes: ['points', 'heatmap'],
    icons: [],
    styleHandler: {
      handler: statZonePopulationStyle
    },
    tooltip: {
      enabled: true,
      titleField: 'name_zh',
      items: [
        { label: 'Stat Zone', field: 'CODEBASE' },
        { label: 'Village', field: 'VILLAGE_CODE' },
        { label: 'Population', field: 'P_CNT', format: 'number', digits: 0 }
      ]
    },
    style: {
      mode: 'heatmap',
      color: '#72e9b7',
      pointSize: 6,
      heatmapIntensity: 1.4,
      weightProperty: 'P_CNT'
    }
  }
})

const toLayerEntry = (entry) => {
  const supportedModes =
    Array.isArray(entry.supportedModes) && entry.supportedModes.length
      ? entry.supportedModes.filter((mode) => ['points', 'heatmap'].includes(mode))
      : ['points', 'heatmap']
  const style = {
    mode: 'points',
    ...(entry.style || {})
  }
  if (!supportedModes.includes(style.mode)) {
    style.mode = supportedModes[0] || 'points'
  }
  return {
    ...entry,
    supportedModes,
    query: {
      dataId: entry.dataId,
      ...(entry.query || {})
    },
    aggregate: {
      metrics: ['count'],
      ...(entry.aggregate || {})
    },
    styleHandler: entry.styleHandler || null,
    icons: Array.isArray(entry.icons) ? entry.icons : [],
    tooltip: {
      enabled: false,
      titleField: '',
      items: [],
      ...(entry.tooltip || {})
    },
    style
  }
}

export const createDataLayerState = (apiBaseUrl) =>
  Object.fromEntries(Object.entries(createDataSourceRegistry(apiBaseUrl)).map(([key, entry]) => [key, toLayerEntry(entry)]))
