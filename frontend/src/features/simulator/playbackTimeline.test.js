import { describe, expect, it } from 'vitest'
import { deriveSessionSegments, nearestFrame } from './playbackTimeline'

describe('nearestFrame', () => {
  it('returns ms unchanged when there are no frames', () => {
    expect(nearestFrame([], 1234)).toBe(1234)
  })

  it('returns the latest frame at or before ms', () => {
    const frames = [0, 100, 200, 300]
    expect(nearestFrame(frames, 250)).toBe(200)
    expect(nearestFrame(frames, 200)).toBe(200)
    expect(nearestFrame(frames, 999)).toBe(300)
  })

  it('clamps to the first frame when ms precedes all frames', () => {
    expect(nearestFrame([100, 200], 50)).toBe(100)
  })
})

describe('deriveSessionSegments', () => {
  it('returns an empty list for no frames', () => {
    expect(deriveSessionSegments([], 60, 4)).toEqual([])
  })

  it('keeps contiguous frames in a single session', () => {
    // interval 60s, gapFactor 4 -> gap threshold 240s = 240000ms.
    const frames = [0, 60000, 120000, 180000]
    expect(deriveSessionSegments(frames, 60, 4)).toEqual([{ from: 0, to: 180000 }])
  })

  it('splits into sessions when the gap exceeds the threshold', () => {
    const frames = [0, 60000, 1_000_000, 1_060_000]
    expect(deriveSessionSegments(frames, 60, 4)).toEqual([
      { from: 0, to: 60000 },
      { from: 1_000_000, to: 1_060_000 }
    ])
  })

  it('treats a single frame as a zero-length session', () => {
    expect(deriveSessionSegments([500], 60, 4)).toEqual([{ from: 500, to: 500 }])
  })
})
