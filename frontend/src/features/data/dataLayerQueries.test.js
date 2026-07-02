import { describe, expect, it } from 'vitest'
import {
  buildAggregatePayload,
  buildPointQueryPayload,
  getDueDynamicLayerKeys,
  getDynamicPollInterval,
  hasRangeFeatures,
  hasRangeRequestCodes,
  isDynamicLayer
} from './dataLayerQueries'

const fc = (features = []) => ({ type: 'FeatureCollection', features })

describe('hasRangeFeatures', () => {
  it('is true only for a non-empty FeatureCollection', () => {
    expect(hasRangeFeatures(fc([{}]))).toBe(true)
    expect(hasRangeFeatures(fc([]))).toBe(false)
    expect(hasRangeFeatures(null)).toBe(false)
    expect(hasRangeFeatures({ type: 'Feature' })).toBe(false)
  })
})

describe('hasRangeRequestCodes', () => {
  it('is true when any code array is non-empty', () => {
    expect(hasRangeRequestCodes({ townCodes: ['T1'] })).toBe(true)
    expect(hasRangeRequestCodes({ statZone2Codes: ['A6501-05'] })).toBe(true)
    expect(hasRangeRequestCodes({ statZone1Codes: ['A6501-05-001'] })).toBe(true)
    expect(hasRangeRequestCodes({ countyCodes: [], villageCodes: [] })).toBe(false)
    expect(hasRangeRequestCodes(null)).toBe(false)
  })
})

describe('isDynamicLayer / getDynamicPollInterval', () => {
  it('detects dynamic layers', () => {
    expect(isDynamicLayer({ dynamic: { enabled: true } })).toBe(true)
    expect(isDynamicLayer({ dynamic: { enabled: false } })).toBe(false)
    expect(isDynamicLayer({})).toBe(false)
  })

  it('clamps poll interval to a 5s floor and 60s default', () => {
    expect(getDynamicPollInterval({ dynamic: { pollIntervalMs: 30000 } })).toBe(30000)
    expect(getDynamicPollInterval({ dynamic: { pollIntervalMs: 100 } })).toBe(5000)
    expect(getDynamicPollInterval({})).toBe(60000)
    expect(getDynamicPollInterval({ dynamic: { pollIntervalMs: -1 } })).toBe(60000)
  })
})

describe('buildPointQueryPayload', () => {
  const layer = { query: { dataId: 'd1', endpoint: '/x', useRangeRequest: true, filters: { a: 1 } } }

  it('drops endpoint/useRangeRequest and ignores range when filtering is off', () => {
    const payload = buildPointQueryPayload(layer, { rangePointFilterEnabled: false })
    expect(payload).toEqual({ dataId: 'd1', filters: { a: 1 } })
    expect(payload).not.toHaveProperty('endpoint')
    expect(payload).not.toHaveProperty('useRangeRequest')
    expect(payload).not.toHaveProperty('range')
  })

  it('merges the range request when codes are provided', () => {
    const payload = buildPointQueryPayload(layer, {
      rangePointFilterEnabled: true,
      selectedRangeRequest: { townCodes: ['T1'] }
    })
    expect(payload.townCodes).toEqual(['T1'])
  })

  it('attaches the drawn range GeoJSON when present', () => {
    const range = fc([{ type: 'Feature' }])
    const payload = buildPointQueryPayload({ query: { dataId: 'd1' } }, {
      rangePointFilterEnabled: true,
      selectedRangeGeoJson: range
    })
    expect(payload.range).toBe(range)
  })

  it('falls back to an empty FeatureCollection when filtering on but nothing drawn', () => {
    const payload = buildPointQueryPayload({ query: { dataId: 'd1' } }, { rangePointFilterEnabled: true })
    expect(payload.range).toEqual(fc([]))
  })
})

describe('buildAggregatePayload', () => {
  it('builds a base payload with default metrics and conditional fields', () => {
    const payload = buildAggregatePayload({ query: { dataId: 'd1', bbox: [1, 2, 3, 4] }, aggregate: {} }, null, null, false)
    expect(payload).toEqual({ dataId: 'd1', metrics: ['count'], bbox: [1, 2, 3, 4] })
  })

  it('uses query.range when filtering is off', () => {
    const payload = buildAggregatePayload({ query: { dataId: 'd1', range: fc([{}]) }, aggregate: {} }, null, null, false)
    expect(payload.range).toEqual(fc([{}]))
  })

  it('merges range request over GeoJSON when codes are present', () => {
    const payload = buildAggregatePayload(
      { query: { dataId: 'd1' }, aggregate: { useRangeRequest: true } },
      fc([{}]),
      { countyCodes: ['C1'] },
      true
    )
    expect(payload.countyCodes).toEqual(['C1'])
    expect(payload).not.toHaveProperty('range')
  })

  it('sends drawn range GeoJSON when filtering on without a code request', () => {
    const payload = buildAggregatePayload({ query: { dataId: 'd1' }, aggregate: {} }, fc([{}]), null, true)
    expect(payload.range).toEqual(fc([{}]))
  })

  it('merges aggregate.query overrides last', () => {
    const payload = buildAggregatePayload(
      { query: { dataId: 'd1' }, aggregate: { groupBy: 'town', query: { extra: 9 } } },
      null,
      null,
      false
    )
    expect(payload.groupBy).toBe('town')
    expect(payload.extra).toBe(9)
  })
})

describe('getDueDynamicLayerKeys', () => {
  const now = 1_000_000
  const layerState = {
    a: { active: true, dynamic: { enabled: true } },
    b: { active: true, dynamic: { enabled: true } },
    c: { active: false, dynamic: { enabled: true } },
    d: { active: true, dynamic: { enabled: false } },
    sim: { active: true, dynamic: { enabled: true } }
  }
  const runtimeMap = {
    a: { nextRefreshAt: null },
    b: { nextRefreshAt: now + 5000 },
    c: { nextRefreshAt: null },
    d: { nextRefreshAt: null },
    sim: { nextRefreshAt: null }
  }

  it('returns active, dynamic, due layers, excluding the simulator layer', () => {
    const due = getDueDynamicLayerKeys(layerState, runtimeMap, { simulatorLayerKey: 'sim', now })
    expect(due).toEqual(['a']) // b not due, c inactive, d not dynamic, sim excluded
  })

  it('includes a layer once its nextRefreshAt has passed', () => {
    const due = getDueDynamicLayerKeys(layerState, runtimeMap, { simulatorLayerKey: 'sim', now: now + 5000 })
    expect(due.sort()).toEqual(['a', 'b'])
  })
})
