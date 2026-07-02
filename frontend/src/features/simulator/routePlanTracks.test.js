import { describe, expect, it } from 'vitest'
import { bearingToTruckIconSuffix, buildRoutePlanTracks, pathBearingAt } from './routePlanTracks'
import { remainingCoords, traveledCoords } from './trackInterpolation'

const BASE = 1_000_000

// Equator-aligned line: each 0.001 lng step is the same ground distance, so
// distance-proportional timing is easy to assert.
const geometry = {
  type: 'LineString',
  coordinates: [
    [0, 0],
    [0.001, 0],
    [0.002, 0],
    [0.003, 0]
  ]
}

const makeRoute = (overrides = {}) => ({
  vehicle_id: 'truck-1',
  duration_s: 150,
  geometry,
  stops: [
    { lng: 0, lat: 0, name: '起點', type: 'start', legFromPrevDurationS: 0 },
    { lng: 0.002, lat: 0, name: '收運點', type: 'pickup', legFromPrevDurationS: 100 },
    { lng: 0.003, lat: 0, name: '終點', type: 'end', legFromPrevDurationS: 50 }
  ],
  ...overrides
})

describe('buildRoutePlanTracks', () => {
  it('returns no tracks for a missing or empty result', () => {
    expect(buildRoutePlanTracks(null, BASE).tracks).toEqual([])
    expect(buildRoutePlanTracks({ routes: [] }, BASE).tracks).toEqual([])
  })

  it('pins stop arrivals to leg durations and spreads vertices by distance', () => {
    const { tracks, fromMs, toMs, frames } = buildRoutePlanTracks({ routes: [makeRoute()] }, BASE)
    expect(tracks).toHaveLength(1)
    const path = tracks[0].segments[0].path
    expect(path.map((p) => p.tMs)).toEqual([BASE, BASE + 50_000, BASE + 100_000, BASE + 150_000])
    expect(path.map((p) => p.lng)).toEqual([0, 0.001, 0.002, 0.003])
    expect(fromMs).toBe(BASE)
    expect(toMs).toBe(BASE + 150_000)
    // Frames are the stop arrival instants, for stop-to-stop stepping.
    expect(frames).toEqual([BASE, BASE + 100_000, BASE + 150_000])
  })

  it('falls back to constant speed along the geometry when legs are missing', () => {
    const route = makeRoute({
      stops: [
        { lng: 0, lat: 0, type: 'start' },
        { lng: 0.003, lat: 0, type: 'end', legFromPrevDurationS: null }
      ]
    })
    const { tracks } = buildRoutePlanTracks({ routes: [route] }, BASE)
    expect(tracks).toHaveLength(1)
    const path = tracks[0].segments[0].path
    expect(path.map((p) => p.tMs)).toEqual([BASE, BASE + 50_000, BASE + 100_000, BASE + 150_000])
  })

  it('uses straight lines between stops when there is no geometry', () => {
    const route = makeRoute({ geometry: null, duration_s: null })
    const { tracks } = buildRoutePlanTracks({ routes: [route] }, BASE)
    expect(tracks).toHaveLength(1)
    const path = tracks[0].segments[0].path
    expect(path).toHaveLength(3)
    expect(path[1]).toMatchObject({ tMs: BASE + 100_000, lng: 0.002 })
  })

  it('splits a timed path into traveled and remaining halves at the clock', () => {
    const { tracks } = buildRoutePlanTracks({ routes: [makeRoute()] }, BASE)
    const path = tracks[0].segments[0].path

    // Before departure: nothing traveled, everything remaining.
    expect(traveledCoords(path, BASE - 1)).toEqual([])
    expect(remainingCoords(path, BASE - 1)).toHaveLength(path.length)

    // Mid-leg: both halves meet at the interpolated vehicle position.
    const traveled = traveledCoords(path, BASE + 75_000)
    const remaining = remainingCoords(path, BASE + 75_000)
    expect(traveled[traveled.length - 1]).toEqual(remaining[0])
    expect(traveled[traveled.length - 1][0]).toBeCloseTo(0.0015, 10)

    // After arrival: everything traveled, nothing remaining.
    expect(remainingCoords(path, BASE + 150_000)).toEqual([])
  })

  it('derives compass bearing along the active leg and holds through dwells', () => {
    const { tracks } = buildRoutePlanTracks({ routes: [makeRoute()] }, BASE)
    const path = tracks[0].segments[0].path
    // The whole demo route heads due east.
    expect(pathBearingAt(path, BASE + 25_000)).toBeCloseTo(90, 5)
    expect(pathBearingAt(path, BASE + 125_000)).toBeCloseTo(90, 5)

    const northbound = [
      { tMs: 0, lng: 0, lat: 0 },
      { tMs: 1000, lng: 0, lat: 0.001 },
      // dwell at the stop: heading keeps the approach direction
      { tMs: 2000, lng: 0, lat: 0.001 }
    ]
    expect(pathBearingAt(northbound, 500)).toBeCloseTo(0, 5)
    expect(pathBearingAt(northbound, 1500)).toBeCloseTo(0, 5)
  })

  it('maps bearings onto the eight tcg-v2 truck sprites', () => {
    expect(bearingToTruckIconSuffix(0)).toBe('o01') // ↑
    expect(bearingToTruckIconSuffix(45)).toBe('o02') // ↗
    expect(bearingToTruckIconSuffix(90)).toBe('o03') // →
    expect(bearingToTruckIconSuffix(180)).toBe('o05') // ↓
    expect(bearingToTruckIconSuffix(270)).toBe('o07') // ←
    expect(bearingToTruckIconSuffix(315)).toBe('o08') // ↖
    expect(bearingToTruckIconSuffix(359)).toBe('o01') // wraps back to ↑
    expect(bearingToTruckIconSuffix(-90)).toBe('o07') // negative input normalizes
  })

  it('drops routes that cannot be timed and colors vehicles by index', () => {
    const dead = makeRoute({ geometry: null, duration_s: null, stops: [{ lng: 0, lat: 0 }] })
    const colors = ['#111111', '#222222']
    const { tracks } = buildRoutePlanTracks(
      { routes: [makeRoute(), dead, makeRoute({ vehicle_id: 'truck-2' })] },
      BASE,
      (index) => colors[index % colors.length]
    )
    expect(tracks.map((t) => t.key)).toEqual(['truck-1', 'truck-2'])
    expect(tracks[0].properties.vehicleColor).toBe('#111111')
    // Color follows the route's index in the result (matches the route lines).
    expect(tracks[1].properties.vehicleColor).toBe('#111111')
  })
})
