const DEFAULT_COLOR_MAP = {
  事故: '#ef4444',      // 紅色
  交通障礙: '#f97316',  // 橘色
  道路施工: '#facc15'   // 黃色
}

const DEFAULT_FALLBACK_COLOR = '#9ca3af' // 灰色 (其他)

export const policeBroadcastingServiceStyle = (ctx, params) => {
  const roadtypeField = params?.roadtypeField || 'roadtype'
  const colorMap = params?.colorMap || DEFAULT_COLOR_MAP
  const fallbackColor = params?.fallbackColor || DEFAULT_FALLBACK_COLOR

  const rawValue = ctx?.properties?.[roadtypeField]
  const roadtype = rawValue == null ? '' : String(rawValue).trim()
  const color = colorMap[roadtype] || fallbackColor

  return {
    style: {
      color
    }
  }
}
