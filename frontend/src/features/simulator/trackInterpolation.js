// Pure geometry/time helpers for history-track playback. No Vue reactivity or
// network access lives here, so each function is deterministic and unit-testable
// in isolation. Paths/segments use vertices shaped `{ tMs, lng, lat }`.

// Linearly interpolate a position within one timestamped path at instant `ms`.
// Clamps to the endpoints outside the path's time span.
export const interpolateInPath = (path, ms) => {
  if (!path.length) return null
  if (ms <= path[0].tMs) return [path[0].lng, path[0].lat]
  const last = path[path.length - 1]
  if (ms >= last.tMs) return [last.lng, last.lat]
  for (let i = 0; i < path.length - 1; i += 1) {
    const a = path[i]
    const b = path[i + 1]
    if (ms >= a.tMs && ms <= b.tMs) {
      const span = b.tMs - a.tMs
      const f = span > 0 ? (ms - a.tMs) / span : 0
      return [a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f]
    }
  }
  return [last.lng, last.lat]
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
  let chosen = samples[0].properties
  for (const sample of samples) {
    if (sample.tMs <= ms) chosen = sample.properties
    else break
  }
  return chosen
}

// Normalize a track's segments to [{ path: [{ tMs, lng, lat }] }]. Accepts both
// the raw /track payload (path vertices carry an ISO `t`) and already-loaded
// smooth tracks (vertices carry a numeric `tMs`).
export const normalizeTrackSegments = (track) =>
  (track?.segments || [])
    .map((seg) => ({
      path: (seg.path || [])
        .map((point) => ({
          tMs: Number.isFinite(point.tMs) ? point.tMs : new Date(point.t).getTime(),
          lng: point.lng,
          lat: point.lat
        }))
        .filter((point) => Number.isFinite(point.tMs))
    }))
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

// The portion of a path already traveled at instant `ms`, including an
// interpolated point at the exact clock position so the colored line ends right
// under the moving vehicle.
export const traveledCoords = (path, ms) => {
  if (path.length < 2 || ms <= path[0].tMs) return []
  const coords = []
  for (let i = 0; i < path.length; i += 1) {
    if (path[i].tMs <= ms) {
      coords.push([path[i].lng, path[i].lat])
    } else {
      const a = path[i - 1]
      const b = path[i]
      const span = b.tMs - a.tMs
      const f = span > 0 ? (ms - a.tMs) / span : 0
      coords.push([a.lng + (b.lng - a.lng) * f, a.lat + (b.lat - a.lat) * f])
      break
    }
  }
  return coords
}
