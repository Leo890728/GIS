import { describe, expect, it } from 'vitest'
import { interpolateTemplate, resolveTooltipTitle } from './formatters'

describe('interpolateTemplate', () => {
  const props = { car_licence: 'ABC-123', wepno: 'W01', empty: '' }

  it('replaces a single placeholder', () => {
    expect(interpolateTemplate('車牌 {car_licence}', props)).toBe('車牌 ABC-123')
  })

  it('replaces multiple placeholders and keeps literal text', () => {
    expect(interpolateTemplate('{car_licence} ({wepno})', props)).toBe('ABC-123 (W01)')
  })

  it('renders missing/empty fields as empty string', () => {
    expect(interpolateTemplate('{nope}', props)).toBe('')
    expect(interpolateTemplate('{empty}!', props)).toBe('!')
  })

  it('trims whitespace inside braces', () => {
    expect(interpolateTemplate('{ car_licence }', props)).toBe('ABC-123')
  })

  it('handles missing template/properties', () => {
    expect(interpolateTemplate(undefined, props)).toBe('')
    expect(interpolateTemplate('{a}', null)).toBe('')
  })
})

describe('resolveTooltipTitle', () => {
  it('interpolates the titleTemplate and trims', () => {
    expect(resolveTooltipTitle({ titleTemplate: '  {name} ' }, { name: 'Plant A' })).toBe('Plant A')
  })

  it('returns empty string without a template', () => {
    expect(resolveTooltipTitle({}, { name: 'x' })).toBe('')
    expect(resolveTooltipTitle(null, {})).toBe('')
  })
})
