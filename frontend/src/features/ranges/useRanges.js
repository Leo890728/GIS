import { computed, onMounted, ref, watch } from 'vue'
import { fetchRangeGeoJson, fetchRangeTree, fetchStatZoneChildren } from './rangeApi'
import {
  buildRangeRequest,
  emptyFeatureCollection,
  findRangeNode,
  getAllLeafRangeIds,
  getLeafRangeIds,
  normalizeRangeNode
} from './rangeTree'

export const useRanges = (apiBaseUrl) => {
  // [{ id, name, ranges: [...] }] — 行政區樹與統計區樹
  const rangeTrees = ref([])
  const selectedRangeIds = ref([])
  const selectedRangeGeoJson = ref(emptyFeatureCollection())
  const rangeNodeLoading = ref({})

  const rangeRoots = computed(() => rangeTrees.value.flatMap((tree) => tree.ranges))
  const selectedRangeRequest = computed(() => buildRangeRequest(rangeRoots.value, selectedRangeIds.value))

  let rangeRequestSequence = 0

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
    if (!target) return

    const childLevel = target?.metadata?.childLevel
    const childCount = Number(target?.metadata?.childCount || 0)
    const parentCode = String(target.code || '').trim()
    if (!childLevel || !parentCode || childCount <= 0) return
    if (target?.metadata?.childrenLoaded === true) return

    setRangeNodeLoading(rangeId, true)
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
      selectedRangeIds.value = [...selectedSet]
    } catch (error) {
      console.error(error)
    } finally {
      setRangeNodeLoading(rangeId, false)
    }
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
    loadRangesTree,
    loadRangeChildren,
    toggleRange
  }
}
