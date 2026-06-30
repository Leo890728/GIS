import { statZonePopulationStyle, taichungGarbageVehicle } from './style-handlers'
import { buildTruckIcon } from './icons'

/**
 * Data source registry — the standard shape for a Data Panel dataset.
 *
 * Each entry below is a *partial* `DataSourceConfig`: only fields that differ
 * from the defaults need to be set. `toLayerEntry()` (bottom of this file) is the
 * single source of defaults and normalization. Keep entries in the canonical key
 * order documented by the typedef: identity → data → render.
 *
 * Conventions
 * - `sourceId` / `layerId` must be globally unique across all data sources.
 * - `dataId` must match a backend `/datasets` entry.
 * - Omit a field to take its default (e.g. drop `dynamic` for a static layer,
 *   drop `supportedModes` to allow both points + heatmap).
 * - `styleHandler.params` is handler-specific (see the referenced handler).
 * - tooltip item `format`: text | number | datetime | enumMap | booleanMap.
 *
 * @typedef {Object} QueryConfig
 * @property {string}  [endpoint='/data/query']
 * @property {boolean} [useRangeRequest]   send the selected admin range as codes
 * @property {Object}  [filters]
 * @property {number}  [limit]
 *
 * @typedef {Object} AggregateSummary
 * @property {string} [sumField] @property {string} [sumLabel] @property {number} [sumDigits]
 * @property {string} [avgField] @property {string} [avgLabel]
 *
 * @typedef {Object} AggregateConfig
 * @property {string}   [endpoint='/data/aggregate']
 * @property {boolean}  [useRangeRequest]
 * @property {string[]} [metrics=['count']]    e.g. 'count', 'sum:FIELD', 'avg:FIELD'
 * @property {string}   [groupBy]
 * @property {AggregateSummary} [summary]
 * @property {number}   [priority]             higher wins when picking the active aggregate
 *
 * @typedef {Object} DynamicConfig
 * @property {boolean} enabled
 * @property {number}  [pollIntervalMs=60000]
 *
 * @typedef {Object} IconConfig
 * @property {string}   id
 * @property {string}   [src]                 image URL (mutually exclusive with builder)
 * @property {Function} [builder]             runtime icon builder (e.g. buildTruckIcon)
 * @property {Object}   [options]             builder options
 *
 * @typedef {Object} StyleHandlerConfig
 * @property {Function} handler               per-feature style function
 * @property {Object<string,*>} [params]      handler-specific parameters
 *
 * @typedef {Object} TooltipItem
 * @property {string} label
 * @property {string} field
 * @property {string} [format]                text|number|datetime|enumMap|booleanMap
 * @property {number} [digits]
 *
 * @typedef {Object} TooltipConfig
 * @property {boolean}       [enabled=false]
 * @property {string}        [titleTemplate='']   title with `{field}` placeholders, e.g. '車牌 {car_licence}'
 * @property {TooltipItem[]} [items=[]]
 *
 * @typedef {Object} StyleConfig
 * @property {'points'|'heatmap'} [mode='points']
 * @property {string} [color]
 * @property {string} [iconId]
 * @property {number} [iconSize]
 * @property {number} [pointSize]
 * @property {number} [heatmapIntensity]
 * @property {string} [weightProperty]
 *
 * @typedef {Object} DataSourceConfig
 * @property {string}  label                  UI display name
 * @property {string}  [detail]               short subtitle / source hint
 * @property {string}  dataId                 backend dataset id
 * @property {string}  sourceId               MapLibre source id (unique)
 * @property {string}  layerId                MapLibre layer id (unique)
 * @property {boolean} [active=false]
 * @property {QueryConfig}        [query]
 * @property {AggregateConfig}    [aggregate]
 * @property {DynamicConfig}      [dynamic]   omit for a static (non-polled) layer
 * @property {('points'|'heatmap')[]} [supportedModes=['points','heatmap']]
 * @property {IconConfig[]}       [icons=[]]
 * @property {StyleHandlerConfig} [styleHandler]
 * @property {TooltipConfig}      [tooltip]
 * @property {StyleConfig}        [style]
 */

/** @returns {Object<string, DataSourceConfig>} */
const createDataSourceRegistry = (apiBaseUrl) => ({
  taichungGarbageDynamicV2: {
    label: '台中市垃圾清運',
    detail: 'taichung_garbage_recycling_dynamic_V2',
    dataId: 'taichung_garbage_recycling_dynamic_V2',
    sourceId: 'data-live-points-source-v2',
    layerId: 'data-live-points-v2',
    query: { filters: {}, limit: 5000 },
    aggregate: {
      metrics: ['count', 'avg:status'],
      groupBy: 'car_no',
      summary: { sumField: '', sumLabel: 'Sum', avgField: 'status', avgLabel: 'Avg status' }
    },
    dynamic: { enabled: true, pollIntervalMs: 15000 },
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
          vehiclePrefixMap: { N: 'tcg-v2-garbage', R: 'tcg-v2-recycle' },
          defaultVehiclePrefix: 'tcg-v2-garbage',
          directionMap: {
            '↑': 'o01',
            '↗': 'o02',
            '→': 'o03',
            '↘': 'o04',
            '↓': 'o05',
            '↙': 'o06',
            '←': 'o07',
            '↖': 'o08'
          }
        },
        heatWeightBase: 1
      }
    },
    tooltip: {
      enabled: true,
      titleTemplate: '{car_licence}',
      items: [
        { label: 'Car', field: 'car_licence' },
        { label: 'Time', field: 'dt', format: 'datetime' },
        { label: 'Location', field: 'caption' },
        { label: 'Status', field: 'status', format: 'number', digits: 0 },
        { label: 'Direction', field: 'direct' }
      ]
    },
    style: {
      color: '#5ec8f2',
      iconId: 'tcg-v2-fallback',
      pointSize: 6,
      heatmapIntensity: 1,
      weightProperty: 'status'
    }
  },

  moenvIncinerators: {
    label: '焚化廠基本資料',
    detail: 'moenv_incinerators',
    dataId: 'moenv_incinerators',
    sourceId: 'data-moenv-incinerators-source',
    layerId: 'data-moenv-incinerators',
    query: { filters: {}, limit: 1000 },
    aggregate: {
      summary: {
        sumField: 'dsnprcqt',
        sumLabel: '設計處理量合計 (公噸/日)',
        avgField: 'dsnprcqt',
        avgLabel: '平均設計處理量 (公噸/日)',
        sumDigits: 0
      }
    },
    supportedModes: ['points'],
    icons: [{ id: 'incinerator', src: '/icons/incinerator.png' }],
    tooltip: {
      enabled: true,
      titleTemplate: '{icnrtname}',
      items: [
        { label: '焚化廠名稱', field: 'icnrtname' },
        { label: '地址', field: 'budadd' },
        { label: '主管環保局', field: 'locaepb' },
        { label: '操作單位', field: 'oprtdept' },
        { label: '營運型態', field: 'weptype' },
        { label: '爐數', field: 'icnrtnum', format: 'number', digits: 0 },
        { label: '設計處理量 (公噸/日)', field: 'dsnprcqt', format: 'number', digits: 0 },
        { label: '發電機組裝置容量 (百萬瓦)', field: 'dsneleqt', format: 'number', digits: 2 },
        { label: '設計熱值 (kcal/kg)', field: 'dsnhv', format: 'number', digits: 0 },
        { label: '開始營運年月', field: 'opendate' },
        { label: '開始操作日期', field: 'oprtdate' },
        { label: '興建主辦機關', field: 'budmajororg' },
        { label: '營運監督機構', field: 'opradmunit' },
        { label: '焚化廠網址', field: 'epcwebaddr' },
        { label: '系統代碼', field: 'wepno' }
      ]
    },
    style: { color: '#f97316', iconId: 'incinerator', iconSize: 1 }
  },

  statZonePopulation: {
    label: 'Stat Zone Population',
    detail: 'stat_zone (P_CNT)',
    dataId: 'stat_zone_population_points',
    sourceId: 'data-stat-zone-population-source',
    layerId: 'data-stat-zone-population',
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
      summary: { sumField: 'P_CNT', sumLabel: 'Population', avgField: '', avgLabel: '', sumDigits: 0 },
      priority: 100
    },
    styleHandler: { handler: statZonePopulationStyle },
    tooltip: {
      enabled: true,
      titleTemplate: '{name_zh}',
      items: [
        { label: 'Stat Zone', field: 'CODEBASE' },
        { label: 'Village', field: 'VILLAGE_CODE' },
        { label: 'Population', field: 'P_CNT', format: 'number', digits: 0 }
      ]
    },
    style: { mode: 'heatmap', color: '#72e9b7', pointSize: 6, heatmapIntensity: 1.4, weightProperty: 'P_CNT' }
  }
})

/**
 * Normalize a partial {@link DataSourceConfig} into a complete layer entry by
 * filling every default. This is the single source of defaults for the registry.
 * @param {DataSourceConfig} entry
 */
const toLayerEntry = (entry) => {
  const supportedModes =
    Array.isArray(entry.supportedModes) && entry.supportedModes.length
      ? entry.supportedModes.filter((mode) => ['points', 'heatmap'].includes(mode))
      : ['points', 'heatmap']
  const style = { mode: 'points', ...(entry.style || {}) }
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
    dynamic: {
      enabled: false,
      ...(entry.dynamic || {})
    },
    styleHandler: entry.styleHandler || null,
    icons: Array.isArray(entry.icons) ? entry.icons : [],
    tooltip: {
      enabled: false,
      titleTemplate: '',
      items: [],
      ...(entry.tooltip || {})
    },
    style
  }
}

export const createDataLayerState = (apiBaseUrl) =>
  Object.fromEntries(Object.entries(createDataSourceRegistry(apiBaseUrl)).map(([key, entry]) => [key, toLayerEntry(entry)]))
