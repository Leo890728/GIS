import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSimulator } from './useSimulator'

// The virtual clock's contracts (see useSimulator tick):
// - the map renders from the precise clock every rAF, but the reactive mirror
//   `state.currentTime` is only written ~10x/s during play;
// - pause() flushes the precise clock so paused reads are exact;
// - an external write to currentTime while playing becomes the new clock origin.

vi.mock('./simulatorApi', () => ({
  fetchHistoryFrames: vi.fn(),
  fetchHistoryRange: vi.fn(),
  fetchHistoryAt: vi.fn(),
  fetchHistoryTrack: vi.fn(),
  streamHistoryTrack: vi.fn()
}))

const dataLayersStub = () => ({
  getSimulatorCandidates: () => [],
  enterSimulator: () => ({}),
  exitSimulator: vi.fn(),
  setSimulatorGeoJson: vi.fn()
})

// Minimal solved-route payload: one truck, arrivals at +0s/+50s/+150s.
const routeResult = () => ({
  routes: [
    {
      vehicle_id: 'truck-1',
      duration_s: 150,
      stops: [
        { lng: 0, lat: 0, type: 'depot', name: 'S', load_kg: 0, legFromPrevDurationS: null },
        { lng: 0.001, lat: 0, type: 'pickup', name: 'P', load_kg: 10, legFromPrevDurationS: 50 },
        { lng: 0.002, lat: 0, type: 'depot', name: 'E', load_kg: 0, legFromPrevDurationS: 100 }
      ],
      geometry: { type: 'LineString', coordinates: [[0, 0], [0.001, 0], [0.002, 0]] }
    }
  ]
})

describe('useSimulator virtual clock (route-plan playback)', () => {
  let rafCallbacks

  const fireFrame = (nowReal) => {
    const callbacks = rafCallbacks
    rafCallbacks = []
    for (const cb of callbacks) cb(nowReal)
  }

  const startPlaying = () => {
    const sim = useSimulator('http://api', dataLayersStub())
    sim.startRouteSimulation(routeResult())
    const state = sim.simulatorState
    expect(state.playing).toBe(true)
    sim.setSimulatorSpeed(30)
    return { sim, state }
  }

  beforeEach(() => {
    rafCallbacks = []
    vi.stubGlobal('requestAnimationFrame', (cb) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    })
    vi.stubGlobal('cancelAnimationFrame', () => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('throttles reactive currentTime writes to ~10Hz while rendering every frame', () => {
    const { state } = startPlaying()
    const from = state.from

    fireFrame(1000) // first tick: establishes lastTickReal, writes (>=100ms since epoch 0)
    expect(state.currentTime).toBe(from)

    fireFrame(1016) // +16ms real: clock advances, mirror must NOT be written yet
    expect(state.currentTime).toBe(from)

    fireFrame(1050) // +50ms: still within the 100ms write window
    expect(state.currentTime).toBe(from)

    fireFrame(1116) // crosses 100ms since the last write -> mirror catches up
    expect(state.currentTime).toBe(from + 116 * 30)
  })

  it('pause() flushes the precise clock so paused reads are exact', () => {
    const { sim, state } = startPlaying()
    const from = state.from

    fireFrame(1000)
    fireFrame(1016)
    fireFrame(1048) // mirror still at `from`, precise clock at +48*30
    expect(state.currentTime).toBe(from)

    sim.toggleSimulatorPlay() // pause
    expect(state.playing).toBe(false)
    expect(state.currentTime).toBe(from + 48 * 30)
  })

  it('adopts an external currentTime write as the new clock origin', () => {
    const { state } = startPlaying()
    const from = state.from

    fireFrame(1000)
    fireFrame(1016)

    // External writer (a seek that didn't go through setTime).
    const seeked = from + 60_000
    state.currentTime = seeked

    fireFrame(1032) // resync: next = seeked + 16ms*speed
    fireFrame(1200) // crosses the write window -> mirror reflects the new origin
    expect(state.currentTime).toBe(seeked + (16 + 168) * 30)
  })

  it('stopSimulator tears the whole playback state down', () => {
    const { sim, state } = startPlaying()
    fireFrame(1000)
    fireFrame(1016)

    sim.stopSimulator()
    expect(state.active).toBe(false)
    expect(state.playing).toBe(false)
    expect(state.mode).toBe('history')
    expect(state.currentTime).toBeNull()
    expect(state.smooth).toBe(false)
    expect(state.smoothing).toBe(false)
    expect(sim.routeSimGeoJson.value.features).toEqual([])
  })
})
