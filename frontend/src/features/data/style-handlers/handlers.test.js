import { describe, expect, it } from 'vitest'
import { statZonePopulationStyle, taichungGarbageVehicle } from './index'

const hasStyleSmuggling = (obj) => Object.keys(obj || {}).some((k) => k.startsWith('__style_'))

describe('taichungGarbageVehicle', () => {
  const params = {
    speedField: 'status',
    normalColor: '#normal',
    mediumColor: '#medium',
    fastColor: '#fast',
    overSpeedColor: '#over',
    directionalIcons: {
      directionField: 'direct',
      vehicleField: 'cartype',
      vehiclePrefixMap: { N: 'g', R: 'r' },
      directionMap: { '↑': 'o01' }
    }
  }
  const run = (properties) => taichungGarbageVehicle({ properties }, params)

  it('colors by speed band and exposes SpeedBand', () => {
    expect(run({ status: 10 }).style.color).toBe('#normal')
    expect(run({ status: 40 }).style.color).toBe('#medium')
    const fast = run({ status: 60 })
    expect(fast.style.color).toBe('#fast')
    expect(fast.derivedFields.SpeedBand).toBe('high')
  })

  it('resolves iconId via directionalIcons into style (not derivedFields)', () => {
    const r = run({ status: 10, direct: '↑', cartype: 'N' })
    expect(r.style.iconId).toBe('g-o01')
    expect(hasStyleSmuggling(r.derivedFields)).toBe(false)
  })

  it('returns numeric pointSize + heatWeight in style', () => {
    const r = run({ status: 60 })
    expect(Number.isFinite(r.style.pointSize)).toBe(true)
    expect(Number.isFinite(r.style.heatWeight)).toBe(true)
  })
})

describe('statZonePopulationStyle', () => {
  it('returns heatWeight via style and P_CNT via derivedFields (no smuggling)', () => {
    const r = statZonePopulationStyle({ properties: { P_CNT: '1,000' } })
    expect(Number.isFinite(r.style.heatWeight)).toBe(true)
    expect(r.derivedFields.P_CNT).toBe(1000)
    expect(hasStyleSmuggling(r.derivedFields)).toBe(false)
  })

  it('handles missing population', () => {
    const r = statZonePopulationStyle({ properties: {} })
    expect(r.style.heatWeight).toBe(0.3)
    expect(r.derivedFields.P_CNT).toBe(0)
  })
})
