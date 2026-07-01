import { describe, expect, it } from 'vitest'
import { formatTooltipItemValue, interpolateTemplate, resolveTooltipTitle } from './formatters'

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

describe('formatTooltipItemValue', () => {
  const props = { a: 'X', b: 'Y', n: 12.345, dt: '20260630T080000' }

  it('formats a single field by format', () => {
    expect(formatTooltipItemValue({ field: 'n', format: 'number', digits: 1 }, props)).toBe('12.3')
  })

  it('interpolates a template item (raw, multi-field)', () => {
    expect(formatTooltipItemValue({ template: '{a} / {b}' }, props)).toBe('X / Y')
  })

  it('template overrides field/format', () => {
    expect(formatTooltipItemValue({ field: 'n', format: 'number', template: '{a}' }, props)).toBe('X')
  })

  it('falls back to "-" for empty field or empty template result', () => {
    expect(formatTooltipItemValue({ field: 'missing' }, props)).toBe('-')
    expect(formatTooltipItemValue({ template: '{missing}' }, props)).toBe('-')
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
