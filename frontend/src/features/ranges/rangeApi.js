export const fetchRangeTree = async (apiBaseUrl) => {
  const response = await fetch(`${apiBaseUrl}/ranges/tree`)
  if (!response.ok) {
    throw new Error(`Failed to load ranges tree: ${response.status}`)
  }
  return response.json()
}

export const fetchVillageStatZoneRanges = async (apiBaseUrl, villageCode) => {
  const response = await fetch(`${apiBaseUrl}/ranges/village/${encodeURIComponent(villageCode)}/stat-zones`)
  if (!response.ok) {
    throw new Error(`Failed to load village stat zones: ${response.status}`)
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
    throw new Error(`Failed to load selected range GeoJSON: ${response.status}`)
  }

  return response.json()
}
