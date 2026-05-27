export const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })

export const fetchDataPoints = async (apiBaseUrl, payload = {}, endpoint = '/data/query') => {
  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error(`Failed to query data points: ${response.status}`)
  }

  return response.json()
}

export const fetchDataAggregate = async (apiBaseUrl, payload = {}, endpoint = '/data/aggregate') => {
  const response = await fetch(`${apiBaseUrl}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error(`Failed to aggregate data points: ${response.status}`)
  }

  return response.json()
}
