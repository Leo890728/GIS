<script setup>
import { computed, ref } from 'vue'
import { Check, ChevronDown, ChevronRight, Ellipsis, Minus } from 'lucide-vue-next'
import { getLeafRangeIds, getRangeChildren } from './rangeTree'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  selectedRangeIds: {
    type: Array,
    required: true
  },
  rangeNodeLoading: {
    type: Object,
    default: () => ({})
  },
  depth: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['toggle-range', 'expand-range'])

const CHILD_LEVEL_LABELS = {
  stat_zone_2: '二級發布區',
  stat_zone_1: '一級發布區',
  stat_zone: '最小統計區'
}

const expanded = ref(false)
const selectedSet = computed(() => new Set(props.selectedRangeIds))
const children = computed(() => getRangeChildren(props.node))
const leafIds = computed(() => getLeafRangeIds(props.node))
const selectedLeafCount = computed(() => leafIds.value.filter((id) => selectedSet.value.has(id)).length)
const isFullySelected = computed(() => leafIds.value.length > 0 && leafIds.value.every((id) => selectedSet.value.has(id)))
const isPartiallySelected = computed(() => selectedLeafCount.value > 0 && !isFullySelected.value)
const lazyChildLevel = computed(() => props.node?.metadata?.childLevel || '')
const lazyChildCount = computed(() => Number(props.node?.metadata?.childCount || 0))
const hasLazyChildren = computed(
  () => lazyChildLevel.value !== '' && lazyChildCount.value > 0 && props.node?.metadata?.childrenLoaded !== true
)
const hasChildren = computed(() => children.value.length > 0 || hasLazyChildren.value)
const isLoadingChildren = computed(() => props.rangeNodeLoading?.[props.node.id] === true)

const rangeMeta = computed(() => {
  if (lazyChildLevel.value) {
    return `${lazyChildCount.value} 個${CHILD_LEVEL_LABELS[lazyChildLevel.value] || '子範圍'}`
  }
  if (props.node.level === 'county') {
    return `${children.value.length} 個鄉鎮市區`
  }
  if (props.node.level === 'township') {
    return `${children.value.length} 個村里`
  }
  return `${selectedLeafCount.value}/${leafIds.value.length} 已選取`
})

const leafMeta = computed(() => {
  if (props.node.level === 'stat_zone' && props.node.description) {
    return props.node.description
  }
  return props.node.code || '無代碼'
})

const nodeClass = computed(() => {
  if (props.depth === 0) return 'county-card'
  if (props.depth === 1) return 'township-card'
  return 'county-card'
})

const rowClass = computed(() => {
  if (props.depth === 0) return 'county-row'
  return 'township-row'
})

const toggleExpand = () => {
  const nextExpanded = !expanded.value
  expanded.value = nextExpanded

  if (nextExpanded && hasLazyChildren.value) {
    emit('expand-range', props.node.id)
  }
}
</script>

<template>
  <article v-if="hasChildren" :class="nodeClass">
    <div :class="rowClass">
      <button
        class="check-box"
        type="button"
        :class="{ selected: isFullySelected, partial: isPartiallySelected }"
        :aria-pressed="isFullySelected"
        @click="emit('toggle-range', node.id)"
      >
        <Check v-if="isFullySelected" :size="10" />
        <Minus v-else-if="isPartiallySelected" :size="10" />
      </button>

      <button
        v-if="hasChildren"
        class="range-label-btn"
        type="button"
        @click="toggleExpand"
      >
        <span class="range-color-dot" :style="{ backgroundColor: node.color }"></span>
        <div class="region-label-wrap">
          <p class="region-name" :class="{ sub: depth > 0 }">{{ node.name }}</p>
          <p class="region-meta">{{ isLoadingChildren ? '載入中...' : rangeMeta }}</p>
        </div>
        <ChevronDown v-if="expanded" class="caret" :size="14" />
        <ChevronRight v-else class="caret" :size="14" />
      </button>
    </div>

    <div v-if="expanded" class="range-children" :class="{ nested: depth > 0 }">
      <RangeTreeNode
        v-for="child in children"
        :key="child.id"
        :node="child"
        :selected-range-ids="selectedRangeIds"
        :range-node-loading="rangeNodeLoading"
        :depth="depth + 1"
        @toggle-range="emit('toggle-range', $event)"
        @expand-range="emit('expand-range', $event)"
      />
    </div>
  </article>

  <button
    v-else
    class="district-row district-toggle"
    type="button"
    :class="{ off: !isFullySelected }"
    :aria-pressed="isFullySelected"
    @click="emit('toggle-range', node.id)"
  >
    <span class="check-box" :class="{ selected: isFullySelected }">
      <Check v-if="isFullySelected" :size="10" />
    </span>
    <span class="range-color-dot" :style="{ backgroundColor: node.color }"></span>
    <div class="region-label-wrap">
      <p class="region-name sub">{{ node.name }}</p>
      <p class="region-meta">{{ leafMeta }}</p>
    </div>
    <Ellipsis class="more" :size="14" />
  </button>
</template>
