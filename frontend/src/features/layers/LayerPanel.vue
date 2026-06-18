<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  layerState: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['toggle-layer', 'update-layer-style'])

const layerDetailMap = {
  county: 'County Boundary',
  township: 'Township Boundary',
  village: 'Village Boundary',
  stat_zone: '最小統計區',
  stat_zone_1: '一級發布區',
  stat_zone_2: '二級發布區'
}

const layerItems = computed(() =>
  Object.entries(props.layerState).map(([key, value]) => ({
    key,
    name: value.label,
    detail: layerDetailMap[key] || value.sourceLayer,
    enabled: value.active,
    color: value.color || '#57a6f5',
    lineWidthScale: Number(value.lineWidthScale || 1)
  }))
)

const activeLayerCount = computed(() => layerItems.value.filter((item) => item.enabled).length)

const handleColorInput = (key, event) => {
  const value = event?.target?.value
  if (!value) return
  emit('update-layer-style', { key, color: value })
}

const handleWidthInput = (key, event) => {
  const value = Number(event?.target?.value)
  if (!Number.isFinite(value)) return
  emit('update-layer-style', { key, lineWidthScale: value })
}
</script>

<template>
  <section class="layers-panel">
    <div class="panel-title-row">
      <h3>Boundary</h3>
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
      <div class="layer-style-controls">
        <label class="style-field">
          <span class="style-label">Color</span>
          <input
            class="color-picker"
            type="color"
            :value="layer.color"
            @input="handleColorInput(layer.key, $event)"
          >
        </label>
        <label class="style-field width-field">
          <span class="style-label">Width {{ layer.lineWidthScale.toFixed(1) }}x</span>
          <input
            class="width-slider"
            type="range"
            min="0.4"
            max="3"
            step="0.1"
            :value="layer.lineWidthScale"
            @input="handleWidthInput(layer.key, $event)"
          >
        </label>
      </div>
    </article>
  </section>
</template>

<style scoped>
.layer-style-controls {
  margin-top: 8px;
  display: grid;
  gap: 8px;
}

.style-field {
  display: grid;
  grid-template-columns: 48px 1fr;
  align-items: center;
  gap: 8px;
}

.width-field {
  grid-template-columns: 88px 1fr;
}

.style-label {
  color: #9fb7da;
  font-size: 10px;
  font-weight: 600;
}

.color-picker {
  width: 100%;
  min-width: 48px;
  height: 26px;
  border: 1px solid #3a5274;
  border-radius: 6px;
  background: #17273f;
  padding: 2px;
}

.width-slider {
  width: 100%;
}
</style>
