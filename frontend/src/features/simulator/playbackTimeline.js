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

// True when two epoch-ms instants fall on the same local calendar day.
const sameLocalDay = (a, b) => {
  const da = new Date(a)
  const db = new Date(b)
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  )
}

// Group ascending capture timestamps into one [{ from, to }] session per local
// calendar day. Each session spans that day's first to last frame; intra-day
// recording pauses are absorbed so the recording unit is a whole day.
export const deriveSessionSegments = (frames) => {
  if (!frames.length) return []
  const segments = []
  let from = frames[0]
  let prev = frames[0]
  for (let i = 1; i < frames.length; i += 1) {
    if (!sameLocalDay(frames[i], prev)) {
      segments.push({ from, to: prev })
      from = frames[i]
    }
    prev = frames[i]
  }
  segments.push({ from, to: prev })
  return segments
}
