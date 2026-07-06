// Convert a solved garbage-route (VRP) result into simulator playback tracks.
// Pure module: no Vue reactivity or I/O, mirrors the smooth-track shape
// `{ key, properties, segments: [{ path: [{ tMs, lng, lat }] }], samples }`
// so the existing interpolation helpers drive the animation as-is.

import { pathIndexAt } from './trackInterpolation'

// Planar approximation is fine at city scale (matches services elsewhere).
const distanceM = (a, b) => {
  const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180
  const dx = (b[0] - a[0]) * Math.cos(midLatRad) * 111320
  const dy = (b[1] - a[1]) * 110540
  return Math.hypot(dx, dy)
}

const isCoord = (value) =>
  Array.isArray(value) && Number.isFinite(value[0]) && Number.isFinite(value[1])

// Cumulative arrival offsets (seconds) per stop from the per-leg durations the
// solver reports. Null when any leg is missing — callers fall back to
// distributing the route's total duration by distance.
const stopArrivalOffsets = (stops) => {
  const offsets = [0]
  for (let i = 1; i < stops.length; i += 1) {
    const leg = Number(stops[i].legFromPrevDurationS)
    if (!Number.isFinite(leg) || leg < 0) return null
    offsets.push(offsets[i - 1] + leg)
  }
  return offsets
}

// Match each stop to a vertex of the route geometry, walking forward only so
// revisited roads (e.g. out-and-back to a disposal site) keep stop order.
const matchStopsToVertices = (coords, stops) => {
  const indices = []
  let searchFrom = 0
  for (const stop of stops) {
    let best = searchFrom
    let bestDistance = Infinity
    for (let i = searchFrom; i < coords.length; i += 1) {
      const d = distanceM([stop.lng, stop.lat], coords[i])
      if (d < bestDistance) {
        bestDistance = d
        best = i
      }
    }
    indices.push(best)
    searchFrom = best
  }
  return indices
}

// Timestamp the geometry vertices leg by leg: each vertex between two stops
// gets a time linear in road distance between the stops' arrival instants.
const timedPathFromGeometry = (coords, stops, arrivalOffsets, baseMs) => {
  const stopIndices = matchStopsToVertices(coords, stops)
  const path = [
    { tMs: baseMs + arrivalOffsets[0] * 1000, lng: coords[stopIndices[0]][0], lat: coords[stopIndices[0]][1] }
  ]
  for (let k = 1; k < stops.length; k += 1) {
    const i0 = stopIndices[k - 1]
    const i1 = stopIndices[k]
    const t0 = arrivalOffsets[k - 1]
    const t1 = arrivalOffsets[k]
    if (i1 <= i0) {
      // Same vertex (aggregated stops that snapped together): dwell in place.
      path.push({ tMs: baseMs + t1 * 1000, lng: coords[i1][0], lat: coords[i1][1] })
      continue
    }
    let total = 0
    const legDistances = []
    for (let i = i0; i < i1; i += 1) {
      total += distanceM(coords[i], coords[i + 1])
      legDistances.push(total)
    }
    for (let i = i0 + 1; i <= i1; i += 1) {
      const fraction = total > 0 ? legDistances[i - i0 - 1] / total : 1
      path.push({
        tMs: baseMs + (t0 + (t1 - t0) * fraction) * 1000,
        lng: coords[i][0],
        lat: coords[i][1]
      })
    }
  }
  return path
}

// Constant-speed fallback along the geometry when per-leg durations are absent.
const timedPathConstantSpeed = (coords, durationS, baseMs) => {
  let total = 0
  const cumulative = [0]
  for (let i = 0; i < coords.length - 1; i += 1) {
    total += distanceM(coords[i], coords[i + 1])
    cumulative.push(total)
  }
  if (total <= 0) return null
  return coords.map((coord, i) => ({
    tMs: baseMs + durationS * (cumulative[i] / total) * 1000,
    lng: coord[0],
    lat: coord[1]
  }))
}

const buildVehicleTrack = (route, vehicleColor, baseMs) => {
  const stops = (route?.stops || []).filter(
    (stop) => Number.isFinite(stop?.lng) && Number.isFinite(stop?.lat)
  )
  const coords = route?.geometry?.type === 'LineString' ? (route.geometry.coordinates || []).filter(isCoord) : []
  const durationS = Number(route?.duration_s)
  const arrivalOffsets = stops.length >= 2 ? stopArrivalOffsets(stops) : null

  let path = null
  if (coords.length >= 2 && arrivalOffsets && arrivalOffsets[arrivalOffsets.length - 1] > 0) {
    path = timedPathFromGeometry(coords, stops, arrivalOffsets, baseMs)
  } else if (coords.length >= 2 && Number.isFinite(durationS) && durationS > 0) {
    path = timedPathConstantSpeed(coords, durationS, baseMs)
  } else if (arrivalOffsets && arrivalOffsets[arrivalOffsets.length - 1] > 0) {
    // No road geometry at all: straight lines between stops.
    path = stops.map((stop, k) => ({
      tMs: baseMs + arrivalOffsets[k] * 1000,
      lng: stop.lng,
      lat: stop.lat
    }))
  }
  if (!path || path.length < 2) return null

  const samples = arrivalOffsets
    ? stops.map((stop, k) => ({
        tMs: baseMs + arrivalOffsets[k] * 1000,
        properties: {
          vehicleId: route.vehicle_id,
          vehicleColor,
          stopName: stop.name || stop.location_id || '',
          stopType: stop.type || '',
          loadKg: stop.load_kg || 0,
          instructions: Array.isArray(stop.instructions) ? stop.instructions : []
        }
      }))
    : []

  return {
    key: String(route.vehicle_id ?? ''),
    properties: { vehicleId: route.vehicle_id, vehicleColor },
    segments: [{ path }],
    samples,
    stopTimesMs: samples.map((sample) => sample.tMs)
  }
}

// Compass bearing (0° = north, clockwise) of the leg the clock is inside,
// expanding across dwell legs (repeated coordinates) so the heading holds
// steady while a vehicle services a stop.
export const pathBearingAt = (path, ms) => {
  if (!Array.isArray(path) || path.length < 2) return 0
  const i = Math.min(pathIndexAt(path, ms), path.length - 2)
  let from = path[i]
  let to = path[i + 1]
  let forward = i + 1
  while (forward < path.length - 1 && to.lng === from.lng && to.lat === from.lat) {
    forward += 1
    to = path[forward]
  }
  let backward = i
  while (backward > 0 && to.lng === from.lng && to.lat === from.lat) {
    backward -= 1
    from = path[backward]
  }
  const midLatRad = (((from.lat + to.lat) / 2) * Math.PI) / 180
  const dx = (to.lng - from.lng) * Math.cos(midLatRad)
  const dy = to.lat - from.lat
  if (dx === 0 && dy === 0) return 0
  return (Math.atan2(dx, dy) * (180 / Math.PI) + 360) % 360
}

// Map a bearing onto the 8-direction truck sprite suffix used by the tcg-v2
// icon set: o01 = ↑ (north), then clockwise every 45° through o08 = ↖.
export const bearingToTruckIconSuffix = (bearing) => {
  const normalized = ((Number(bearing) % 360) + 360) % 360
  const index = Math.round(normalized / 45) % 8
  return `o0${index + 1}`
}

// Heat points for the stop-heatmap view: one feature per pickup stop, weighted
// by the garbage collected there (the load delta from the previous stop, since
// route stops report cumulative load). `stopIndex` matches the stop layer so
// served stops can be zeroed out during playback.
export const buildRouteHeatGeoJson = (routeResult) => {
  const features = []
  for (const route of routeResult?.routes || []) {
    let previousLoadKg = 0
    for (const [stopIndex, stop] of (route?.stops || []).entries()) {
      const loadKg = Number(stop?.load_kg) || 0
      if (stop?.type === 'pickup' && Number.isFinite(stop?.lng) && Number.isFinite(stop?.lat)) {
        const demandKg = Math.max(0, loadKg - previousLoadKg)
        if (demandKg > 0) {
          features.push({
            type: 'Feature',
            properties: { vehicleId: route.vehicle_id, stopIndex, demandKg },
            geometry: { type: 'Point', coordinates: [stop.lng, stop.lat] }
          })
        }
      }
      previousLoadKg = loadKg
    }
  }
  return { type: 'FeatureCollection', features }
}

/**
 * Build simulator tracks for every vehicle route in a solved VRP result.
 * All vehicles depart together at `baseMs`.
 * @returns {{ tracks: Array, fromMs: number, toMs: number, frames: number[] }}
 */
export const buildRoutePlanTracks = (routeResult, baseMs, getColor = () => '#f97316') => {
  const tracks = []
  const frameSet = new Set()
  let toMs = baseMs
  for (const [index, route] of (routeResult?.routes || []).entries()) {
    const track = buildVehicleTrack(route, getColor(index), baseMs)
    if (!track) continue
    tracks.push(track)
    for (const tMs of track.stopTimesMs) frameSet.add(tMs)
    const path = track.segments[0].path
    toMs = Math.max(toMs, path[path.length - 1].tMs)
  }
  if (!frameSet.size) {
    frameSet.add(baseMs)
    frameSet.add(toMs)
  }
  return {
    tracks,
    fromMs: baseMs,
    toMs,
    frames: [...frameSet].sort((a, b) => a - b)
  }
}
