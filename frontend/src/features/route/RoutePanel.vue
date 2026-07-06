<script setup>
const props = defineProps({
  routeForm: {
    type: Object,
    required: true
  },
  routeRuntime: {
    type: Object,
    required: true
  },
  routeSummary: {
    type: Object,
    required: true
  },
  routeRows: {
    type: Array,
    required: true
  },
  droppedRows: {
    type: Array,
    required: true
  },
  pickMode: {
    type: String,
    default: ''
  },
  selectedRangeCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['update-route-field', 'set-pick-mode', 'solve-route', 'clear-route'])

const updateText = (key, event) => {
  emit('update-route-field', { key, value: event.target.value })
}

const updateNumber = (key, event) => {
  const value = Number(event.target.value)
  emit('update-route-field', { key, value: Number.isFinite(value) ? value : 0 })
}

const numberStepOptions = {
  demandMultiplierKg: { min: 0.001, step: 0.01 },
  vehicleCount: { min: 1, step: 1 },
  vehicleCapacityKg: { min: 1, step: 1 },
  solverTimeLimitSec: { min: 1, step: 1 },
  nodeLimit: { min: 1, step: 1 },
  aggregationCellMeters: { min: 10, step: 10 },
  aggregationThreshold: { min: 10, step: 10 },
  snapToRoadMaxDistanceMeters: { min: 0, step: 10 }
}

const decimalPlaces = (value) => {
  const text = String(value)
  return text.includes('.') ? text.split('.')[1].length : 0
}

const stepNumber = (key, direction) => {
  const options = numberStepOptions[key] || { step: 1 }
  const current = Number(props.routeForm[key])
  const base = Number.isFinite(current) ? current : options.min || 0
  const precision = Math.max(decimalPlaces(options.step), decimalPlaces(options.min || 0))
  let value = base + direction * options.step

  if (Number.isFinite(options.min)) value = Math.max(options.min, value)
  if (Number.isFinite(options.max)) value = Math.min(options.max, value)

  emit('update-route-field', { key, value: Number(value.toFixed(precision)) })
}

const updateCheckbox = (key, event) => {
  emit('update-route-field', { key, value: event.target.checked === true })
}

const setPickMode = (mode) => {
  emit('set-pick-mode', mode)
}

const stopTypeLabels = {
  start: '起點',
  end: '終點',
  pickup: '收運點',
  disposal: '處理場',
  dropped: '未排入'
}

const formatStopType = (value) => stopTypeLabels[value] || value

const formatMeters = (meters) => {
  if (typeof meters !== 'number' || !Number.isFinite(meters)) return ''
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`
}

// 指示掛在 leg 終點站上；此處要顯示「從本站往下一站」的走法，故取下一站的
// instructions 並濾掉「抵達目的地」。
const nextLegSteps = (route, idx) => {
  const steps = route?.stops?.[idx + 1]?.instructions || []
  return steps.filter((step) => step.type !== 'arrive')
}
</script>

<template>
  <section class="route-panel">
    <div class="panel-title-row">
      <h3>路線規劃</h3>
    </div>
    <p class="route-hint">已選範圍：{{ selectedRangeCount }}</p>

    <article class="route-card">
      <label class="field-label" for="route-node-mode">節點來源</label>
      <select
        id="route-node-mode"
        class="field-control"
        :value="routeForm.nodeSourceMode"
        @change="updateText('nodeSourceMode', $event)"
      >
        <option value="preset">預設</option>
        <option value="dataset">資料集</option>
      </select>

      <template v-if="routeForm.nodeSourceMode === 'preset'">
        <label class="field-label" for="route-preset">預設資料</label>
        <select
          id="route-preset"
          class="field-control"
          :value="routeForm.preset"
          @change="updateText('preset', $event)"
        >
          <option value="stat_zone_population_points">統計區人口點位</option>
        </select>
      </template>

      <template v-else>
        <label class="field-label" for="route-data-id">資料集 ID</label>
        <input
          id="route-data-id"
          class="field-control"
          type="text"
          :value="routeForm.datasetDataId"
          @input="updateText('datasetDataId', $event)"
        />
      </template>

      <div class="field-row">
        <div class="field-col">
          <label class="field-label" for="route-demand-field">需求欄位</label>
          <input
            id="route-demand-field"
            class="field-control"
            type="text"
            :value="routeForm.demandField"
            @input="updateText('demandField', $event)"
          />
        </div>
        <div class="field-col">
          <label class="field-label" for="route-demand-mul">換算倍率 (kg)</label>
          <div class="number-control">
            <input
              id="route-demand-mul"
              class="field-control number-control-input"
              type="number"
              min="0.001"
              step="0.01"
              :value="routeForm.demandMultiplierKg"
              @input="updateNumber('demandMultiplierKg', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加換算倍率" @click="stepNumber('demandMultiplierKg', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少換算倍率" @click="stepNumber('demandMultiplierKg', -1)">-</button>
            </div>
          </div>
        </div>
      </div>

      <div class="field-row">
        <div class="field-col">
          <label class="field-label" for="route-vehicle-count">車輛數</label>
          <div class="number-control">
            <input
              id="route-vehicle-count"
              class="field-control number-control-input"
              type="number"
              min="1"
              step="1"
              :value="routeForm.vehicleCount"
              @input="updateNumber('vehicleCount', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加車輛數" @click="stepNumber('vehicleCount', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少車輛數" @click="stepNumber('vehicleCount', -1)">-</button>
            </div>
          </div>
        </div>
        <div class="field-col">
          <label class="field-label" for="route-capacity">容量 (kg)</label>
          <div class="number-control">
            <input
              id="route-capacity"
              class="field-control number-control-input"
              type="number"
              min="1"
              step="1"
              :value="routeForm.vehicleCapacityKg"
              @input="updateNumber('vehicleCapacityKg', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加容量" @click="stepNumber('vehicleCapacityKg', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少容量" @click="stepNumber('vehicleCapacityKg', -1)">-</button>
            </div>
          </div>
        </div>
      </div>

      <div class="field-row">
        <div class="field-col">
          <label class="field-label" for="route-time-limit">求解時間上限 (秒)</label>
          <div class="number-control">
            <input
              id="route-time-limit"
              class="field-control number-control-input"
              type="number"
              min="1"
              step="1"
              :value="routeForm.solverTimeLimitSec"
              @input="updateNumber('solverTimeLimitSec', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加求解時間上限" @click="stepNumber('solverTimeLimitSec', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少求解時間上限" @click="stepNumber('solverTimeLimitSec', -1)">-</button>
            </div>
          </div>
        </div>
        <div class="field-col">
          <label class="field-label" for="route-limit">節點上限</label>
          <div class="number-control">
            <input
              id="route-limit"
              class="field-control number-control-input"
              type="number"
              min="1"
              step="1"
              :value="routeForm.nodeLimit"
              @input="updateNumber('nodeLimit', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加節點上限" @click="stepNumber('nodeLimit', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少節點上限" @click="stepNumber('nodeLimit', -1)">-</button>
            </div>
          </div>
        </div>
      </div>

      <label class="field-check">
        <input
          type="checkbox"
          :checked="routeForm.aggregationEnabled"
          @change="updateCheckbox('aggregationEnabled', $event)"
        />
        <span>啟用求解前聚合</span>
      </label>

      <div class="field-row">
        <div class="field-col">
          <label class="field-label" for="route-cell">網格大小 (m)</label>
          <div class="number-control">
            <input
              id="route-cell"
              class="field-control number-control-input"
              type="number"
              min="10"
              step="10"
              :value="routeForm.aggregationCellMeters"
              @input="updateNumber('aggregationCellMeters', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加網格大小" @click="stepNumber('aggregationCellMeters', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少網格大小" @click="stepNumber('aggregationCellMeters', -1)">-</button>
            </div>
          </div>
        </div>
        <div class="field-col">
          <label class="field-label" for="route-threshold">聚合門檻</label>
          <div class="number-control">
            <input
              id="route-threshold"
              class="field-control number-control-input"
              type="number"
              min="10"
              step="10"
              :value="routeForm.aggregationThreshold"
              @input="updateNumber('aggregationThreshold', $event)"
            />
            <div class="number-stepper">
              <button type="button" class="number-stepper-btn" aria-label="增加聚合門檻" @click="stepNumber('aggregationThreshold', 1)">+</button>
              <button type="button" class="number-stepper-btn" aria-label="減少聚合門檻" @click="stepNumber('aggregationThreshold', -1)">-</button>
            </div>
          </div>
        </div>
      </div>

      <label class="field-check">
        <input
          type="checkbox"
          :checked="routeForm.snapToRoadEnabled"
          @change="updateCheckbox('snapToRoadEnabled', $event)"
        />
        <span>將點位貼齊道路（聚合前與聚合後）</span>
      </label>

      <label class="field-label" for="route-snap-distance">貼齊道路最大距離 (m)</label>
      <div class="number-control">
        <input
          id="route-snap-distance"
          class="field-control number-control-input"
          type="number"
          min="0"
          step="10"
          :value="routeForm.snapToRoadMaxDistanceMeters"
          @input="updateNumber('snapToRoadMaxDistanceMeters', $event)"
        />
        <div class="number-stepper">
          <button type="button" class="number-stepper-btn" aria-label="增加貼齊道路最大距離" @click="stepNumber('snapToRoadMaxDistanceMeters', 1)">+</button>
          <button type="button" class="number-stepper-btn" aria-label="減少貼齊道路最大距離" @click="stepNumber('snapToRoadMaxDistanceMeters', -1)">-</button>
        </div>
      </div>

      <p class="field-note" :class="{ warn: selectedRangeCount === 0 }">
        {{ selectedRangeCount === 0 ? '請先在地圖上選取範圍才能求解' : `節點依地圖上已選取的範圍篩選（已選 ${selectedRangeCount} 個範圍）` }}
      </p>

      <div class="pick-row">
        <button
          class="pick-btn"
          type="button"
          :class="{ active: pickMode === 'start' }"
          @click="setPickMode(pickMode === 'start' ? '' : 'start')"
        >
          選取起點
        </button>
        <button
          class="pick-btn"
          type="button"
          :class="{ active: pickMode === 'end' }"
          @click="setPickMode(pickMode === 'end' ? '' : 'end')"
        >
          選取終點
        </button>
      </div>

      <p class="field-note">未選取起訖點時，自動使用最近的清潔隊作為起點與終點</p>

      <div class="coord-row">
        <p>起點：{{ routeForm.startCoord ? routeForm.startCoord.join(', ') : '自動（最近清潔隊）' }}</p>
        <p>終點：{{ routeForm.endCoord ? routeForm.endCoord.join(', ') : '自動（最近清潔隊）' }}</p>
      </div>

      <div class="action-row">
        <button
          class="primary-btn"
          type="button"
          :disabled="routeRuntime.loading || selectedRangeCount === 0"
          @click="emit('solve-route')"
        >
          {{ routeRuntime.loading ? '求解中...' : '求解路線' }}
        </button>
        <button class="secondary-btn" type="button" :disabled="routeRuntime.loading" @click="emit('clear-route')">
          清除
        </button>
      </div>

      <p v-if="routeRuntime.error" class="status error">{{ routeRuntime.error }}</p>
      <p v-else-if="routeRuntime.solvedAt" class="status">求解完成</p>
    </article>

    <article v-if="routeRows.length" class="route-card">
      <h4 class="sub-title">摘要</h4>
      <div class="summary-grid">
        <p>總距離：{{ routeSummary.totalDistanceM || 0 }} m</p>
        <p>總時間：{{ routeSummary.totalDurationS || 0 }} s</p>
        <p>總需求量：{{ routeSummary.totalDemandKg || 0 }} kg</p>
        <p>已服務需求量：{{ routeSummary.servedDemandKg || 0 }} kg</p>
        <p>未服務需求量：{{ routeSummary.droppedDemandKg || 0 }} kg</p>
        <p>使用車輛：{{ routeSummary.vehicleUsed || 0 }}</p>
      </div>

      <h4 class="sub-title">路線停靠點</h4>
      <div v-for="route in routeRows" :key="route.vehicle_id" class="route-block">
        <p class="route-name">{{ route.vehicle_id }} / {{ route.distance_m }} m / {{ route.duration_s }} s</p>
        <ol class="stop-list">
          <li v-for="(stop, idx) in route.stops" :key="`${route.vehicle_id}-${idx}`" class="stop-row">
            <span>{{ idx + 1 }}. [{{ formatStopType(stop.type) }}] {{ stop.name }} / 載重 {{ stop.load_kg }} kg</span>
            <ol v-if="nextLegSteps(route, idx).length" class="nav-list">
              <li v-for="(step, stepIdx) in nextLegSteps(route, idx)" :key="stepIdx" class="nav-step">
                <span class="nav-text">{{ step.text }}</span>
                <span v-if="formatMeters(step.distance_m)" class="nav-dist">{{ formatMeters(step.distance_m) }}</span>
              </li>
            </ol>
          </li>
        </ol>
      </div>

      <template v-if="droppedRows.length">
        <h4 class="sub-title">未排入節點</h4>
        <ul class="stop-list">
          <li v-for="node in droppedRows" :key="node.id" class="stop-row">
            {{ node.name }} / {{ node.demandKg }} kg
          </li>
        </ul>
      </template>
    </article>
  </section>
</template>

<style scoped>
.route-panel {
  display: grid;
  gap: 8px;
  padding-right: 4px;
}

.panel-title-row h3 {
  margin: 0;
  color: #eaf4ff;
  font-size: 14px;
  font-weight: 700;
}

.route-hint {
  margin: 0;
  font-size: 10px;
  color: #9fc5f8;
}

.route-card {
  border-radius: 8px;
  border: 1px solid #2a3a54;
  background: #122139;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.field-col {
  display: grid;
  gap: 4px;
}

.field-label {
  color: #b7d2f2;
  font-size: 10px;
  font-weight: 600;
}

.field-control {
  border: 1px solid #35527c;
  border-radius: 6px;
  background: #0f1b2d;
  color: #eaf4ff;
  font-size: 11px;
  padding: 6px 8px;
  width: 100%;
}

.number-control {
  position: relative;
  min-width: 0;
  width: 100%;
}

.number-control-input {
  appearance: textfield;
  -moz-appearance: textfield;
  padding-right: 30px;
}

.number-control-input::-webkit-inner-spin-button,
.number-control-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.number-stepper {
  position: absolute;
  top: 1px;
  right: 1px;
  bottom: 1px;
  display: grid;
  grid-template-rows: 1fr 1fr;
  width: 22px;
  overflow: hidden;
  border-left: 1px solid #294567;
  border-radius: 0 5px 5px 0;
}

.number-stepper-btn {
  display: grid;
  place-items: center;
  min-width: 0;
  border: 0;
  background: #162b47;
  color: #bfe0ff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
}

.number-stepper-btn + .number-stepper-btn {
  border-top: 1px solid #294567;
}

.number-stepper-btn:hover {
  background: #1d3d66;
  color: #ffffff;
}

.number-stepper-btn:active {
  background: #28518a;
}

.number-stepper-btn:focus-visible {
  outline: 1px solid #7cb9ff;
  outline-offset: -2px;
}

.field-note {
  margin: 0;
  font-size: 10px;
  color: #9fc5f8;
}

.field-note.warn {
  color: #ffb3ad;
}

.field-check {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #d1e4ff;
  font-size: 11px;
}

.pick-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.pick-btn,
.primary-btn,
.secondary-btn {
  border-radius: 6px;
  border: 1px solid #35527c;
  background: #17355b;
  color: #eaf4ff;
  font-size: 11px;
  font-weight: 600;
  padding: 7px 8px;
}

.pick-btn.active {
  border-color: #7cb9ff;
  background: #28518a;
}

.coord-row {
  display: grid;
  gap: 2px;
  font-size: 10px;
  color: #bfd7f8;
}

.coord-row p {
  margin: 0;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

.secondary-btn {
  background: #102038;
}

.status {
  margin: 0;
  color: #bde1ff;
  font-size: 10px;
}

.status.error {
  color: #ffb3ad;
}

.sub-title {
  margin: 0;
  color: #dfefff;
  font-size: 12px;
  font-weight: 700;
}

.summary-grid {
  display: grid;
  gap: 2px;
  color: #c6dcff;
  font-size: 10px;
}

.summary-grid p {
  margin: 0;
}

.route-block {
  border: 1px solid #274066;
  border-radius: 6px;
  padding: 6px;
  display: grid;
  gap: 4px;
}

.route-name {
  margin: 0;
  color: #f4e3a5;
  font-size: 10px;
  font-weight: 700;
}

.stop-list {
  margin: 0;
  padding-left: 16px;
  display: grid;
  gap: 2px;
}

.stop-row {
  color: #d1e4ff;
  font-size: 10px;
}

.nav-list {
  margin: 2px 0 4px 8px;
  padding-left: 14px;
  display: grid;
  gap: 1px;
  list-style: decimal;
  border-left: 1px solid #274363;
}

.nav-step {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  color: #a9c4e6;
  font-size: 9px;
}

.nav-dist {
  flex: none;
  color: #7f9dc0;
}
</style>
