import { computed, onMounted, ref, watch } from 'vue'
import { fetchRangeGeoJson, fetchRangePick, fetchRangeTree, fetchStatZoneChildren } from './rangeApi'
import {
  LEVEL_CODE_KEYS,
  buildRangeRequest,
  emptyFeatureCollection,
  emptyRangeRequest,
  findRangeNode,
  findRangeNodeByCode,
  getAllLeafRangeIds,
  getLeafRangeIds,
  mergeRangeRequests,
  normalizeRangeNode
} from './rangeTree'

const STAT_PICK_LEVELS = new Set(['stat_zone_2', 'stat_zone_1', 'stat_zone'])

const normalizeCode = (value) => String(value ?? '').trim()

export const useRanges = (apiBaseUrl) => {
  // [{ id, name, ranges: [...] }] — 行政區樹與統計區樹
  const rangeTrees = ref([])
  const selectedRangeIds = ref([])
  const selectedRangeGeoJson = ref(emptyFeatureCollection())
  const rangeNodeLoading = ref({})

  // Map-click range picking. `pickModeEnabled` gates the map click handler;
  // `pickLevel` is the boundary level the dropdown selected. `mapSelectedCodes`
  // is the fallback selection for codes with no matching tree node (deep stat
  // zones that were never expanded) — merged into selectedRangeRequest so the
  // highlight + downstream see one unified selection.
  const pickModeEnabled = ref(false)
  const pickLevel = ref('township')
  const mapSelectedCodes = ref(emptyRangeRequest())

  const rangeRoots = computed(() => rangeTrees.value.flatMap((tree) => tree.ranges))
  const statRangeRoots = computed(() => rangeTrees.value.find((tree) => tree.id === 'stat')?.ranges || [])
  const selectedRangeRequest = computed(() =>
    mergeRangeRequests(buildRangeRequest(rangeRoots.value, selectedRangeIds.value), mapSelectedCodes.value)
  )

  let rangeRequestSequence = 0
  const rangeChildLoadPromises = new Map()

  const toggleRange = (rangeId) => {
    const target = findRangeNode(rangeRoots.value, rangeId)
    if (!target) return

    const leafIds = getLeafRangeIds(target)
    if (!leafIds.length) return

    const selectedSet = new Set(selectedRangeIds.value)
    const isFullySelected = leafIds.every((id) => selectedSet.has(id))

    for (const id of leafIds) {
      if (isFullySelected) {
        selectedSet.delete(id)
      } else {
        selectedSet.add(id)
      }
    }

    selectedRangeIds.value = [...selectedSet]
  }

  const setPickModeEnabled = (enabled) => {
    pickModeEnabled.value = enabled === true
  }

  const setPickLevel = (level) => {
    if (LEVEL_CODE_KEYS[level]) pickLevel.value = level
  }

  const toggleMapSelectedCode = (levelKey, code) => {
    const current = mapSelectedCodes.value[levelKey] || []
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code]
    mapSelectedCodes.value = { ...mapSelectedCodes.value, [levelKey]: next }
  }

  const foldLoadedFallbackCodesIntoSelection = (childNodes, selectedSet) => {
    const nextFallback = { ...mapSelectedCodes.value }
    let changed = false

    for (const child of childNodes) {
      const levelKey = LEVEL_CODE_KEYS[child?.level]
      const code = String(child?.code || '')
      if (!levelKey || !code) continue

      const fallback = nextFallback[levelKey] || []
      if (!fallback.includes(code)) continue

      if (child?.id) selectedSet.add(child.id)
      nextFallback[levelKey] = fallback.filter((item) => item !== code)
      changed = true
    }

    if (changed) {
      mapSelectedCodes.value = nextFallback
    }
  }

  const loadChildrenForNode = async (target) => {
    if (!target) return []

    const childLevel = target?.metadata?.childLevel
    const childCount = Number(target?.metadata?.childCount || 0)
    const parentCode = normalizeCode(target.code)
    if (!childLevel || !parentCode || childCount <= 0) {
      return Array.isArray(target.children) ? target.children : []
    }
    if (target?.metadata?.childrenLoaded === true) {
      return Array.isArray(target.children) ? target.children : []
    }
    if (rangeChildLoadPromises.has(target.id)) {
      return rangeChildLoadPromises.get(target.id)
    }

    const promise = (async () => {
      setRangeNodeLoading(target.id, true)
      try {
        const payload = await fetchStatZoneChildren(apiBaseUrl, target.level, parentCode)
        const childNodes = Array.isArray(payload?.ranges) ? payload.ranges.map(normalizeRangeNode) : []

        target.children = childNodes
        target.metadata = {
          ...(target.metadata || {}),
          childrenLoaded: true
        }

        // 父節點原本以自身 id 代表整個範圍；載入子節點後改由子節點承接選取狀態。
        const selectedSet = new Set(selectedRangeIds.value)
        if (selectedSet.has(target.id)) {
          selectedSet.delete(target.id)
          for (const child of childNodes) {
            if (child?.id) {
              selectedSet.add(child.id)
            }
          }
        }
        foldLoadedFallbackCodesIntoSelection(childNodes, selectedSet)
        selectedRangeIds.value = [...selectedSet]

        return childNodes
      } catch (error) {
        console.error(error)
        return Array.isArray(target.children) ? target.children : []
      } finally {
        setRangeNodeLoading(target.id, false)
        rangeChildLoadPromises.delete(target.id)
      }
    })()

    rangeChildLoadPromises.set(target.id, promise)
    return promise
  }

  const ensureStatRangePathLoaded = async ({ level, code, ancestors } = {}) => {
    if (!STAT_PICK_LEVELS.has(level)) return true

    const pickedCode = normalizeCode(code)
    const ancestorCode = (ancestorLevel) => normalizeCode(ancestors?.[ancestorLevel])
    const townshipCode = ancestorCode('township')
    if (!townshipCode) return false

    let parent = findRangeNodeByCode(statRangeRoots.value, 'township', townshipCode)
    if (!parent) return false

    await loadChildrenForNode(parent)
    if (level === 'stat_zone_2') {
      return Boolean(findRangeNodeByCode(statRangeRoots.value, 'stat_zone_2', pickedCode))
    }

    const code2 = ancestorCode('stat_zone_2')
    if (!code2) return false
    parent = findRangeNodeByCode(statRangeRoots.value, 'stat_zone_2', code2)
    if (!parent) return false

    await loadChildrenForNode(parent)
    if (level === 'stat_zone_1') {
      return Boolean(findRangeNodeByCode(statRangeRoots.value, 'stat_zone_1', pickedCode))
    }

    const code1 = ancestorCode('stat_zone_1')
    if (!code1) return false
    parent = findRangeNodeByCode(statRangeRoots.value, 'stat_zone_1', code1)
    if (!parent) return false

    await loadChildrenForNode(parent)
    return Boolean(findRangeNodeByCode(statRangeRoots.value, 'stat_zone', pickedCode))
  }

  // Add/remove a clicked boundary polygon. Prefer folding into the tree
  // selection (so the tree panel checkbox stays in sync + downstream reuse);
  // only codes with no loaded tree node fall back to mapSelectedCodes.
  const toggleRangeByFeature = ({ level, code } = {}) => {
    const levelKey = LEVEL_CODE_KEYS[level]
    const targetCode = normalizeCode(code)
    if (!levelKey || !targetCode) return

    const node = findRangeNodeByCode(rangeRoots.value, level, targetCode)
    if (node) {
      // A tree node now covers this code — drop any earlier fallback entry so
      // the two paths can't both hold it (stale highlight).
      const fallback = mapSelectedCodes.value[levelKey] || []
      if (fallback.includes(targetCode)) {
        mapSelectedCodes.value = {
          ...mapSelectedCodes.value,
          [levelKey]: fallback.filter((c) => c !== targetCode)
        }
      }
      toggleRange(node.id)
    } else {
      toggleMapSelectedCode(levelKey, targetCode)
    }
  }

  const runRangePick = async ({ level, lng, lat }) => {
    try {
      const result = await fetchRangePick(apiBaseUrl, { level, lng, lat })
      if (result?.hit && result.code != null && result.code !== '') {
        const resultLevel = result.level || level
        const resultCode = normalizeCode(result.code)
        await ensureStatRangePathLoaded({
          level: resultLevel,
          code: resultCode,
          ancestors: result.ancestors || {}
        })
        toggleRangeByFeature({ level: resultLevel, code: resultCode })
      }
    } catch (error) {
      console.error(error)
    }
  }

  // Serialize picks so rapid clicks apply their toggles in click order (each
  // pick reads/writes the selection, and lazy path-loading is async) — two
  // in-flight clicks on the same polygon must not cancel each other out.
  let rangePickChain = Promise.resolve()

  const toggleRangeByPoint = ({ level, lng, lat } = {}) => {
    const targetLevel = level || pickLevel.value
    if (!LEVEL_CODE_KEYS[targetLevel]) return rangePickChain

    const pointLng = Number(lng)
    const pointLat = Number(lat)
    if (!Number.isFinite(pointLng) || !Number.isFinite(pointLat)) return rangePickChain

    rangePickChain = rangePickChain.then(() =>
      runRangePick({ level: targetLevel, lng: pointLng, lat: pointLat })
    )
    return rangePickChain
  }

  const loadSelectedRangeGeoJson = async () => {
    const requestId = ++rangeRequestSequence
    const payload = selectedRangeRequest.value
    const hasSelection = Object.values(payload).some((codes) => codes.length > 0)

    if (!hasSelection) {
      selectedRangeGeoJson.value = emptyFeatureCollection()
      return
    }

    try {
      const geojson = await fetchRangeGeoJson(apiBaseUrl, payload)
      if (requestId === rangeRequestSequence) {
        selectedRangeGeoJson.value = geojson
      }
    } catch (error) {
      console.error(error)
      if (requestId === rangeRequestSequence) {
        selectedRangeGeoJson.value = emptyFeatureCollection()
      }
    }
  }

  const loadRangesTree = async () => {
    try {
      const payload = await fetchRangeTree(apiBaseUrl)
      const trees = (Array.isArray(payload?.trees) ? payload.trees : []).map((tree) => ({
        id: tree?.id || '',
        name: tree?.name || '',
        ranges: Array.isArray(tree?.ranges) ? tree.ranges.map(normalizeRangeNode) : []
      }))
      const availableRangeIds = new Set(getAllLeafRangeIds(trees.flatMap((tree) => tree.ranges)))

      rangeTrees.value = trees
      rangeNodeLoading.value = {}
      selectedRangeIds.value = selectedRangeIds.value.filter((id) => availableRangeIds.has(id))
    } catch (error) {
      console.error(error)
      rangeTrees.value = []
      rangeNodeLoading.value = {}
      selectedRangeIds.value = []
      selectedRangeGeoJson.value = emptyFeatureCollection()
    }
  }

  const setRangeNodeLoading = (rangeId, loading) => {
    rangeNodeLoading.value = {
      ...rangeNodeLoading.value,
      [rangeId]: loading === true
    }
  }

  // 統計區樹的節點展開時動態載入子節點（區→二級發布區→一級發布區→最小統計區）。
  const loadRangeChildren = async (rangeId) => {
    const target = findRangeNode(rangeRoots.value, rangeId)
    if (!target) return []
    return loadChildrenForNode(target)
  }

  onMounted(() => {
    loadRangesTree()
  })

  watch(selectedRangeRequest, loadSelectedRangeGeoJson, { deep: true })

  return {
    rangeTrees,
    selectedRangeIds,
    selectedRangeGeoJson,
    rangeNodeLoading,
    selectedRangeRequest,
    pickModeEnabled,
    pickLevel,
    loadRangesTree,
    loadRangeChildren,
    toggleRange,
    toggleRangeByFeature,
    toggleRangeByPoint,
    setPickModeEnabled,
    setPickLevel
  }
}
