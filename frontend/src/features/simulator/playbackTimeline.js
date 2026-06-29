// Pure timeline helpers for history playback: frame lookup and splitting the
// capture timeline into recording sessions. No Vue reactivity or I/O.

// Parse an ISO timestamp to epoch milliseconds, or null when absent/invalid.
export const toMs = (iso) => {
  if (!iso) return null
  const ms = new Date(iso).getTime()
  return Number.isFinite(ms) ? ms : null
}

// The latest frame at or before `ms` (frames must be ascending). Returns `ms`
// unchanged when there are no frames.
export const nearestFrame = (frames, ms) => {
  if (!frames.length) return ms
  let lo = frames[0]
  for (const frame of frames) {
    if (frame <= ms) lo = frame
    else break
  }
  return lo
}

// Split ascending capture timestamps into [{ from, to }] sessions, breaking
// whenever the gap between consecutive frames exceeds `gapFactor` poll cycles.
export const deriveSessionSegments = (frames, intervalSeconds, gapFactor) => {
  if (!frames.length) return []
  const gapMs = (Number(intervalSeconds) || 60) * 1000 * gapFactor
  const segments = []
  let from = frames[0]
  let prev = frames[0]
  for (let i = 1; i < frames.length; i += 1) {
    if (frames[i] - prev > gapMs) {
      segments.push({ from, to: prev })
      from = frames[i]
    }
    prev = frames[i]
  }
  segments.push({ from, to: prev })
  return segments
}
