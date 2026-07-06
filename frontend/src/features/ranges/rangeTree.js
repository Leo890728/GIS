export const emptyFeatureCollection = () => ({ type: 'FeatureCollection', features: [] })

export const normalizeRangeNode = (node) => ({
  id: node?.id || '',
  name: node?.name || node?.code || 'Unknown range',
  description: node?.description || '',
  color: node?.color || '#57a6f5',
  type: node?.type || 'admin',
  level: node?.level || 'custom',
  code: node?.code || '',
  selectable: node?.selectable !== false,
  metadata: node?.metadata || {},
  children: Array.isArray(node?.children) ? node.children.map(normalizeRangeNode) : []
})

export const getRangeChildren = (range) => (Array.isArray(range?.children) ? range.children : [])

export const getLeafRangeIds = (range) => {
  const children = getRangeChildren(range)
  if (!children.length) {
    return range?.selectable && range?.id ? [range.id] : []
  }
  return children.flatMap((child) => getLeafRangeIds(child))
}

export const getAllLeafRangeIds = (nodes) => nodes.flatMap((node) => getLeafRangeIds(node))

export const findRangeNode = (nodes, rangeId) => {
  for (const node of nodes || []) {
    if (node.id === rangeId) {
      return node
    }

    const childMatch = findRangeNode(node.children, rangeId)
    if (childMatch) {
      return childMatch
    }
  }

  return null
}

// Locate a node by its boundary level + code (map-click uses these, not ids).
export const findRangeNodeByCode = (nodes, level, code) => {
  const targetCode = String(code || '')
  for (const node of nodes || []) {
    if (node.level === level && String(node.code || '') === targetCode) {
      return node
    }
    const childMatch = findRangeNodeByCode(node.children, level, code)
    if (childMatch) {
      return childMatch
    }
  }

  return null
}

export const isRangeFullySelected = (range, selectedSet) => {
  const leafIds = getLeafRangeIds(range)
  return leafIds.length > 0 && leafIds.every((id) => selectedSet.has(id))
}

export const isRangePartiallySelected = (range, selectedSet) => {
  const selectedCount = getLeafRangeIds(range).filter((id) => selectedSet.has(id)).length
  return selectedCount > 0 && !isRangeFullySelected(range, selectedSet)
}

// Boundary levels selectable via map-click, ordered coarse → fine. The dropdown
// sends `level` to the backend, which resolves the clicked point to a code.
export const RANGE_PICK_LEVELS = [
  { level: 'county', label: '縣市' },
  { level: 'township', label: '鄉鎮市區' },
  { level: 'village', label: '村里' },
  { level: 'stat_zone_2', label: '二級發布區' },
  { level: 'stat_zone_1', label: '一級發布區' },
  { level: 'stat_zone', label: '最小統計區' }
]

// range node level → request payload key
export const LEVEL_CODE_KEYS = {
  county: 'countyCodes',
  township: 'townCodes',
  village: 'villageCodes',
  stat_zone_2: 'statZone2Codes',
  stat_zone_1: 'statZone1Codes',
  stat_zone: 'statZoneCodes'
}

export const emptyRangeRequest = () => ({
  countyCodes: [],
  townCodes: [],
  villageCodes: [],
  statZone2Codes: [],
  statZone1Codes: [],
  statZoneCodes: []
})

// Union two range requests, de-duplicating codes per level. Used to fold the
// map-click fallback selection into the tree-derived request.
export const mergeRangeRequests = (...requests) => {
  const merged = emptyRangeRequest()
  for (const key of Object.keys(merged)) {
    const seen = new Set()
    for (const request of requests) {
      for (const code of request?.[key] || []) {
        if (!seen.has(code)) {
          seen.add(code)
          merged[key].push(code)
        }
      }
    }
  }
  return merged
}

export const buildRangeRequest = (rangeTree, selectedRangeIds) => {
  const selectedSet = new Set(selectedRangeIds)
  const request = emptyRangeRequest()

  const collect = (node) => {
    if (!node?.id) return

    const codeKey = LEVEL_CODE_KEYS[node.level]
    if (codeKey && node.code && isRangeFullySelected(node, selectedSet)) {
      request[codeKey].push(node.code)
      return
    }

    for (const child of getRangeChildren(node)) {
      collect(child)
    }
  }

  for (const node of rangeTree) {
    collect(node)
  }

  return request
}
