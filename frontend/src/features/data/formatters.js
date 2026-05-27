const DEFAULT_FALLBACK = '-'
const COMPACT_DATETIME_PATTERN = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})$/

const isEmpty = (value) => value == null || value === ''

const toNumber = (value) => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const converted = Number(value)
  return Number.isFinite(converted) ? converted : null
}

const formatText = (value, item) => {
  const text = String(value)
  return item?.unit ? `${text} ${item.unit}` : text
}

const formatNumber = (value, item) => {
  const numberValue = toNumber(value)
  if (numberValue == null) return DEFAULT_FALLBACK
  const digits = Number.isInteger(item?.digits) ? item.digits : null
  const text = digits == null ? String(numberValue) : numberValue.toFixed(digits)
  return item?.unit ? `${text} ${item.unit}` : text
}

const formatDateTime = (value, item) => {
  if (typeof value !== 'string' && !(value instanceof Date)) return DEFAULT_FALLBACK

  let parsed
  if (value instanceof Date) {
    parsed = value
  } else {
    const compactMatch = value.match(COMPACT_DATETIME_PATTERN)
    if (compactMatch) {
      const [, year, month, day, hour, minute, second] = compactMatch
      parsed = new Date(
        Number(year),
        Number(month) - 1,
        Number(day),
        Number(hour),
        Number(minute),
        Number(second)
      )
    } else {
      parsed = new Date(value)
    }
  }

  if (Number.isNaN(parsed.getTime())) return DEFAULT_FALLBACK
  const locale = item?.locale || 'zh-TW'
  const options = item?.dateTimeOptions || {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }
  return new Intl.DateTimeFormat(locale, options).format(parsed)
}

const formatMapped = (value, item) => {
  const mapping = item?.map
  if (!mapping || typeof mapping !== 'object') return formatText(value, item)
  const mapped = mapping[value]
  if (mapped == null) return formatText(value, item)
  return formatText(mapped, item)
}

const FORMATTERS = {
  text: formatText,
  number: formatNumber,
  datetime: formatDateTime,
  enumMap: formatMapped,
  booleanMap: formatMapped
}

const resolveFormatKey = (item) => {
  if (item?.format && FORMATTERS[item.format]) return item.format
  if (item?.map) return 'enumMap'
  if (item?.unit) return 'number'
  return 'text'
}

export const formatTooltipItemValue = (item, properties) => {
  if (!item || typeof item !== 'object') return DEFAULT_FALLBACK
  const rawValue = properties?.[item.field]
  if (isEmpty(rawValue)) return DEFAULT_FALLBACK

  const formatKey = resolveFormatKey(item)
  const formatter = FORMATTERS[formatKey] || FORMATTERS.text
  return formatter(rawValue, item)
}
