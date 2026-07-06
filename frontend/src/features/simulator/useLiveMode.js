import { fetchHistoryFrames, fetchHistoryRange } from './simulatorApi'
import { toMs } from './playbackTimeline'

// Live mode: pin the clock to the leading edge of the recording and poll for
// newly captured frames, extending the timeline as data arrives. Owns the poll
// timer; drives the shared playback `state` and the frame renderer. Entering
// live cancels smooth playback (it would be stale against the moving edge).
export const useLiveMode = ({
  apiBaseUrl,
  state,
  deriveSegments,
  applyActiveFrame,
  pausePlayback,
  smooth,
  clearSelection
}) => {
  let liveTimer = null

  const stopLive = () => {
    if (liveTimer) {
      clearInterval(liveTimer)
      liveTimer = null
    }
  }

  const exitLive = () => {
    if (state.mode === 'live') {
      state.mode = 'history'
      stopLive()
    }
  }

  const pollLive = async () => {
    if (state.mode !== 'live' || !state.dataId) return
    try {
      const range = await fetchHistoryRange(apiBaseUrl, state.dataId)
      const newTo = toMs(range?.to)
      if (newTo == null) return
      if (newTo > state.to) {
        state.to = newTo
        state.count = Number(range.count) || state.count
        const framesResponse = await fetchHistoryFrames(apiBaseUrl, state.dataId)
        if (Array.isArray(framesResponse?.frames)) {
          state.frames = framesResponse.frames.map(toMs).filter((value) => value != null)
        }
        state.segments = deriveSegments()
      }
      // Keep the clock pinned to "now".
      state.playFrom = state.from
      state.playTo = state.to
      state.currentTime = state.to
      applyActiveFrame(true)
    } catch (error) {
      console.error(error)
    }
  }

  const startLive = () => {
    stopLive()
    const everyMs = Math.max(15000, (Number(state.intervalSeconds) || 60) * 1000)
    liveTimer = setInterval(pollLive, everyMs)
  }

  const toggleLive = () => {
    if (state.mode === 'live') {
      exitLive()
      return
    }
    pausePlayback()
    // Live follows the leading edge as frames; smooth tracks would be stale.
    smooth.disable()
    state.selectedSegmentIndex = -1
    clearSelection()
    state.mode = 'live'
    state.playFrom = state.from
    state.playTo = state.to
    state.currentTime = state.to
    applyActiveFrame(true)
    pollLive()
    startLive()
  }

  return { stopLive, exitLive, toggleLive, pollLive, startLive }
}
