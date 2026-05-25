export const createLayerState = (apiBaseUrl) => ({
  county: {
    label: '縣市界線',
    sourceId: 'county-source',
    layerId: 'county-line',
    sourceLayer: 'county',
    url: `${apiBaseUrl}/tiles/county/{z}/{x}/{y}.pbf`,
    color: '#2f7df4',
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
    maxNativeZoom: 14,
    minVisibleZoom: 12,
    active: true
  }
})
