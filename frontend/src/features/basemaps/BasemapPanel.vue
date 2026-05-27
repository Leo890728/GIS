<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  basemapState: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['set-basemap'])

const basemapItems = computed(() =>
  Object.entries(props.basemapState).map(([key, value]) => ({
    key,
    name: value.label || key,
    detail: value.detail || '',
    enabled: value.active === true
  }))
)

const activeCount = computed(() => basemapItems.value.filter((item) => item.enabled).length)
</script>

<template>
  <section class="layers-panel">
    <div class="panel-title-row">
      <h3>Basemap</h3>
      <span class="count-badge">{{ activeCount }} active</span>
    </div>

    <article v-for="item in basemapItems" :key="item.key" class="region-card expanded">
      <button
        class="region-row region-toggle"
        type="button"
        :aria-pressed="item.enabled"
        @click="emit('set-basemap', item.key)"
      >
        <div class="check-box" :class="{ selected: item.enabled }">
          <Check v-if="item.enabled" :size="10" />
        </div>
        <div class="region-label-wrap">
          <p class="region-name">{{ item.name }}</p>
          <p class="region-meta">{{ item.detail }}</p>
        </div>
      </button>
    </article>
  </section>
</template>
