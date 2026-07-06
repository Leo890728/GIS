export const createLayerState = (apiBaseUrl) => {
  // MapLibre fetches vector tiles from a Web Worker, which has no document base
  // URL, so a relative `/tiles/...` (same-origin mode, empty apiBaseUrl) throws
  // "Failed to parse URL". Resolve to an absolute origin for tile sources.
  const tileBase = apiBaseUrl || (typeof window !== 'undefined' ? window.location.origin : '')
  // 邊界線 Z 軸遵照註冊順序：越早註冊越下層，越晚註冊越上層。
  return {
    stat_zone: {
      label: '最小統計區',
      sourceId: 'stat_zone-source',
      layerId: 'stat_zone-line',
      sourceLayer: 'stat_zone',
      url: `${tileBase}/tiles/stat_zone/{z}/{x}/{y}.pbf`,
      color: '#72e9b7',
      lineWidthScale: 1,
      maxNativeZoom: 14,
      minVisibleZoom: 14,
      active: false
    },
    stat_zone_1: {
      label: '一級發布區',
      sourceId: 'stat_zone_1-source',
      layerId: 'stat_zone_1-line',
      sourceLayer: 'stat_zone_1',
      url: `${tileBase}/tiles/stat_zone_1/{z}/{x}/{y}.pbf`,
      color: '#34d399',
      lineWidthScale: 1,
      maxNativeZoom: 13,
      minVisibleZoom: 13,
      active: false
    },
    stat_zone_2: {
      label: '二級發布區',
      sourceId: 'stat_zone_2-source',
      layerId: 'stat_zone_2-line',
      sourceLayer: 'stat_zone_2',
      url: `${tileBase}/tiles/stat_zone_2/{z}/{x}/{y}.pbf`,
      color: '#a78bfa',
      lineWidthScale: 1,
      maxNativeZoom: 12,
      minVisibleZoom: 12,
      active: false
    },
    village: {
      label: '村里界線',
      sourceId: 'village-source',
      layerId: 'village-line',
      sourceLayer: 'village',
      url: `${tileBase}/tiles/village/{z}/{x}/{y}.pbf`,
      color: '#d17827',
      lineWidthScale: 1,
      maxNativeZoom: 14,
      minVisibleZoom: 11,
      active: true
    },
    township: {
      label: '鄉鎮市區界線',
      sourceId: 'township-source',
      layerId: 'township-line',
      sourceLayer: 'township',
      url: `${tileBase}/tiles/township/{z}/{x}/{y}.pbf`,
      color: '#27a693',
      lineWidthScale: 1,
      maxNativeZoom: 12,
      minVisibleZoom: 8,
      active: true
    },
    county: {
      label: '縣市界線',
      sourceId: 'county-source',
      layerId: 'county-line',
      sourceLayer: 'county',
      url: `${tileBase}/tiles/county/{z}/{x}/{y}.pbf`,
      color: '#2f7df4',
      lineWidthScale: 1,
      maxNativeZoom: 9,
      minVisibleZoom: 5,
      active: true
    }
  }
}
