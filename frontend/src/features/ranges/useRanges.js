import { computed, onMounted, ref, watch } from 'vue'
import { fetchRangeGeoJson, fetchRangeTree } from './rangeApi'
import {
  buildRangeRequest,
  emptyFeatureCollection,
  findRangeNode,
  getAllLeafRangeIds,
  getLeafRangeIds,
  normalizeRangeNode
} from './rangeTree'

export const useRanges = (apiBaseUrl) => {
  const rangeTree = ref([])
  const selectedRangeIds = ref([])
  const selectedRangeGeoJson = ref(emptyFeatureCollection())

  const selectedRangeRequest = computed(() => buildRangeRequest(rangeTree.value, selectedRangeIds.value))

  let rangeRequestSequence = 0

  const toggleRange = (rangeId) => {
    const target = findRangeNode(rangeTree.value, rangeId)
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
    const hasSelection = payload.countyCodes.length || payload.townCodes.length || payload.villageCodes.length

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
      const tree = Array.isArray(payload?.ranges) ? payload.ranges.map(normalizeRangeNode) : []
      const availableRangeIds = new Set(getAllLeafRangeIds(tree))

      rangeTree.value = tree
      selectedRangeIds.value = selectedRangeIds.value.filter((id) => availableRangeIds.has(id))
    } catch (error) {
      console.error(error)
      rangeTree.value = []
      selectedRangeIds.value = []
      selectedRangeGeoJson.value = emptyFeatureCollection()
    }
  }

  onMounted(() => {
    loadRangesTree()
  })

  watch(selectedRangeRequest, loadSelectedRangeGeoJson, { deep: true })

  return {
    rangeTree,
    selectedRangeIds,
    selectedRangeGeoJson,
    selectedRangeRequest,
    loadRangesTree,
    toggleRange
  }
}
