<script setup>
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import RangeTreeNode from './RangeTreeNode.vue'
import { RANGE_PICK_LEVELS, getAllLeafRangeIds } from './rangeTree'

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
  },
  pickModeEnabled: {
    type: Boolean,
    default: false
  },
  pickLevel: {
    type: String,
    default: 'township'
  }
})

const emit = defineEmits(['toggle-range', 'expand-range', 'set-pick-mode-enabled', 'set-pick-level'])

const pickLevels = RANGE_PICK_LEVELS

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

    <article class="region-card expanded pick-card">
      <button
        class="region-row region-toggle"
        type="button"
        :aria-pressed="pickModeEnabled"
        @click="emit('set-pick-mode-enabled', !pickModeEnabled)"
      >
        <div class="switch-dot" :class="{ selected: pickModeEnabled }">
          <span class="switch-knob"></span>
        </div>
        <div class="region-label-wrap">
          <p class="region-name">地圖點選</p>
          <p class="region-meta">在地圖上點多邊形以加入/移除</p>
        </div>
      </button>

      <label class="pick-field-label" for="range-pick-level">邊界層級</label>
      <select
        id="range-pick-level"
        class="pick-select"
        :value="pickLevel"
        :disabled="!pickModeEnabled"
        @change="emit('set-pick-level', $event.target.value)"
      >
        <option v-for="opt in pickLevels" :key="opt.level" :value="opt.level">{{ opt.label }}</option>
      </select>
    </article>

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

<style scoped>
.pick-card {
  display: grid;
  gap: 8px;
}

.region-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
  text-align: left;
}

.switch-dot {
  width: 32px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid #3b82f6;
  background: #1b2b44;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-shrink: 0;
}

.switch-dot.selected {
  justify-content: flex-end;
}

.switch-knob {
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: #b9f3d2;
}

.pick-field-label {
  color: #b7d2f2;
  font-size: 10px;
  font-weight: 600;
}

.pick-select {
  border: 1px solid #35527c;
  border-radius: 6px;
  background: #0f1b2d;
  color: #eaf4ff;
  font-size: 11px;
  padding: 6px 8px;
  width: 100%;
}

.pick-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
