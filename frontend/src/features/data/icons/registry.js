const loadingByMap = new WeakMap()

const getLoadingSet = (map) => {
  const current = loadingByMap.get(map)
  if (current) return current
  const created = new Set()
  loadingByMap.set(map, created)
  return created
}

const validateIconDef = (iconDef) => {
  if (!iconDef || typeof iconDef !== 'object') return false
  if (!iconDef.id || typeof iconDef.id !== 'string') return false
  if (typeof iconDef.builder === 'function') return true
  if (iconDef.src && typeof iconDef.src === 'string') return true
  return false
}

const loadImageFromUrl = async (map, src) => {
  const response = await map.loadImage(src)
  if (!response || !response.data) {
    throw new Error(`Failed to load image: ${src}`)
  }
  return response.data
}

const addIconIfNeeded = async (map, iconDef, loadingSet) => {
  if (map.hasImage(iconDef.id)) return
  if (loadingSet.has(iconDef.id)) return
  loadingSet.add(iconDef.id)
  try {
    if (typeof iconDef.builder === 'function') {
      const imageData = iconDef.builder(iconDef.options || {})
      if (imageData && !map.hasImage(iconDef.id)) {
        map.addImage(iconDef.id, imageData, { pixelRatio: 2 })
      }
      return
    }
    if (iconDef.src && typeof iconDef.src === 'string') {
      const loaded = await loadImageFromUrl(map, iconDef.src)
      if (!map.hasImage(iconDef.id)) {
        map.addImage(iconDef.id, loaded, { pixelRatio: 2 })
      }
    }
  } finally {
    loadingSet.delete(iconDef.id)
  }
}

export const ensureIcons = async (map, iconDefs) => {
  if (!map || !Array.isArray(iconDefs) || !iconDefs.length) return

  const loadingSet = getLoadingSet(map)
  for (const iconDef of iconDefs) {
    if (!validateIconDef(iconDef)) continue
    try {
      await addIconIfNeeded(map, iconDef, loadingSet)
    } catch (error) {
      console.warn(`[icons] failed to load icon '${iconDef.id}'`, error)
      continue
    }
  }
}
