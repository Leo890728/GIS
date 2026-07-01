// Style handler for the Taichung garbage/recycling fleet. Everything dataset-
// specific (field names, speed colour bands, directional icon mapping) lives
// here as DEFAULTS — the config only needs `{ handler: taichungGarbageVehicle }`.
// `params` may shallow-override any DEFAULTS key when needed.
//
// Icon naming contract: directional icons are `${prefix}-${suffix}` where prefix
// comes from cartype (N→tcg-v2-garbage, R→tcg-v2-recycle) and suffix from the
// `direct` arrow (o01..o08); the config's `icons` must register those ids.
const DEFAULTS = {
  speedField: 'status',
  overSpeedField: '',
  normalColor: '#5ec8f2',
  mediumColor: '#79d48a',
  fastColor: '#f2994a',
  overSpeedColor: '#eb5757',
  heatWeightBase: 1,
  fallbackIconId: 'tcg-v2-fallback',
  directionalIcons: {
    directionField: 'direct',
    vehicleField: 'cartype',
    vehiclePrefixMap: { N: 'tcg-v2-garbage', R: 'tcg-v2-recycle' },
    defaultVehiclePrefix: 'tcg-v2-garbage',
    directionMap: {
      '↑': 'o01',
      '↗': 'o02',
      '→': 'o03',
      '↘': 'o04',
      '↓': 'o05',
      '↙': 'o06',
      '←': 'o07',
      '↖': 'o08'
    }
  }
}

const isFiniteNumber = (value) => Number.isFinite(value)

const toNumber = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const isTruthyOverSpeed = (value) => {
  if (value == null) return false
  if (typeof value === 'boolean') return value
  const normalized = String(value).trim().toUpperCase()
  return normalized === 'Y' || normalized === 'YES' || normalized === 'TRUE' || normalized === '1'
}

const resolveDirectionalIcon = (properties, directionalIcons) => {
  const directionValue = properties?.[directionalIcons.directionField]
  const vehicleValue = properties?.[directionalIcons.vehicleField]
  const directionKey = directionValue == null ? '' : String(directionValue).trim()
  const vehicleKey = vehicleValue == null ? '' : String(vehicleValue).trim()
  const suffix = directionalIcons.directionMap[directionKey]
  const prefix = directionalIcons.vehiclePrefixMap[vehicleKey] || directionalIcons.defaultVehiclePrefix
  if (!suffix || !prefix) return null
  return `${prefix}-${suffix}`
}

export const taichungGarbageVehicle = (ctx, params) => {
  const p = { ...DEFAULTS, ...(params || {}) }
  const speed = toNumber(ctx.properties?.[p.speedField])
  const isOverSpeed = isTruthyOverSpeed(ctx.properties?.[p.overSpeedField])

  let color = p.normalColor
  let pointSize = 6
  let speedBand = 'low'
  if (isFiniteNumber(speed)) {
    if (speed >= 50) {
      color = p.fastColor
      pointSize = 8
      speedBand = 'high'
    } else if (speed >= 30) {
      color = p.mediumColor
      pointSize = 7
      speedBand = 'medium'
    }
  }
  if (isOverSpeed) {
    color = p.overSpeedColor
    pointSize = 9
    speedBand = 'overspeed'
  }

  const heatWeightBase = toNumber(p.heatWeightBase) ?? 1
  const heatWeightBySpeed = isFiniteNumber(speed) ? Math.max(0.2, speed / 40) : 1
  const heatWeight = Number((heatWeightBase * heatWeightBySpeed * (isOverSpeed ? 1.3 : 1)).toFixed(3))

  const iconId = resolveDirectionalIcon(ctx.properties, p.directionalIcons) || p.fallbackIconId

  return {
    style: {
      color,
      pointSize,
      heatWeight,
      ...(iconId ? { iconId } : {})
    },
    derivedFields: {
      OverSpeedText: isOverSpeed ? 'Yes' : 'No',
      SpeedBand: speedBand
    }
  }
}
