<script setup>
import { computed } from 'vue'
import { Pause, Play, SkipBack, SkipForward, X } from 'lucide-vue-next'

const props = defineProps({
  simulatorState: {
    type: Object,
    required: true
  },
  simulatorSpeeds: {
    type: Array,
    default: () => [1, 10, 30, 60]
  }
})

const emit = defineEmits(['set-time', 'toggle-play', 'set-speed', 'step', 'toggle-smooth', 'stop'])

const fmt = (ms) => {
  if (ms == null) return '--'
  const d = new Date(ms)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString([], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const sliderStep = computed(() => Math.max(1000, (Number(props.simulatorState.intervalSeconds) || 60) * 1000))
</script>

<template>
  <div class="sim-bar">
    <div class="sim-bar-controls">
      <button class="sim-bar-btn" type="button" aria-label="Previous frame" @click="emit('step', -1)">
        <SkipBack :size="16" />
      </button>
      <button
        class="sim-bar-btn play"
        type="button"
        :aria-label="simulatorState.playing ? 'Pause' : 'Play'"
        @click="emit('toggle-play')"
      >
        <Pause v-if="simulatorState.playing" :size="18" />
        <Play v-else :size="18" />
      </button>
      <button class="sim-bar-btn" type="button" aria-label="Next frame" @click="emit('step', 1)">
        <SkipForward :size="16" />
      </button>
    </div>

    <div class="sim-bar-timeline">
      <span class="sim-bar-time">{{ fmt(simulatorState.currentTime) }}</span>
      <input
        class="sim-bar-slider"
        type="range"
        :min="simulatorState.from"
        :max="simulatorState.to"
        :step="sliderStep"
        :value="simulatorState.currentTime ?? simulatorState.to"
        @input="emit('set-time', Number($event.target.value))"
      />
      <span class="sim-bar-bound">{{ fmt(simulatorState.to) }}</span>
    </div>

    <div class="sim-bar-right">
      <div class="sim-bar-speeds">
        <button
          v-for="speed in simulatorSpeeds"
          :key="speed"
          class="sim-bar-speed"
          :class="{ active: simulatorState.speed === speed }"
          type="button"
          @click="emit('set-speed', speed)"
        >
          {{ speed }}×
        </button>
      </div>
      <button
        class="sim-bar-smooth"
        :class="{ active: simulatorState.smooth }"
        type="button"
        title="Road smoothing (OSRM)"
        @click="emit('toggle-smooth')"
      >
        OSRM
      </button>
      <span v-if="simulatorState.loading" class="sim-bar-loading">…</span>
      <button class="sim-bar-exit" type="button" aria-label="Exit playback" @click="emit('stop')">
        <X :size="16" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.sim-bar {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(880px, calc(100% - 48px));
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  border-radius: 12px;
  background: rgb(13 20 33 / 92%);
  border: 1px solid #2d4161;
  box-shadow: 0 8px 24px rgb(0 0 0 / 35%);
  z-index: 5;
}

.sim-bar-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-bar-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #d6e6ff;
  cursor: pointer;
}

.sim-bar-btn.play {
  width: 40px;
  height: 32px;
  background: #2a4d7a;
  border-color: #5fa3e3;
  color: #eaf4ff;
}

.sim-bar-timeline {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.sim-bar-time {
  font-size: 12px;
  font-weight: 700;
  color: #f4e3a5;
  white-space: nowrap;
}

.sim-bar-bound {
  font-size: 10px;
  color: #9fb7da;
  white-space: nowrap;
}

.sim-bar-slider {
  flex: 1;
  min-width: 0;
  accent-color: #5fa3e3;
}

.sim-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-bar-speeds {
  display: flex;
  gap: 4px;
}

.sim-bar-speed {
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 7px;
  cursor: pointer;
}

.sim-bar-speed.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-bar-smooth {
  border-radius: 6px;
  border: 1px solid #2a3a54;
  background: #1a2940;
  color: #9fb7da;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 8px;
  cursor: pointer;
}

.sim-bar-smooth.active {
  border-color: #5fa3e3;
  background: #2a4d7a;
  color: #eaf4ff;
}

.sim-bar-loading {
  color: #88a4c8;
  font-size: 14px;
}

.sim-bar-exit {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #5a3540;
  background: #2a1a22;
  color: #ffb3ad;
  cursor: pointer;
}

@media (max-width: 720px) {
  .sim-bar {
    flex-wrap: wrap;
    gap: 8px;
  }
  .sim-bar-timeline {
    order: 3;
    flex-basis: 100%;
  }
}
</style>
