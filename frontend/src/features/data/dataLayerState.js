import { policeBroadcastingServiceStyle, statZonePopulationStyle, taichungGarbageVehicle } from './style-handlers'
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
 * @property {string} [field]                 single property value, formatted by `format`
 * @property {string} [template]              '{field}' template (raw, multi-field); overrides field/format
 * @property {string} [format]                text|number|datetime|enumMap|booleanMap
 * @property {number} [digits]
 *
 * @typedef {Object} TooltipConfig
 * @property {boolean}       [enabled=false]
 * @property {string}        [titleTemplate='']   title with `{field}` placeholders, e.g. '車牌 {car_licence}'
 * @property {TooltipItem[]} [items=[]]
 *
 * @typedef {Object} PointStyle
 * @property {string}  [color]               circle/point fallback colour
 * @property {string}  [iconId]              symbol icon id (falls back to circle if absent)
 * @property {number}  [iconSize]
 * @property {number}  [pointSize]
 * @property {boolean} [forceCircle]         render as a circle even if an icon exists
 * @property {boolean} [scalePointWithZoom]
 *
 * @typedef {Object} HeatmapStyle
 * @property {string} [weightProperty]       property driving the heatmap weight
 * @property {number} [heatmapIntensity]
 *
 * @typedef {Object} ModeStyles
 * @property {PointStyle}   [points]         present => 'points' is a supported mode
 * @property {HeatmapStyle} [heatmap]        present => 'heatmap' is a supported mode
 *
 * The styleHandler's per-feature dynamic output uses the same keys as PointStyle
 * (color/pointSize/iconId) plus `heatWeight`, and overrides these static
 * defaults via the map's `__style_*` properties.
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
 * @property {ModeStyles}         [style]     per-mode style; its keys define supportedModes
 * @property {'points'|'heatmap'} [defaultMode]  active mode (defaults to first key of `style`)
 * @property {IconConfig[]}       [icons=[]]
 * @property {StyleHandlerConfig} [styleHandler]
 * @property {TooltipConfig}      [tooltip]
 * @property {Object<string,string>} [propertyLabels]  extra field→label pairs for
 *   the analytics drawer (tooltip item labels are merged in automatically)
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
      summary: { sumField: '', sumLabel: '總和', avgField: 'status', avgLabel: '平均狀態' }
    },
    dynamic: { enabled: true, pollIntervalMs: 15000 },
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
    styleHandler: { handler: taichungGarbageVehicle },
    tooltip: {
      enabled: true,
      titleTemplate: '{car_licence}',
      items: [
        { label: '車號', field: 'car_licence' },
        { label: '時間', field: 'dt', format: 'datetime' },
        { label: '位置', field: 'caption' },
        { label: '狀態', field: 'status', format: 'number', digits: 0 },
        { label: '方向', field: 'direct' }
      ]
    },
    // Extra field labels beyond the tooltip items (analytics drawer shows every
    // property of a selected entity; tooltip labels are merged in automatically).
    propertyLabels: {
      car_no: '車號',
      cartype: '車種',
      OverSpeedText: '是否超速',
      SpeedBand: '速度級距'
    },
    style: {
      points: { color: '#5ec8f2', iconId: 'tcg-v2-fallback', pointSize: 6 }
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
    style: {
      points: { color: '#f97316', iconId: 'incinerator', iconSize: 1 }
    }
  },

  statZonePopulation: {
    label: '統計區人口',
    detail: '統計區 (P_CNT)',
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
      summary: { sumField: 'P_CNT', sumLabel: '人口數', avgField: '', avgLabel: '', sumDigits: 0 },
      priority: 100
    },
    styleHandler: { handler: statZonePopulationStyle },
    tooltip: {
      enabled: true,
      titleTemplate: '{name_zh}',
      items: [
        { label: '統計區代碼', field: 'CODEBASE' },
        { label: '村里代碼', field: 'VILLAGE_CODE' },
        { label: '人口數', field: 'P_CNT', format: 'number', digits: 0 }
      ]
    },
    defaultMode: 'heatmap',
    style: {
      points: { color: '#72e9b7', pointSize: 6 },
      heatmap: { weightProperty: 'P_CNT', heatmapIntensity: 1.4 }
    }
  },

  policeBroadcastingService: {
    label: '警廣即時路況',
    detail: 'police_broadcasting_service',
    dataId: 'police_broadcasting_service',
    sourceId: 'data-police-broadcasting-service-source',
    layerId: 'data-police-broadcasting-service',
    query: { filters: {}, limit: 5000 },
    aggregate: { metrics: ['count'], groupBy: 'roadtype' },
    dynamic: { enabled: true, pollIntervalMs: 300000 },
    styleHandler: {
      handler: policeBroadcastingServiceStyle,
      params: {
        roadtypeField: 'roadtype',
        colorMap: {
          事故: '#ef4444',      // 紅色
          交通障礙: '#f97316',  // 橘色
          道路施工: '#facc15'   // 黃色
        },
        fallbackColor: '#9ca3af' // 灰色 (其他)
      }
    },
    tooltip: {
      enabled: true,
      titleTemplate: '{areaNm}',
      items: [
        { label: '路況類別', field: 'roadtype' },
        { label: '地區', field: 'areaNm' },
        { label: '道路名稱', field: 'road' },
        { label: '路況說明', field: 'comment' },
        { label: '方向', field: 'direction' },
        { label: '資料來源', field: 'srcdetail' },
        { label: '發生日期', field: 'happendate' },
        { label: '發生時間', field: 'happentime' },
        { label: '修改時間', field: 'modDttm', format: 'datetime' },
        { label: 'UID', field: 'UID' }
      ]
    },
    style: {
      points: { color: '#3b82f6', pointSize: 6 },
      heatmap: { heatmapIntensity: 1 }
    }
  },

  taichungCleaningTeams: {
    label: '臺中市清潔隊',
    detail: 'taichung_cleaning_teams',
    dataId: 'taichung_cleaning_teams',
    sourceId: 'data-taichung-cleaning-teams-source',
    layerId: 'data-taichung-cleaning-teams',
    query: { filters: {}, limit: 1000 },
    icons: [{ id: 'cleaning-team', src: '/icons/cleaning-team.png' }],
    tooltip: {
      enabled: true,
      titleTemplate: '{隊別}',
      items: [
        { label: '隊別', field: '隊別' },
        { label: '辦公室地址', field: '辦公室地址' },
        { label: '負責轄區', field: '負責轄區' },
        { label: '市話', field: '市話' },
        { label: '傳真', field: '傳真' }
      ]
    },
    style: {
      points: { color: '#16a34a', iconId: 'cleaning-team', iconSize: 0.12 }
    }
  }
})

/**
 * Normalize a partial {@link DataSourceConfig} into a complete layer entry by
 * filling every default. This is the single source of defaults for the registry.
 * @param {DataSourceConfig} entry
 */
const MODES = ['points', 'heatmap']

const toLayerEntry = (entry) => {
  // supportedModes are the modes that have a style block; the active mode is
  // `defaultMode` (or the first supported). The per-mode style is flattened into
  // the single object the map layer consumes (point + heatmap keys don't collide).
  const modeStyles = entry.style || {}
  const supportedModes = MODES.filter((mode) => modeStyles[mode])
  const safeModes = supportedModes.length ? supportedModes : ['points']
  const mode = safeModes.includes(entry.defaultMode) ? entry.defaultMode : safeModes[0]
  const style = { mode, ...(modeStyles.points || {}), ...(modeStyles.heatmap || {}) }
  return {
    ...entry,
    supportedModes: safeModes,
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
    // field -> human label for the analytics drawer: tooltip labels first,
    // topped up with the entry's explicit extras.
    propertyLabels: {
      ...Object.fromEntries(
        (entry.tooltip?.items || [])
          .filter((item) => item.field && item.label)
          .map((item) => [item.field, item.label])
      ),
      ...(entry.propertyLabels || {})
    },
    style
  }
}

export const createDataLayerState = (apiBaseUrl) =>
  Object.fromEntries(Object.entries(createDataSourceRegistry(apiBaseUrl)).map(([key, entry]) => [key, toLayerEntry(entry)]))
