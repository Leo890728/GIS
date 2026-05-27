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

export const buildRangeRequest = (rangeTree, selectedRangeIds) => {
  const selectedSet = new Set(selectedRangeIds)
  const countyCodes = []
  const townCodes = []
  const villageCodes = []
  const statZoneCodes = []

  const collect = (node) => {
    if (!node?.id) return
    const children = getRangeChildren(node)

    if (isRangeFullySelected(node, selectedSet)) {
      if (node.level === 'county') {
        countyCodes.push(node.code)
        return
      }
      if (node.level === 'township') {
        townCodes.push(node.code)
        return
      }
      if (node.level === 'village') {
        villageCodes.push(node.code)
        return
      }
      if (node.level === 'stat_zone_min_113') {
        statZoneCodes.push(node.code)
        return
      }
    }

    for (const child of children) {
      collect(child)
    }
  }

  for (const node of rangeTree) {
    collect(node)
  }

  return {
    countyCodes: countyCodes.filter(Boolean),
    townCodes: townCodes.filter(Boolean),
    villageCodes: villageCodes.filter(Boolean),
    statZoneCodes: statZoneCodes.filter(Boolean)
  }
}
