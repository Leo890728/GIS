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
    throw new Error(`資料點查詢失敗：${response.status}`)
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
    throw new Error(`資料點統計失敗：${response.status}`)
  }

  return response.json()
}
