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

export const isRangeFullySelected = (range, selectedSet) => {
  const leafIds = getLeafRangeIds(range)
  return leafIds.length > 0 && leafIds.every((id) => selectedSet.has(id))
}

export const isRangePartiallySelected = (range, selectedSet) => {
  const selectedCount = getLeafRangeIds(range).filter((id) => selectedSet.has(id)).length
  return selectedCount > 0 && !isRangeFullySelected(range, selectedSet)
}

// range node level → request payload key
const LEVEL_CODE_KEYS = {
  county: 'countyCodes',
  township: 'townCodes',
  village: 'villageCodes',
  stat_zone_2: 'statZone2Codes',
  stat_zone_1: 'statZone1Codes',
  stat_zone: 'statZoneCodes'
}

export const buildRangeRequest = (rangeTree, selectedRangeIds) => {
  const selectedSet = new Set(selectedRangeIds)
  const request = {
    countyCodes: [],
    townCodes: [],
    villageCodes: [],
    statZone2Codes: [],
    statZone1Codes: [],
    statZoneCodes: []
  }

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
