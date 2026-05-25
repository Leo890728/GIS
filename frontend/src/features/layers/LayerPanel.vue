<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle-layer'])

const layerDetailMap = {
  county: 'County Boundary',
  township: 'Township Boundary',
  village: 'Village Boundary'
}

const layerItems = computed(() =>
  Object.entries(props.layerState).map(([key, value]) => ({
    key,
    name: value.label,
    detail: layerDetailMap[key] || value.sourceLayer,
    enabled: value.active
  }))
)

const activeLayerCount = computed(() => layerItems.value.filter((item) => item.enabled).length)
</script>

<template>
  <section class="layers-panel">
    <div class="panel-title-row">
      <h3>Map Layers</h3>
      <span class="count-badge">{{ activeLayerCount }} active</span>
    </div>

    <article v-for="layer in layerItems" :key="layer.key" class="region-card expanded">
      <button class="region-row region-toggle" type="button" :aria-pressed="layer.enabled" @click="emit('toggle-layer', layer.key)">
        <div class="check-box" :class="{ selected: layer.enabled }">
          <Check v-if="layer.enabled" :size="10" />
        </div>
        <div class="region-label-wrap">
          <p class="region-name">{{ layer.name }}</p>
          <p class="region-meta">{{ layer.detail }}</p>
        </div>
      </button>
    </article>
  </section>
</template>
