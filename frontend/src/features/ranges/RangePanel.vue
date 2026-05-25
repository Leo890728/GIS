<script setup>
import { computed } from 'vue'
import { ChevronDown, Minus } from 'lucide-vue-next'
import RangeTreeNode from './RangeTreeNode.vue'
import { getAllLeafRangeIds } from './rangeTree'

const props = defineProps({
  rangeTree: {
    type: Array,
    required: true
  },
  selectedRangeIds: {
    type: Array,
    required: true
  }
})

const emit = defineEmits(['toggle-range'])

const totalRangeLeafCount = computed(() => getAllLeafRangeIds(props.rangeTree).length)
const selectedRangeLeafCount = computed(() => props.selectedRangeIds.length)
</script>

<template>
  <section class="ranges-panel">
    <div class="panel-title-row">
      <h3>Ranges</h3>
      <span class="count-badge">{{ selectedRangeLeafCount }} / {{ totalRangeLeafCount }} selected</span>
    </div>

    <article class="region-card expanded">
      <header class="region-row">
        <div class="check-box selected">
          <Minus :size="10" />
        </div>
        <div class="region-label-wrap">
          <p class="region-name">All Ranges</p>
          <p class="region-meta">{{ selectedRangeLeafCount }}/{{ totalRangeLeafCount }} selected</p>
        </div>
        <ChevronDown class="caret" :size="14" />
      </header>

      <div class="county-list">
        <RangeTreeNode
          v-for="range in rangeTree"
          :key="range.id"
          :node="range"
          :selected-range-ids="selectedRangeIds"
          @toggle-range="emit('toggle-range', $event)"
        />
      </div>
    </article>
  </section>
</template>
