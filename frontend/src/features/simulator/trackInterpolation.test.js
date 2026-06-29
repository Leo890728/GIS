import { describe, expect, it } from 'vitest'
import {
  activePropertiesAt,
  interpolateInPath,
  interpolateSegmentsAt,
  normalizeTrackSegments,
  segmentsToEndpointsGeoJson,
  segmentsToLineGeoJson,
  trackTimeBounds,
  traveledCoords
} from './trackInterpolation'

const pt = (tMs, lng, lat) => ({ tMs, lng, lat })

describe('interpolateInPath', () => {
  const path = [pt(0, 0, 0), pt(100, 10, 0), pt(200, 10, 10)]

  it('returns null for an empty path', () => {
    expect(interpolateInPath([], 50)).toBeNull()
  })

  it('clamps to the first point before the path starts', () => {
    expect(interpolateInPath(path, -10)).toEqual([0, 0])
  })

  it('clamps to the last point after the path ends', () => {
    expect(interpolateInPath(path, 999)).toEqual([10, 10])
  })

  it('linearly interpolates within a segment', () => {
    expect(interpolateInPath(path, 50)).toEqual([5, 0])
    expect(interpolateInPath(path, 150)).toEqual([10, 5])
  })

  it('returns the segment start when the span is zero', () => {
    expect(interpolateInPath([pt(100, 1, 2), pt(100, 9, 9)], 100)).toEqual([1, 2])
  })
})

describe('trackTimeBounds', () => {
  it('returns null for empty/missing segments', () => {
    expect(trackTimeBounds([])).toBeNull()
    expect(trackTimeBounds(null)).toBeNull()
  })

  it('spans the first and last vertex across all segments', () => {
    const segments = [
      { path: [pt(100, 0, 0), pt(200, 1, 0)] },
      { path: [pt(500, 2, 0), pt(900, 3, 0)] }
    ]
    expect(trackTimeBounds(segments)).toEqual([100, 900])
  })
})

describe('interpolateSegmentsAt', () => {
  const segments = [
    { path: [pt(0, 0, 0), pt(100, 10, 0)] },
    { path: [pt(500, 20, 0), pt(600, 30, 0)] }
  ]

  it('returns null when there are no segments', () => {
    expect(interpolateSegmentsAt([], 50)).toBeNull()
  })

  it('clamps to the very first vertex before playback starts', () => {
    expect(interpolateSegmentsAt(segments, -1)).toEqual([0, 0])
  })

  it('interpolates inside a segment', () => {
    expect(interpolateSegmentsAt(segments, 50)).toEqual([5, 0])
  })

  it('holds the previous segment end during a recording gap', () => {
    // 300ms is between segment 0 (ends @100) and segment 1 (starts @500).
    expect(interpolateSegmentsAt(segments, 300)).toEqual([10, 0])
  })

  it('clamps to the final vertex past the end', () => {
    expect(interpolateSegmentsAt(segments, 9999)).toEqual([30, 0])
  })
})

describe('activePropertiesAt', () => {
  const samples = [
    { tMs: 0, properties: { speed: 1 } },
    { tMs: 100, properties: { speed: 2 } },
    { tMs: 200, properties: { speed: 3 } }
  ]

  it('returns an empty object when there are no samples', () => {
    expect(activePropertiesAt([], 50)).toEqual({})
    expect(activePropertiesAt(undefined, 50)).toEqual({})
  })

  it('picks the most recent sample at or before the instant (step, not lerp)', () => {
    expect(activePropertiesAt(samples, 150)).toEqual({ speed: 2 })
    expect(activePropertiesAt(samples, 200)).toEqual({ speed: 3 })
  })

  it('returns the first sample before any has elapsed', () => {
    expect(activePropertiesAt(samples, -10)).toEqual({ speed: 1 })
  })
})

describe('normalizeTrackSegments', () => {
  it('converts ISO `t` vertices to numeric `tMs`', () => {
    const iso = '2026-06-18T08:00:00.000Z'
    const out = normalizeTrackSegments({ segments: [{ path: [{ t: iso, lng: 1, lat: 2 }, { t: iso, lng: 3, lat: 4 }] }] })
    expect(out[0].path[0].tMs).toBe(new Date(iso).getTime())
    expect(out[0].path[0]).toEqual({ tMs: new Date(iso).getTime(), lng: 1, lat: 2 })
  })

  it('passes through numeric `tMs` vertices', () => {
    const out = normalizeTrackSegments({ segments: [{ path: [pt(10, 1, 2), pt(20, 3, 4)] }] })
    expect(out[0].path.map((p) => p.tMs)).toEqual([10, 20])
  })

  it('drops invalid-time vertices and resulting empty segments', () => {
    const out = normalizeTrackSegments({
      segments: [
        { path: [{ t: 'not-a-date', lng: 1, lat: 2 }] },
        { path: [pt(10, 5, 6)] }
      ]
    })
    expect(out).toHaveLength(1)
    expect(out[0].path).toEqual([pt(10, 5, 6)])
  })

  it('handles a missing/empty track', () => {
    expect(normalizeTrackSegments(null)).toEqual([])
    expect(normalizeTrackSegments({})).toEqual([])
  })
})

describe('segmentsToLineGeoJson', () => {
  it('emits one LineString feature per segment with >=2 points', () => {
    const fc = segmentsToLineGeoJson([{ path: [pt(0, 0, 0), pt(1, 1, 1)] }])
    expect(fc.type).toBe('FeatureCollection')
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].geometry).toEqual({ type: 'LineString', coordinates: [[0, 0], [1, 1]] })
  })

  it('skips single-point segments and returns null when nothing remains', () => {
    expect(segmentsToLineGeoJson([{ path: [pt(0, 0, 0)] }])).toBeNull()
  })
})

describe('segmentsToEndpointsGeoJson', () => {
  it('returns start/end markers across all segments', () => {
    const fc = segmentsToEndpointsGeoJson([
      { path: [pt(0, 0, 0), pt(1, 1, 1)] },
      { path: [pt(2, 2, 2), pt(3, 3, 3)] }
    ])
    expect(fc.features.map((f) => f.properties.role)).toEqual(['start', 'end'])
    expect(fc.features[0].geometry.coordinates).toEqual([0, 0])
    expect(fc.features[1].geometry.coordinates).toEqual([3, 3])
  })

  it('returns null with fewer than two vertices', () => {
    expect(segmentsToEndpointsGeoJson([{ path: [pt(0, 0, 0)] }])).toBeNull()
  })
})

describe('traveledCoords', () => {
  const path = [pt(0, 0, 0), pt(100, 10, 0), pt(200, 20, 0)]

  it('returns an empty array before the path starts', () => {
    expect(traveledCoords(path, 0)).toEqual([])
    expect(traveledCoords([pt(0, 0, 0)], 50)).toEqual([])
  })

  it('includes passed vertices plus an interpolated tip at the clock', () => {
    // At 150ms: full first leg + interpolated point halfway along the second leg.
    expect(traveledCoords(path, 150)).toEqual([[0, 0], [10, 0], [15, 0]])
  })

  it('includes every vertex once the clock passes the end', () => {
    expect(traveledCoords(path, 999)).toEqual([[0, 0], [10, 0], [20, 0]])
  })
})
