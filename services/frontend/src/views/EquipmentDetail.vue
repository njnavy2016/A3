<template>
  <div class="detail-page">
    <div v-if="equipment">
      <!-- 顶部信息 -->
      <el-card class="dark-card" style="margin-bottom: 16px">
        <div class="detail-header">
          <div>
            <h2 class="title"><code>{{ equipment.equipment_code }}</code> · {{ equipment.name }}</h2>
            <div class="sub">{{ equipment.model }} / {{ equipment.manufacturer }} · {{ equipment.location }}</div>
          </div>
          <div class="health-box">
            <el-progress type="dashboard" :percentage="equipment.health_score" :width="120" :color="getHealthColor(equipment.health_score)">
              <template #default="{ percentage }">
                <div class="health-num">{{ percentage }}</div>
                <div class="health-label">健康</div>
              </template>
            </el-progress>
          </div>
        </div>
      </el-card>

      <!-- 传感器曲线图 -->
      <el-card class="dark-card">
        <template #header>
          <div class="card-header">
            <span><el-icon><TrendCharts /></el-icon> 实时传感器曲线（最近 6 小时）</span>
            <div class="sensors-filter">
              <el-select v-model="selectedSensors" multiple placeholder="选择传感器" style="min-width: 300px">
                <el-option v-for="s in sensors" :key="s.id" :label="`${s.sensor_code} (${s.unit || ''})`" :value="s.sensor_code" />
              </el-select>
            </div>
          </div>
        </template>
        <div ref="chartRef" class="chart-container"></div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getEquipment, getEquipmentSensors, getSensorRealtime } from '../api/client'

const props = defineProps({ id: String })
const id = () => props.id || location.hash.split('/').pop()

const equipment = ref(null)
const sensors = ref([])
const selectedSensors = ref([])
const chartRef = ref(null)
let chart = null

onMounted(async () => {
  const eid = location.hash.split('/').pop()
  equipment.value = await getEquipment(eid)
  sensors.value = await getEquipmentSensors(eid)
  // 默认选第一个振动 + 温度 + 油壓
  selectedSensors.value = sensors.value.slice(0, 3).map(s => s.sensor_code)
  
  await nextTick()
  chart = echarts.init(chartRef.value, 'dark')
  await loadDataAndRender()
  
  setInterval(loadDataAndRender, 30000)
})

watch(selectedSensors, loadDataAndRender)

const loadDataAndRender = async () => {
  if (!sensors.value.length) return
  const series = []
  const allTimestamps = new Set()
  
  for (const code of selectedSensors.value) {
    const sensor = sensors.value.find(s => s.sensor_code === code)
    if (!sensor) continue
    
    const data = await getSensorRealtime(sensor.id)
    const points = data.points || []
    
    for (const p of points) allTimestamps.add(p.ts)
    
    series.push({
      name: code,
      type: 'line',
      smooth: true,
      data: points.map(p => [p.ts, p.value]),
      itemStyle: { opacity: 0.7 },
      lineStyle: { width: 2 },
    })
  }
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: selectedSensors.value, textStyle: { color: '#94a3b8' } },
    grid: { top: 50, bottom: 30, left: 50, right: 30 },
    xAxis: { type: 'time', axisLine: { lineStyle: { color: '#475569' } }, axisLabel: { color: '#94a3b8' } },
    yAxis: { axisLine: { lineStyle: { color: '#475569' } }, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#334155' } } },
    series,
  }
  chart?.setOption(option)
}

const getHealthColor = (h) => h >= 80 ? '#22c55e' : h >= 60 ? '#eab308' : h >= 40 ? '#f97316' : '#ef4444'
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }

.detail-header { display: flex; justify-content: space-between; align-items: center; }
.title { margin: 0; color: #f1f5f9; font-size: 20px; }
.title code { color: #60a5fa; }
.sub { color: #64748b; font-size: 13px; margin-top: 6px; }

.health-num { font-size: 24px; font-weight: 700; color: #e2e8f0; }
.health-label { font-size: 11px; color: #94a3b8; }

.chart-container { width: 100%; height: 450px; }
</style>
