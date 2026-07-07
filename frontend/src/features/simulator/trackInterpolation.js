// Pure geometry/time helpers for history-track playback. No Vue reactivity or
// network access lives here, so each function is deterministic and unit-testable
// in isolation. Paths/segments use vertices shaped `{ tMs, lng, lat }`.

// Greatest index `i` with `path[i].tMs <= ms` (0 when `ms` precedes the path).
// Paths are time-sorted, so binary search keeps the per-frame lookups O(log n)
// on the multi-thousand-vertex OSRM geometries instead of scanning from zero.
export const pathIndexAt = (path, ms) => {
  let lo = 0
  let hi = path.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1
    if (path[mid].tMs <= ms) lo = mid
    else hi = mid - 1
  }
  return lo
}

// Linearly interpolate a position within one timestamped path at instant `ms`.
// Clamps to the endpoints outside the path's time span.
export const interpolateInPath = (path, ms) => {
  if (!path.length) return null
  if (ms <= path[0].tMs) return [path[0].lng, path[0].lat]
  const last = path[path.length - 1]
  if (ms >= last.tMs) return [last.lng, last.lat]
  const i = pathIndexAt(path, ms)
  const a = path[i]
  const b = path[i + 1]
  const span = b.tMs - a.tMs
  const f = span > 0 ? (ms - a.tMs) / span : 0
  return [a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f]
}

// Segment-aware: interpolate within a segment; during a between-segment gap
// (a recording interruption) hold the last known position instead of sliding.
export const interpolateSegmentsAt = (segments, ms) => {
  if (!segments.length) return null
  const firstPt = segments[0].path[0]
  if (ms <= firstPt.tMs) return [firstPt.lng, firstPt.lat]
  for (let i = 0; i < segments.length; i += 1) {
    const seg = segments[i]
    const lastPt = seg.path[seg.path.length - 1]
    if (ms <= lastPt.tMs) {
      if (ms >= seg.path[0].tMs) return interpolateInPath(seg.path, ms)
      const prev = segments[i - 1].path // gap before this segment -> hold prev end
      const held = prev[prev.length - 1]
      return [held.lng, held.lat]
    }
  }
  const tail = segments[segments.length - 1].path
  const lp = tail[tail.length - 1]
  return [lp.lng, lp.lat]
}

// True when `ms` falls inside an actual recorded segment of the track (not in a
// between-segment recording gap, and not before its first / after its last
// capture). Used so smooth playback only shows an entity when it genuinely has
// data near `ms`, instead of holding it frozen at a stale position across gaps.
export const isWithinTrackSegment = (segments, ms) => {
  if (!segments) return false
  for (const seg of segments) {
    const path = seg.path
    if (!path || !path.length) continue
    if (ms >= path[0].tMs && ms <= path[path.length - 1].tMs) return true
  }
  return false
}

// The most recent sample's properties at instant `ms` (step function, not
// interpolated) for surfacing per-capture attributes during playback.
export const activePropertiesAt = (samples, ms) => {
  if (!samples || !samples.length) return {}
  return samples[pathIndexAt(samples, ms)].properties
}

// Cumulative planar distances (meters) per path vertex. Precomputed once per
// track so per-frame progress lookups stay O(log n).
export const pathCumulativeDistances = (path) => {
  const cumulative = new Array(path.length).fill(0)
  let total = 0
  for (let i = 1; i < path.length; i += 1) {
    const a = path[i - 1]
    const b = path[i]
    const midLatRad = (((a.lat + b.lat) / 2) * Math.PI) / 180
    const dx = (b.lng - a.lng) * Math.cos(midLatRad) * 111320
    const dy = (b.lat - a.lat) * 110540
    total += Math.hypot(dx, dy)
    cumulative[i] = total
  }
  return cumulative
}

// Fraction [0, 1] of the path's total length traveled at instant `ms`, using
// the cumulative distances from pathCumulativeDistances. Drives the MapLibre
// line-progress gradient split, so it must be distance- (not time-) based to
// line up with the geometry.
export const pathProgressAt = (path, cumulative, ms) => {
  if (!path || path.length < 2 || !cumulative) return 0
  const total = cumulative[cumulative.length - 1]
  if (!(total > 0)) return ms >= path[path.length - 1].tMs ? 1 : 0
  if (ms <= path[0].tMs) return 0
  if (ms >= path[path.length - 1].tMs) return 1
  const i = pathIndexAt(path, ms)
  const a = path[i]
  const b = path[i + 1]
  const span = b.tMs - a.tMs
  const f = span > 0 ? (ms - a.tMs) / span : 0
  return (cumulative[i] + (cumulative[i + 1] - cumulative[i]) * f) / total
}

// Count of sorted timestamps at or before `ms` (binary search).
export const countAtOrBefore = (sortedTimes, ms) => {
  let lo = 0
  let hi = sortedTimes.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sortedTimes[mid] <= ms) lo = mid + 1
    else hi = mid
  }
  return lo
}

const isTimeSorted = (path) => {
  for (let i = 1; i < path.length; i += 1) {
    if (path[i].tMs < path[i - 1].tMs) return false
  }
  return true
}

// Normalize a track's segments to [{ path: [{ tMs, lng, lat }] }]. Accepts both
// the raw /track payload (path vertices carry an ISO `t`) and already-loaded
// smooth tracks (vertices carry a numeric `tMs`).
export const normalizeTrackSegments = (track) =>
  (track?.segments || [])
    .map((seg) => {
      const path = (seg.path || [])
        .map((point) => ({
          tMs: Number.isFinite(point.tMs) ? point.tMs : new Date(point.t).getTime(),
          lng: point.lng,
          lat: point.lat
        }))
        .filter((point) => Number.isFinite(point.tMs))
      // pathIndexAt binary-searches by tMs, so paths MUST be time-sorted. The
      // backend emits them sorted; repair (stable sort) rather than render
      // garbage if a source ever violates that. Load-time only, O(n) check.
      if (!isTimeSorted(path)) path.sort((a, b) => a.tMs - b.tMs)
      return { path }
    })
    .filter((seg) => seg.path.length > 0)

// Normalize the raw /track stream payload into smooth-playback tracks:
// `{ key, properties, segments: [{ path: [{ tMs, lng, lat }] }], samples }`.
// Tracks with no usable segment are dropped.
export const normalizeSmoothTracks = (tracks) =>
  (tracks || [])
    .map((track) => ({
      key: track.key,
      properties: track.properties || {},
      segments: normalizeTrackSegments(track),
      samples: (track.samples || [])
        .map((sample) => ({ tMs: new Date(sample.t).getTime(), properties: sample.properties || {} }))
        .filter((sample) => Number.isFinite(sample.tMs))
    }))
    .filter((track) => track.segments.length > 0)

// Clip a smooth track's segments to the inclusive [lo, hi] time window so an
// already-loaded full-range track can back a windowed (session/day) overlay
// without a second OSRM fetch. Vertices are kept by `tMs`; empty segments drop.
export const clipTrackToWindow = (track, lo, hi) => {
  const from = Number(lo)
  const to = Number(hi)
  const bounded = Number.isFinite(from) && Number.isFinite(to)
  const segments = (track?.segments || [])
    .map((seg) => ({
      path: (seg.path || []).filter((point) => !bounded || (point.tMs >= from && point.tMs <= to))
    }))
    .filter((seg) => seg.path.length > 0)
  return { ...track, segments }
}

export const segmentsToLineGeoJson = (segments) => {
  const features = segments
    .map((seg) => seg.path.map((point) => [point.lng, point.lat]))
    .filter((coords) => coords.length >= 2)
    .map((coords) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } }))
  return features.length ? { type: 'FeatureCollection', features } : null
}

// Origin (start) and destination (end) markers for the whole trajectory.
export const segmentsToEndpointsGeoJson = (segments) => {
  const vertices = segments.flatMap((seg) => seg.path)
  if (vertices.length < 2) return null
  const start = vertices[0]
  const end = vertices[vertices.length - 1]
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', properties: { role: 'start' }, geometry: { type: 'Point', coordinates: [start.lng, start.lat] } },
      { type: 'Feature', properties: { role: 'end' }, geometry: { type: 'Point', coordinates: [end.lng, end.lat] } }
    ]
  }
}

// The portion of a path not yet traveled at instant `ms`, starting with an
// interpolated point at the exact clock position so the line begins right
// under the moving vehicle. Complements `traveledCoords`.
export const remainingCoords = (path, ms) => {
  if (path.length < 2) return []
  if (ms <= path[0].tMs) return path.map((point) => [point.lng, point.lat])
  if (ms >= path[path.length - 1].tMs) return []
  const i = pathIndexAt(path, ms)
  const a = path[i]
  const b = path[i + 1]
  const span = b.tMs - a.tMs
  const f = span > 0 ? (ms - a.tMs) / span : 0
  const coords = [[a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f]]
  for (let j = i + 1; j < path.length; j += 1) {
    coords.push([path[j].lng, path[j].lat])
  }
  return coords
}

// The portion of a path already traveled at instant `ms`, including an
// interpolated point at the exact clock position so the colored line ends right
// under the moving vehicle.
export const traveledCoords = (path, ms) => {
  if (path.length < 2 || ms <= path[0].tMs) return []
  const i = pathIndexAt(path, ms)
  const coords = []
  for (let j = 0; j <= i; j += 1) {
    coords.push([path[j].lng, path[j].lat])
  }
  if (i < path.length - 1) {
    const a = path[i]
    const b = path[i + 1]
    const span = b.tMs - a.tMs
    const f = span > 0 ? (ms - a.tMs) / span : 0
    coords.push([a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f])
  }
  return coords
}
