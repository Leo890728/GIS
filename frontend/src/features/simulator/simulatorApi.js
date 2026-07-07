const toIso = (ms) => new Date(ms).toISOString()

const getJson = async (url, label) => {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`無法${label}：${response.status}`)
  }
  return response.json()
}

export const fetchHistoryRange = (apiBaseUrl, dataId) =>
  getJson(`${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/range`, '載入歷史時間範圍')

export const fetchHistoryFrames = (apiBaseUrl, dataId) =>
  getJson(`${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/frames`, '載入歷史影格')

export const fetchHistoryAt = (apiBaseUrl, dataId, ms) =>
  getJson(
    `${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/at?t=${encodeURIComponent(toIso(ms))}`,
    '載入歷史影格'
  )

export const fetchHistoryTrack = (apiBaseUrl, dataId, fromMs, toMs, key) => {
  const params = new URLSearchParams()
  if (fromMs != null) params.set('from', toIso(fromMs))
  if (toMs != null) params.set('to', toIso(toMs))
  // Restrict the backend build to this entity — without it the endpoint
  // OSRM-routes every entity in the dataset just to return one track.
  if (key != null) params.set('key', key)
  const query = params.toString()
  return getJson(
    `${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/track${query ? `?${query}` : ''}`,
    '載入歷史軌跡'
  )
}

const parseSseEvent = (raw) => {
  let event = 'message'
  const dataLines = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  return { event, data: dataLines.join('\n') }
}

/**
 * Streams road-smoothing track building via SSE, reporting per-entity progress.
 *
 * @returns the final track payload; rejects on error or abort.
 */
export const streamHistoryTrack = async (apiBaseUrl, dataId, fromMs, toMs, { onProgress, signal } = {}) => {
  const params = new URLSearchParams()
  if (fromMs != null) params.set('from', toIso(fromMs))
  if (toMs != null) params.set('to', toIso(toMs))
  const query = params.toString()
  const url = `${apiBaseUrl}/data/history/${encodeURIComponent(dataId)}/track/stream${query ? `?${query}` : ''}`

  const response = await fetch(url, { signal, headers: { Accept: 'text/event-stream' } })
  if (!response.ok || !response.body) {
    throw new Error(`串流歷史軌跡失敗：${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  // The final `result` event carries the whole track payload in ONE SSE event
  // (tens of MB for large datasets). Appending every network chunk to a single
  // string and re-scanning it from index 0 made completion quadratic — the UI
  // froze right after progress hit 100%. Buffer the pieces in an array instead
  // and only join + scan when the incoming piece (plus the previous boundary
  // char) actually contains an event separator.
  let parts = []
  let result = null
  let streamError = null
  // The backend streams one `track` event per entity (bounded memory server
  // side); the final `result` event only carries metadata. A `result` that
  // still embeds `tracks` (older backend) wins over the collected list.
  const collectedTracks = []

  const processEvents = (text) => {
    let rest = text
    let sep
    while ((sep = rest.indexOf('\n\n')) >= 0) {
      const { event, data } = parseSseEvent(rest.slice(0, sep))
      rest = rest.slice(sep + 2)
      if (!data) continue
      const payload = JSON.parse(data)
      if (event === 'progress') onProgress?.(payload)
      else if (event === 'track') collectedTracks.push(payload)
      else if (event === 'result') result = payload
      else if (event === 'error') streamError = new Error(payload.message || '串流錯誤')
    }
    return rest
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const piece = decoder.decode(value, { stream: true })
    if (!piece) continue
    const boundary = parts.length ? parts[parts.length - 1].slice(-1) : ''
    if (!(boundary + piece).includes('\n\n')) {
      parts.push(piece)
      continue
    }
    const rest = processEvents(parts.join('') + piece)
    parts = rest ? [rest] : []
  }

  if (streamError) throw streamError
  if (!result) throw new Error('軌跡串流結束但沒有回傳結果')
  if (!Array.isArray(result.tracks)) result = { ...result, tracks: collectedTracks }
  return result
}
