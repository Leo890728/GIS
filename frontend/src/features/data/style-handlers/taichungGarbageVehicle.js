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

const resolveIconFromFieldRules = (properties, iconByField) => {
  if (!iconByField || typeof iconByField !== 'object') return null
  for (const [fieldName, mapping] of Object.entries(iconByField)) {
    if (!mapping || typeof mapping !== 'object') continue
    const rawValue = properties?.[fieldName]
    const normalized = rawValue == null ? '' : String(rawValue).trim()
    if (Object.prototype.hasOwnProperty.call(mapping, normalized)) {
      return mapping[normalized]
    }
  }
  return null
}

const resolveDirectionalIcon = (properties, directionalIcons) => {
  if (!directionalIcons || typeof directionalIcons !== 'object') return null
  const directionField = directionalIcons.directionField || 'direct'
  const vehicleField = directionalIcons.vehicleField || 'cartype'
  const directionMap = directionalIcons.directionMap || {}
  const vehiclePrefixMap = directionalIcons.vehiclePrefixMap || {}

  const directionValue = properties?.[directionField]
  const vehicleValue = properties?.[vehicleField]
  const directionKey = directionValue == null ? '' : String(directionValue).trim()
  const vehicleKey = vehicleValue == null ? '' : String(vehicleValue).trim()
  const suffix = directionMap[directionKey]
  const prefix = vehiclePrefixMap[vehicleKey] || directionalIcons.defaultVehiclePrefix
  if (!suffix || !prefix) return null
  return `${prefix}-${suffix}`
}

export const taichungGarbageVehicle = (ctx, params) => {
  /*
   * params example:
   * {
   *   speedField: 'status',
   *   overSpeedField: 'OverSpeed',
   *   iconIds: {
   *     normal: 'tcg-v2-normal',
   *     medium: 'tcg-v2-medium',
   *     fast: 'tcg-v2-fast',
   *     overSpeed: 'tcg-v2-overspeed'
   *   },
   *   iconByField: {
   *     cartype: { R: 'tcg-v2-recycle' }
   *   },
   *   directionalIcons: {
   *     directionField: 'direct',
   *     vehicleField: 'cartype',
   *     vehiclePrefixMap: {
   *       N: 'tcg-v2-garbage',
   *       R: 'tcg-v2-recycle'
   *     },
   *     directionMap: {
   *       '\\u2191': 'o01', '\\u2197': 'o02', '\\u2192': 'o03', '\\u2198': 'o04',
   *       '\\u2193': 'o05', '\\u2199': 'o06', '\\u2190': 'o07', '\\u2196': 'o08'
   *     }
   *   }
   * }
   * Priority: directionalIcons > iconByField > iconIds(speed band)
   */
  const speedField = params?.speedField || 'SpeedValue'
  const overSpeedField = params?.overSpeedField || 'OverSpeed'
  const speed = toNumber(ctx.properties?.[speedField])
  const isOverSpeed = isTruthyOverSpeed(ctx.properties?.[overSpeedField])

  const normalColor = params?.normalColor || '#4ade80'
  const mediumColor = params?.mediumColor || '#facc15'
  const fastColor = params?.fastColor || '#fb923c'
  const overSpeedColor = params?.overSpeedColor || '#ef4444'

  let pointColor = normalColor
  let pointSize = 6
  let speedBand = 'low'
  let iconBand = 'normal'
  if (isFiniteNumber(speed)) {
    if (speed >= 50) {
      pointColor = fastColor
      pointSize = 8
      speedBand = 'high'
      iconBand = 'fast'
    } else if (speed >= 30) {
      pointColor = mediumColor
      pointSize = 7
      speedBand = 'medium'
      iconBand = 'medium'
    }
  }
  if (isOverSpeed) {
    pointColor = overSpeedColor
    pointSize = 9
    speedBand = 'overspeed'
    iconBand = 'overSpeed'
  }

  const heatWeightBase = toNumber(params?.heatWeightBase) ?? 1
  const heatWeightBySpeed = isFiniteNumber(speed) ? Math.max(0.2, speed / 40) : 1
  const heatWeight = Number((heatWeightBase * heatWeightBySpeed * (isOverSpeed ? 1.3 : 1)).toFixed(3))
  const iconIds = params?.iconIds || {}
  const iconIdFromBand = iconIds[iconBand] || iconIds.normal || null
  const iconIdFromField = resolveIconFromFieldRules(ctx.properties, params?.iconByField)
  const directionalIconId = resolveDirectionalIcon(ctx.properties, params?.directionalIcons)
  const resolvedIconId = directionalIconId || iconIdFromField || iconIdFromBand

  return {
    style: {
      pointColor,
      pointSize,
      heatWeight
    },
    derivedFields: {
      OverSpeedText: isOverSpeed ? 'Yes' : 'No',
      SpeedBand: speedBand,
      ...(resolvedIconId ? { __style_iconId: resolvedIconId } : {})
    }
  }
}
