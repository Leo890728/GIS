<script setup>
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import RangeTreeNode from './RangeTreeNode.vue'
import { getAllLeafRangeIds } from './rangeTree'

const props = defineProps({
  rangeTrees: {
    type: Array,
    required: true
  },
  selectedRangeIds: {
    type: Array,
    required: true
  },
  rangeNodeLoading: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['toggle-range', 'expand-range'])

const collapsedTrees = ref({})

const toggleTree = (treeId) => {
  collapsedTrees.value = {
    ...collapsedTrees.value,
    [treeId]: !collapsedTrees.value[treeId]
  }
}

const selectedSet = computed(() => new Set(props.selectedRangeIds))

const treeSummaries = computed(() =>
  props.rangeTrees.map((tree) => {
    const leafIds = getAllLeafRangeIds(tree.ranges)
    return {
      total: leafIds.length,
      selected: leafIds.filter((id) => selectedSet.value.has(id)).length
    }
  })
)

const selectedRangeLeafCount = computed(() => props.selectedRangeIds.length)
</script>

<template>
  <section class="ranges-panel">
    <div class="panel-title-row">
      <h3>範圍</h3>
      <span class="count-badge">{{ selectedRangeLeafCount }} 已選取</span>
    </div>

    <article
      v-for="(tree, index) in rangeTrees"
      :key="tree.id"
      class="region-card"
      :class="{ expanded: !collapsedTrees[tree.id] }"
    >
      <header class="region-row">
        <button class="range-label-btn" type="button" @click="toggleTree(tree.id)">
          <div class="region-label-wrap">
            <p class="region-name">{{ tree.name }}</p>
            <p class="region-meta">
              {{ treeSummaries[index].selected }}/{{ treeSummaries[index].total }} 已選取
            </p>
          </div>
          <ChevronDown v-if="!collapsedTrees[tree.id]" class="caret" :size="14" />
          <ChevronRight v-else class="caret" :size="14" />
        </button>
      </header>

      <div v-if="!collapsedTrees[tree.id]" class="county-list">
        <RangeTreeNode
          v-for="range in tree.ranges"
          :key="range.id"
          :node="range"
          :selected-range-ids="selectedRangeIds"
          :range-node-loading="rangeNodeLoading"
          @toggle-range="emit('toggle-range', $event)"
          @expand-range="emit('expand-range', $event)"
        />
      </div>
    </article>
  </section>
</template>
