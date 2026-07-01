<script setup>
import { Minus, Plus } from 'lucide-vue-next'
</script>

<template>
  <header class="top-toolbar">
    <h1>GIS 地圖編輯器</h1>
    <div class="zoom-controls">
      <button type="button" aria-label="縮小">
        <Minus :size="16" />
      </button>
      <span>100%</span>
      <button type="button" aria-label="放大">
        <Plus :size="16" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.top-toolbar {
  background: #15243a;
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.top-toolbar h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.zoom-controls {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.zoom-controls button,
.zoom-controls span {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #223652;
  color: #d6e4ff;
  min-width: 34px;
  height: 32px;
  padding: 0 10px;
  display: inline-grid;
  place-items: center;
  font-size: 13px;
  font-weight: 600;
}

.zoom-controls span {
  background: #1d2e47;
  color: #c9d9f2;
}

@media (max-width: 640px) {
  .top-toolbar {
    flex-wrap: wrap;
  }

  .zoom-controls {
    margin-left: 0;
  }
}
</style>
