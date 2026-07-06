import { describe, expect, it } from 'vitest'
import { normalizeSmoothTracks } from './trackInterpolation'

describe('normalizeSmoothTracks', () => {
  const isoA = '2026-06-18T08:00:00.000Z'
  const isoB = '2026-06-18T08:01:00.000Z'

  it('returns an empty array for missing input', () => {
    expect(normalizeSmoothTracks(null)).toEqual([])
    expect(normalizeSmoothTracks(undefined)).toEqual([])
  })

  it('shapes segments and samples with numeric tMs', () => {
    const tracks = [
      {
        key: 'A',
        properties: { color: 'red' },
        segments: [{ path: [{ t: isoA, lng: 1, lat: 2 }, { t: isoB, lng: 3, lat: 4 }] }],
        samples: [{ t: isoA, properties: { speed: 5 } }]
      }
    ]
    const [track] = normalizeSmoothTracks(tracks)
    expect(track.key).toBe('A')
    expect(track.properties).toEqual({ color: 'red' })
    expect(track.segments[0].path).toEqual([
      { tMs: new Date(isoA).getTime(), lng: 1, lat: 2 },
      { tMs: new Date(isoB).getTime(), lng: 3, lat: 4 }
    ])
    expect(track.samples).toEqual([{ tMs: new Date(isoA).getTime(), properties: { speed: 5 } }])
  })

  it('drops tracks that have no usable segment', () => {
    const tracks = [
      { key: 'empty', segments: [{ path: [{ t: isoA, lng: 1, lat: 2 }] }], samples: [] }
    ]
    // single-vertex path survives normalizeTrackSegments, so segment count is 1;
    // verify instead that a track with only invalid vertices is dropped.
    const dropped = normalizeSmoothTracks([
      { key: 'bad', segments: [{ path: [{ t: 'nope', lng: 1, lat: 2 }] }], samples: [] }
    ])
    expect(dropped).toEqual([])
    expect(normalizeSmoothTracks(tracks)).toHaveLength(1)
  })

  it('repairs a path that violates the time-sorted invariant', () => {
    // pathIndexAt binary-searches by tMs — an unsorted source must be fixed at
    // load time instead of producing garbage interpolation.
    const [track] = normalizeSmoothTracks([
      {
        key: 'C',
        segments: [
          {
            path: [
              { tMs: 3000, lng: 3, lat: 0 },
              { tMs: 1000, lng: 1, lat: 0 },
              { tMs: 2000, lng: 2, lat: 0 }
            ]
          }
        ],
        samples: []
      }
    ])
    expect(track.segments[0].path.map((p) => p.tMs)).toEqual([1000, 2000, 3000])
  })

  it('defaults missing properties/samples to empty', () => {
    const [track] = normalizeSmoothTracks([
      { key: 'B', segments: [{ path: [{ t: isoA, lng: 1, lat: 2 }, { t: isoB, lng: 3, lat: 4 }] }] }
    ])
    expect(track.properties).toEqual({})
    expect(track.samples).toEqual([])
  })
})
