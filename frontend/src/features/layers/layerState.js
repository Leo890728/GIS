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
  stat_zone_min_113: {
    label: '最小統計區',
    sourceId: 'stat_zone_min_113-source',
    layerId: 'stat_zone_min_113-line',
    sourceLayer: 'datageojson',
    url: `${apiBaseUrl}/tiles/stat_zone_min_113/{z}/{x}/{y}.pbf`,
    color: '#72e9b7',
    lineWidthScale: 1,
    maxNativeZoom: 13,
    minVisibleZoom: 12,
    active: false
  }
})
