import { describe, expect, it } from 'vitest'
import { deriveSessionSegments, nearestFrame, toMs } from './playbackTimeline'

describe('toMs', () => {
  it('returns null for falsy or invalid input', () => {
    expect(toMs(null)).toBeNull()
    expect(toMs('')).toBeNull()
    expect(toMs('not-a-date')).toBeNull()
  })

  it('parses an ISO timestamp to epoch ms', () => {
    const iso = '2026-06-18T08:00:00.000Z'
    expect(toMs(iso)).toBe(new Date(iso).getTime())
  })
})

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
    expect(deriveSessionSegments([])).toEqual([])
  })

  it('keeps a single day in one session regardless of intra-day pauses', () => {
    // Three frames on the same local day, with a multi-hour gap between them.
    const a = new Date(2026, 5, 18, 6, 0).getTime()
    const b = new Date(2026, 5, 18, 12, 0).getTime()
    const c = new Date(2026, 5, 18, 20, 0).getTime()
    expect(deriveSessionSegments([a, b, c])).toEqual([{ from: a, to: c }])
  })

  it('starts a new session at each calendar-day boundary', () => {
    const d1a = new Date(2026, 5, 18, 9, 0).getTime()
    const d1b = new Date(2026, 5, 18, 23, 0).getTime()
    const d2a = new Date(2026, 5, 19, 5, 0).getTime()
    const d2b = new Date(2026, 5, 19, 9, 0).getTime()
    expect(deriveSessionSegments([d1a, d1b, d2a, d2b])).toEqual([
      { from: d1a, to: d1b },
      { from: d2a, to: d2b }
    ])
  })

  it('treats a single frame as a zero-length session', () => {
    expect(deriveSessionSegments([500])).toEqual([{ from: 500, to: 500 }])
  })
})
