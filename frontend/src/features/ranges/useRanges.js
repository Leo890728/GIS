import { computed, onMounted, ref, watch } from 'vue'
import { fetchRangeGeoJson, fetchRangeTree, fetchVillageStatZoneRanges } from './rangeApi'
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
  const rangeNodeLoading = ref({})

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
    const hasSelection =
      payload.countyCodes.length ||
      payload.townCodes.length ||
      payload.villageCodes.length ||
      payload.statZoneCodes.length

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
      rangeNodeLoading.value = {}
      selectedRangeIds.value = selectedRangeIds.value.filter((id) => availableRangeIds.has(id))
    } catch (error) {
      console.error(error)
      rangeTree.value = []
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

  const loadVillageStatZones = async (rangeId) => {
    const target = findRangeNode(rangeTree.value, rangeId)
    if (!target || target.level !== 'village') return

    const villageCode = String(target.code || '').trim()
    const statZoneCount = Number(target?.metadata?.statZoneCount || 0)
    if (!villageCode || statZoneCount <= 0) return
    if (target?.metadata?.statZoneLoaded === true) return

    setRangeNodeLoading(rangeId, true)
    try {
      const payload = await fetchVillageStatZoneRanges(apiBaseUrl, villageCode)
      const statZoneNodes = Array.isArray(payload?.ranges) ? payload.ranges.map(normalizeRangeNode) : []

      target.children = statZoneNodes
      target.metadata = {
        ...(target.metadata || {}),
        statZoneLoaded: true
      }

      const selectedSet = new Set(selectedRangeIds.value)
      if (selectedSet.has(target.id)) {
        selectedSet.delete(target.id)
        for (const child of statZoneNodes) {
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
    rangeTree,
    selectedRangeIds,
    selectedRangeGeoJson,
    rangeNodeLoading,
    selectedRangeRequest,
    loadRangesTree,
    loadVillageStatZones,
    toggleRange
  }
}
