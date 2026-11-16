<template>
  <div class="dashboard">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <div class="stat-card health">
          <div class="stat-icon"><el-icon><Cpu /></el-icon></div>
          <div class="stat-content">
            <div class="stat-label">设备总数</div>
            <div class="stat-value">{{ stats.total_equipment }}</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card score">
          <div class="stat-icon"><el-icon><TrendCharts /></el-icon></div>
          <div class="stat-content">
            <div class="stat-label">平均健康分数</div>
            <div class="stat-value">{{ stats.avg_health_score }} <span class="unit">/ 100</span></div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card alert">
          <div class="stat-icon"><el-icon><Bell /></el-icon></div>
          <div class="stat-content">
            <div class="stat-label">未处理告警</div>
            <div class="stat-value">{{ stats.open_alerts }}</div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-card critical">
          <div class="stat-icon"><el-icon><WarningFilled /></el-icon></div>
          <div class="stat-content">
            <div class="stat-label">严重告警</div>
            <div class="stat-value critical">{{ stats.critical_alerts }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 左：设备健康矩阵 -->
      <el-col :span="14">
        <el-card class="dark-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><Grid /></el-icon> 设备健康矩阵</span>
              <el-tag size="small">实时</el-tag>
            </div>
          </template>
          <div class="equipment-grid">
            <div
              v-for="eq in stats.equipment_summary"
              :key="eq.id"
              class="equipment-tile"
              :class="getHealthClass(eq.health)"
              @click="$router.push(`/equipment/${eq.id}`)"
            >
              <div class="tile-code">{{ eq.code }}</div>
              <div class="tile-name">{{ eq.name }}</div>
              <div class="tile-score">
                <el-progress
                  :percentage="eq.health"
                  :color="getProgressColor(eq.health)"
                  :stroke-width="6"
                  :show-text="false"
                />
                <span class="score-num">{{ eq.health }}</span>
              </div>
              <div class="tile-status">
                <el-tag size="small" :type="getStatusTagType(eq.status)">
                  {{ eq.status }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右：最新告警 -->
      <el-col :span="10">
        <el-card class="dark-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><List /></el-icon> 最新告警</span>
              <el-button size="small" text @click="$router.push('/alerts')">查看全部 →</el-button>
            </div>
          </template>
          <div class="alert-list">
            <div v-for="a in stats.recent_alerts" :key="a.id" class="alert-item" @click="$router.push('/alerts')">
              <div class="alert-severity" :class="a.severity.toLowerCase()"></div>
              <div class="alert-info">
                <div class="alert-title">{{ a.title }}</div>
                <div class="alert-meta">
                  <el-tag size="small">{{ a.alert_type }}</el-tag>
                  <span>{{ formatTime(a.created_at) }}</span>
                  <el-tag size="small" :type="getSeverityType(a.severity)">{{ a.severity }}</el-tag>
                </div>
              </div>
            </div>
            <el-empty v-if="!stats.recent_alerts?.length" description="暂无告警" :image-size="60" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部：触发 Agent 分析 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="24">
        <el-card class="dark-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><MagicStick /></el-icon> 手动触发智能体分析</span>
              <el-tag size="small" type="warning">演示模式</el-tag>
            </div>
          </template>
          <div class="trigger-section">
            <el-select v-model="selectedEq" placeholder="选择设备" style="width: 200px">
              <el-option v-for="eq in stats.equipment_summary" :key="eq.code" :label="eq.code + ' - ' + eq.name" :value="eq.code" />
            </el-select>
            <el-button type="primary" :loading="analyzing" @click="runAnalysis">
              <el-icon><MagicStick /></el-icon> 触发完整分析（特征提取 + RAG + LLM）
            </el-button>
            <div class="analysis-result" v-if="lastResult">
              <el-alert
                :title="`分析完成 - ${lastResult.anomaly_level} 级异常，RUL: ${lastResult.rul?.rul_hours ?? 'N/A'} 小时`"
                :type="getAnalysisAlertType(lastResult.anomaly_level)"
                :description="lastResult.llm_analysis?.full_response?.substring(0, 200) + '...'"
                show-icon
                :closable="false"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDashboardStats, triggerAgentAnalysis } from '../api/client'

const stats = ref({
  total_equipment: 0,
  avg_health_score: 0,
  open_alerts: 0,
  critical_alerts: 0,
  equipment_summary: [],
  recent_alerts: [],
})
const selectedEq = ref('WT-GEAR-003')
const analyzing = ref(false)
const lastResult = ref(null)

onMounted(async () => {
  stats.value = await getDashboardStats()
})

const getHealthClass = (h) => {
  if (h >= 80) return 'healthy'
  if (h >= 60) return 'warning'
  if (h >= 40) return 'critical'
  return 'danger'
}
const getProgressColor = (h) => {
  if (h >= 80) return '#22c55e'
  if (h >= 60) return '#eab308'
  if (h >= 40) return '#f97316'
  return '#ef4444'
}
const getStatusTagType = (s) => ({ RUNNING: 'success', MAINTENANCE: 'warning', CRITICAL: 'danger', STOPPED: 'info' }[s] || 'info')
const getSeverityType = (s) => ({ LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }[s] || 'info')
const getAnalysisAlertType = (l) => ({ NONE: 'success', LOW: 'info', MEDIUM: 'warning', HIGH: 'warning', CRITICAL: 'error' }[l] || 'info')
const formatTime = (t) => t ? new Date(t).toLocaleString() : ''

const runAnalysis = async () => {
  analyzing.value = true
  try {
    lastResult.value = await triggerAgentAnalysis({ equipment_code: selectedEq.value, force_llm: true })
  } catch (e) {
    lastResult.value = { anomaly_level: 'ERROR', llm_analysis: { full_response: String(e) } }
  } finally {
    analyzing.value = false
  }
}
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.dark-card :deep(.el-card__header) { background: #334155; border-bottom: 1px solid #475569; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; align-items: center; color: #e2e8f0; }

.stat-cards { margin-bottom: 4px; }
.stat-card {
  background: #1e293b; border-radius: 10px; padding: 20px;
  display: flex; align-items: center; gap: 16px;
  border: 1px solid #334155; transition: transform 0.2s;
}
.stat-card:hover { transform: translateY(-2px); }
.stat-icon {
  width: 50px; height: 50px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; color: white;
}
.stat-card.health .stat-icon { background: linear-gradient(135deg, #3b82f6, #1d4ed8); }
.stat-card.score .stat-icon { background: linear-gradient(135deg, #22c55e, #15803d); }
.stat-card.alert .stat-icon { background: linear-gradient(135deg, #eab308, #a16207); }
.stat-card.critical .stat-icon { background: linear-gradient(135deg, #ef4444, #991b1b); }
.stat-label { color: #94a3b8; font-size: 13px; }
.stat-value { font-size: 28px; font-weight: 600; color: #f1f5f9; }
.stat-value.critical { color: #ef4444; }
.unit { font-size: 14px; color: #64748b; }

.equipment-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.equipment-tile {
  background: #0f172a; border-radius: 10px; padding: 14px; cursor: pointer;
  border: 2px solid #334155; transition: all 0.2s;
}
.equipment-tile:hover { border-color: #60a5fa; }
.equipment-tile.healthy { border-color: #166534; }
.equipment-tile.warning { border-color: #a16207; }
.equipment-tile.critical { border-color: #c2410c; }
.equipment-tile.danger { border-color: #991b1b; background: #450a0a; }
.tile-code { font-family: monospace; color: #60a5fa; font-size: 13px; }
.tile-name { color: #cbd5e1; font-size: 13px; margin-bottom: 8px; }
.tile-score { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tile-score .el-progress { flex: 1; }
.score-num { font-size: 12px; color: #e2e8f0; font-weight: 600; }
.tile-status { text-align: right; }

.alert-list { display: flex; flex-direction: column; gap: 8px; }
.alert-item { display: flex; gap: 12px; padding: 12px; background: #0f172a; border-radius: 8px; cursor: pointer; }
.alert-item:hover { background: #1e293b; }
.alert-severity { width: 4px; border-radius: 2px; }
.alert-severity.low { background: #3b82f6; }
.alert-severity.medium { background: #eab308; }
.alert-severity.high { background: #f97316; }
.alert-severity.critical { background: #ef4444; }
.alert-info { flex: 1; }
.alert-title { color: #e2e8f0; font-size: 14px; margin-bottom: 4px; }
.alert-meta { display: flex; gap: 8px; align-items: center; font-size: 12px; color: #64748b; }

.trigger-section { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.analysis-result { width: 100%; margin-top: 12px; }
</style>
