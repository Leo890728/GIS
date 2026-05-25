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
  depth: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['toggle-range'])

const expanded = ref(false)
const selectedSet = computed(() => new Set(props.selectedRangeIds))
const children = computed(() => getRangeChildren(props.node))
const leafIds = computed(() => getLeafRangeIds(props.node))
const selectedLeafCount = computed(() => leafIds.value.filter((id) => selectedSet.value.has(id)).length)
const isFullySelected = computed(() => leafIds.value.length > 0 && leafIds.value.every((id) => selectedSet.value.has(id)))
const isPartiallySelected = computed(() => selectedLeafCount.value > 0 && !isFullySelected.value)
const hasChildren = computed(() => children.value.length > 0)

const rangeMeta = computed(() => {
  if (leafIds.value.length > 1) {
    return `${selectedLeafCount.value}/${leafIds.value.length} ${props.node.level || 'range'}`
  }
  return props.node.code || props.node.level || 'range'
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
        @click="expanded = !expanded"
      >
        <span class="range-color-dot" :style="{ backgroundColor: node.color }"></span>
        <div class="region-label-wrap">
          <p class="region-name" :class="{ sub: depth > 0 }">{{ node.name }}</p>
          <p class="region-meta">{{ rangeMeta }}</p>
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
        :depth="depth + 1"
        @toggle-range="emit('toggle-range', $event)"
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
      <p class="region-meta">{{ node.code || 'N/A' }}</p>
    </div>
    <Ellipsis class="more" :size="14" />
  </button>
</template>
