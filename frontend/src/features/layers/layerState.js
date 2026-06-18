export const createLayerState = (apiBaseUrl) => ({
  county: {
    label: '縣市界線',
    sourceId: 'county-source',
    layerId: 'county-line',
    sourceLayer: 'county',
    url: `${apiBaseUrl}/tiles/county/{z}/{x}/{y}.pbf`,
    color: '#2f7df4',
    lineWidthScale: 1,
    maxNativeZoom: 9,
    minVisibleZoom: 5,
    active: true
  },
  township: {
    label: '鄉鎮市區界線',
    sourceId: 'township-source',
    layerId: 'township-line',
    sourceLayer: 'township',
    url: `${apiBaseUrl}/tiles/township/{z}/{x}/{y}.pbf`,
    color: '#27a693',
    lineWidthScale: 1,
    maxNativeZoom: 12,
    minVisibleZoom: 8,
    active: true
  },
  village: {
    label: '村里界線',
    sourceId: 'village-source',
    layerId: 'village-line',
    sourceLayer: 'village',
    url: `${apiBaseUrl}/tiles/village/{z}/{x}/{y}.pbf`,
    color: '#d17827',
    lineWidthScale: 1,
    maxNativeZoom: 14,
    minVisibleZoom: 12,
    active: true
  },
  stat_zone_2: {
    label: '二級發布區',
    sourceId: 'stat_zone_2-source',
    layerId: 'stat_zone_2-line',
    sourceLayer: 'stat_zone_2',
    url: `${apiBaseUrl}/tiles/stat_zone_2/{z}/{x}/{y}.pbf`,
    color: '#a78bfa',
    lineWidthScale: 1,
    maxNativeZoom: 12,
    minVisibleZoom: 9,
    active: false
  },
  stat_zone_1: {
    label: '一級發布區',
    sourceId: 'stat_zone_1-source',
    layerId: 'stat_zone_1-line',
    sourceLayer: 'stat_zone_1',
    url: `${apiBaseUrl}/tiles/stat_zone_1/{z}/{x}/{y}.pbf`,
    color: '#34d399',
    lineWidthScale: 1,
    maxNativeZoom: 13,
    minVisibleZoom: 11,
    active: false
  },
  stat_zone: {
    label: '最小統計區',
    sourceId: 'stat_zone-source',
    layerId: 'stat_zone-line',
    sourceLayer: 'stat_zone',
    url: `${apiBaseUrl}/tiles/stat_zone/{z}/{x}/{y}.pbf`,
    color: '#72e9b7',
    lineWidthScale: 1,
    maxNativeZoom: 14,
    minVisibleZoom: 12,
    active: false
  }
})
