import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { useSmoothRenderer } from './useSmoothRenderer'
import { streamHistoryTrack } from './simulatorApi'

vi.mock('./simulatorApi', () => ({
  streamHistoryTrack: vi.fn()
}))

const makeState = () =>
  reactive({
    dataId: 'ds',
    from: 1000,
    to: 9000,
    playFrom: 2000,
    playTo: 5000,
    currentTime: 2000,
    loading: false,
    smooth: true,
    smoothing: false,
    smoothProgress: { done: 0, total: 0 },
    featureCount: 0,
    error: ''
  })

const makeRenderer = (state) =>
  useSmoothRenderer({
    apiBaseUrl: 'http://api',
    state,
    dataLayers: { setSimulatorGeoJson: vi.fn() },
    getLayerEntry: () => null,
    syncSelectedPosition: vi.fn()
  })

const trackPayload = () => ({
  tracks: [
    {
      key: 'A',
      properties: {},
      segments: [
        {
          path: [
            { tMs: 2000, lng: 120, lat: 24 },
            { tMs: 4000, lng: 120.01, lat: 24 }
          ]
        }
      ],
      samples: []
    }
  ]
})

describe('useSmoothRenderer window-scoped loading', () => {
  beforeEach(() => {
    vi.mocked(streamHistoryTrack).mockReset()
  })

  it('loads tracks for the active playback window, not the full range', async () => {
    const state = makeState()
    const renderer = makeRenderer(state)
    vi.mocked(streamHistoryTrack).mockResolvedValue(trackPayload())

    await renderer.loadTracks()

    const [, , from, to] = vi.mocked(streamHistoryTrack).mock.calls[0]
    expect(from).toBe(2000) // playFrom, not state.from
    expect(to).toBe(5000) // playTo, not state.to
    expect(renderer.hasTracks()).toBe(true)
  })

  it('coversWindow reflects the loaded window', async () => {
    const state = makeState()
    const renderer = makeRenderer(state)
    vi.mocked(streamHistoryTrack).mockResolvedValue(trackPayload())

    expect(renderer.coversWindow(2000, 5000)).toBe(false) // nothing loaded yet
    await renderer.loadTracks()

    expect(renderer.coversWindow(2000, 5000)).toBe(true)
    expect(renderer.coversWindow(2500, 4000)).toBe(true) // narrower window reuses
    expect(renderer.coversWindow(1000, 5000)).toBe(false) // wider needs reload
    expect(renderer.coversWindow(2000, 9000)).toBe(false)
  })

  it('re-derives the truck heading from the smoothed path, keeping other props', async () => {
    const state = makeState()
    const setSimulatorGeoJson = vi.fn()
    const renderer = useSmoothRenderer({
      apiBaseUrl: 'http://api',
      state,
      dataLayers: { setSimulatorGeoJson },
      getLayerEntry: () => null, // pass-through: assert the pre-handler properties
      syncSelectedPosition: vi.fn()
    })
    // Track heads due east; the recorded direction (↓) disagrees with travel.
    vi.mocked(streamHistoryTrack).mockResolvedValue({
      tracks: [
        {
          key: 'A',
          properties: {},
          segments: [{ path: [{ tMs: 2000, lng: 120, lat: 24 }, { tMs: 4000, lng: 120.01, lat: 24 }] }],
          samples: [{ t: '1970-01-01T00:00:02.000Z', properties: { direct: '↓', cartype: 'N' } }]
        }
      ]
    })
    await renderer.loadTracks()

    renderer.renderSmooth(3000)
    const collection = setSimulatorGeoJson.mock.calls.at(-1)[0]
    const props = collection.features[0].properties
    expect(props.direct).toBe('→') // overridden to the eastbound heading
    expect(props.cartype).toBe('N') // untouched
  })

  it('leaves features without a recorded direction untouched', async () => {
    const state = makeState()
    const setSimulatorGeoJson = vi.fn()
    const renderer = useSmoothRenderer({
      apiBaseUrl: 'http://api',
      state,
      dataLayers: { setSimulatorGeoJson },
      getLayerEntry: () => null,
      syncSelectedPosition: vi.fn()
    })
    vi.mocked(streamHistoryTrack).mockResolvedValue(trackPayload()) // samples: []
    await renderer.loadTracks()

    renderer.renderSmooth(3000)
    const collection = setSimulatorGeoJson.mock.calls.at(-1)[0]
    expect(collection.features[0].properties.direct).toBeUndefined()
  })

  it('disable() clears every smooth flag and the loaded tracks in one place', async () => {
    const state = makeState()
    const renderer = makeRenderer(state)
    vi.mocked(streamHistoryTrack).mockResolvedValue(trackPayload())
    await renderer.loadTracks()
    state.smoothing = true
    state.smoothProgress = { done: 3, total: 5 }

    renderer.disable()

    expect(state.smooth).toBe(false)
    expect(state.smoothing).toBe(false)
    expect(state.smoothProgress).toEqual({ done: 0, total: 0 })
    expect(renderer.hasTracks()).toBe(false)
    expect(renderer.coversWindow(2000, 5000)).toBe(false)
  })
})
