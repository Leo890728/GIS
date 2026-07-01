export const fetchRangeTree = async (apiBaseUrl) => {
  const response = await fetch(`${apiBaseUrl}/ranges/tree`)
  if (!response.ok) {
    throw new Error(`載入範圍樹失敗：${response.status}`)
  }
  return response.json()
}

export const fetchVillageStatZoneRanges = async (apiBaseUrl, villageCode) => {
  const response = await fetch(`${apiBaseUrl}/ranges/village/${encodeURIComponent(villageCode)}/stat-zones`)
  if (!response.ok) {
    throw new Error(`載入村里統計區失敗：${response.status}`)
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
