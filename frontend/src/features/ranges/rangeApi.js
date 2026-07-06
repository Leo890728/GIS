export const fetchRangeTree = async (apiBaseUrl) => {
  const response = await fetch(`${apiBaseUrl}/ranges/tree`)
  if (!response.ok) {
    throw new Error(`載入範圍樹失敗：${response.status}`)
  }
  return response.json()
}

export const fetchStatZoneChildren = async (apiBaseUrl, parentLevel, parentCode) => {
  const response = await fetch(
    `${apiBaseUrl}/ranges/stat-zones/${encodeURIComponent(parentLevel)}/${encodeURIComponent(parentCode)}/children`
  )
  if (!response.ok) {
    throw new Error(`載入統計區子節點失敗：${response.status}`)
  }
  return response.json()
}

export const fetchRangeGeoJson = async (apiBaseUrl, payload) => {
  const response = await fetch(`${apiBaseUrl}/regions/range-geojson`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error(`載入已選範圍 GeoJSON 失敗：${response.status}`)
  }

  return response.json()
}

export const fetchRangePick = async (apiBaseUrl, payload) => {
  const response = await fetch(`${apiBaseUrl}/regions/pick`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error(`範圍點選失敗：${response.status}`)
  }

  return response.json()
}
