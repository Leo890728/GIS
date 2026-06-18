const toIso = (ms) => new Date(ms).toISOString()

const getJson = async (url, label) => {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to ${label}: ${response.status}`)
  }
  return response.json()
}

export const fetchHistoryRange = (apiBaseUrl, dataId) =>
  getJson(`${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/range`, 'load history range')

export const fetchHistoryFrames = (apiBaseUrl, dataId) =>
  getJson(`${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/frames`, 'load history frames')

export const fetchHistoryAt = (apiBaseUrl, dataId, ms) =>
  getJson(
    `${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/at?t=${encodeURIComponent(toIso(ms))}`,
    'load history frame'
  )

export const fetchHistoryTrack = (apiBaseUrl, dataId, fromMs, toMs) => {
  const params = new URLSearchParams()
  if (fromMs != null) params.set('from', toIso(fromMs))
  if (toMs != null) params.set('to', toIso(toMs))
  const query = params.toString()
  return getJson(
    `${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/track${query ? `?${query}` : ''}`,
    'load history tracks'
  )
}
