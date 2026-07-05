import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamHistoryTrack } from './simulatorApi'

const encoder = new TextEncoder()

// Fake fetch returning an SSE body that yields `chunks` (strings) one read at
// a time, mirroring how network chunks slice the stream at arbitrary points.
const stubFetchWithChunks = (chunks) => {
  const queue = chunks.map((chunk) => encoder.encode(chunk))
  let index = 0
  vi.stubGlobal('fetch', async () => ({
    ok: true,
    body: {
      getReader: () => ({
        read: async () =>
          index < queue.length ? { done: false, value: queue[index++] } : { done: true, value: undefined }
      })
    }
  }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamHistoryTrack', () => {
  it('parses progress events and a result split across many chunks', async () => {
    // A large single-event payload arriving in many pieces is the regression
    // case: it previously re-scanned the whole accumulated buffer per chunk.
    const tracks = [{ key: 'A', segments: [{ path: Array.from({ length: 500 }, (_, i) => ({ t: i, lng: i, lat: i })) }] }]
    const resultJson = JSON.stringify({ tracks })
    const resultEvent = `event: result\ndata: ${resultJson}\n\n`
    const pieces = []
    for (let i = 0; i < resultEvent.length; i += 1000) {
      pieces.push(resultEvent.slice(i, i + 1000))
    }
    stubFetchWithChunks([
      'event: progress\ndata: {"done":1,"total":2}\n\n',
      'event: progress\ndata: {"done":2,"total":2}\n\n',
      ...pieces
    ])

    const progress = []
    const result = await streamHistoryTrack('http://api', 'ds', 0, 1, {
      onProgress: (payload) => progress.push(payload)
    })

    expect(progress).toEqual([
      { done: 1, total: 2 },
      { done: 2, total: 2 }
    ])
    expect(result.tracks).toHaveLength(1)
    expect(result.tracks[0].segments[0].path).toHaveLength(500)
  })

  it('collects per-entity track events when the result only carries metadata', async () => {
    stubFetchWithChunks([
      'event: progress\ndata: {"done":1,"total":2}\n\n',
      'event: track\ndata: {"key":"A","segments":[]}\n\n',
      'event: track\ndata: {"key":"B","segments":[]}\n\n',
      'event: result\ndata: {"dataId":"ds"}\n\n'
    ])
    const result = await streamHistoryTrack('http://api', 'ds', 0, 1, {})
    expect(result.dataId).toBe('ds')
    expect(result.tracks.map((t) => t.key).sort()).toEqual(['A', 'B'])
  })

  it('handles an event separator split across chunk boundaries', async () => {
    stubFetchWithChunks([
      'event: progress\ndata: {"done":1,"total":1}\n',
      '\nevent: result\ndata: {"tracks":[]}\n\n'
    ])
    const progress = []
    const result = await streamHistoryTrack('http://api', 'ds', 0, 1, {
      onProgress: (payload) => progress.push(payload)
    })
    expect(progress).toEqual([{ done: 1, total: 1 }])
    expect(result.tracks).toEqual([])
  })

  it('rejects on an error event', async () => {
    stubFetchWithChunks(['event: error\ndata: {"message":"boom"}\n\n'])
    await expect(streamHistoryTrack('http://api', 'ds', 0, 1, {})).rejects.toThrow('boom')
  })

  it('rejects when the stream ends without a result', async () => {
    stubFetchWithChunks(['event: progress\ndata: {"done":1,"total":2}\n\n'])
    await expect(streamHistoryTrack('http://api', 'ds', 0, 1, {})).rejects.toThrow('軌跡串流結束但沒有回傳結果')
  })
})
