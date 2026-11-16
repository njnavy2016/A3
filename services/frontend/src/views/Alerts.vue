<template>
  <div class="alerts-page">
    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Bell /></el-icon> 告警中心</span>
          <div class="filters">
            <el-select v-model="filterSeverity" placeholder="严重等级" clearable size="small">
              <el-option label="LOW" value="LOW" />
              <el-option label="MEDIUM" value="MEDIUM" />
              <el-option label="HIGH" value="HIGH" />
              <el-option label="CRITICAL" value="CRITICAL" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="状态" clearable size="small">
              <el-option label="OPEN" value="OPEN" />
              <el-option label="ACKNOWLEDGED" value="ACKNOWLEDGED" />
              <el-option label="RESOLVED" value="RESOLVED" />
            </el-select>
            <el-button type="primary" size="small" @click="loadAlerts">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="alerts" stripe class="dark-table" style="width: 100%">
        <el-table-column label="等级" width="90">
          <template #default="{ row }">
            <div class="severity-badge" :class="row.severity.toLowerCase()">
              {{ row.severity }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120" prop="alert_type">
          <template #default="{ row }">
            <el-tag size="small">{{ row.alert_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标题" prop="title" min-width="250">
          <template #default="{ row }">
            <div class="alert-title">{{ row.title }}</div>
            <div class="alert-desc">{{ row.description }}</div>
          </template>
        </el-table-column>
        <el-table-column label="RUL(小时)" width="100">
          <template #default="{ row }">
            <span v-if="row.rul_hours" :class="getRulClass(row.rul_hours)">
              {{ row.rul_hours }}
            </span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="风险评分" width="100">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.risk_score || 0)"
              :color="getProgressColor(row.risk_score || 0)"
              :show-text="false"
              :stroke-width="8"
              style="width: 80px"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="dark">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            <span class="muted">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
            <el-button size="small" type="warning" @click="acknowledge(row)" v-if="row.status === 'OPEN'">确认</el-button>
            <el-button size="small" type="success" @click="resolve(row)" v-if="row.status !== 'RESOLVED'">解决</el-button>
            <el-button size="small" type="primary" :loading="analyzingId === row.id" @click="analyze(row)">
              智能体分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 告警详情对话框 -->
    <el-dialog v-model="detailVisible" :title="currentAlert?.title" width="70%" class="dark-dialog">
      <div v-if="currentAlert" class="alert-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="严重等级">{{ currentAlert.severity }}</el-descriptions-item>
          <el-descriptions-item label="告警类型">{{ currentAlert.alert_type }}</el-descriptions-item>
          <el-descriptions-item label="RUL">{{ currentAlert.rul_hours }} 小时</el-descriptions-item>
          <el-descriptions-item label="风险评分">{{ currentAlert.risk_score }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ currentAlert.status }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(currentAlert.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title"><el-icon><ChatDotRound /></el-icon> 智能体诊断</h4>
        <div class="diag-box">
          <div class="diag-text">{{ currentAlert.agent_diagnosis || '（无智能体诊断）' }}</div>
        </div>

        <h4 class="section-title"><el-icon><Connection /></el-icon> 根因分析链 (RCA)</h4>
        <div class="rca-box">
          <pre>{{ formatRCA(currentAlert.agent_rca) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { listAlerts, acknowledgeAlert, resolveAlert, triggerAgentAnalysis } from '../api/client'

const alerts = ref([])
const filterSeverity = ref('')
const filterStatus = ref('')
const detailVisible = ref(false)
const currentAlert = ref(null)
const analyzingId = ref(null)

const loadAlerts = async () => {
  const params = {}
  if (filterSeverity.value) params.severity = filterSeverity.value
  if (filterStatus.value) params.status = filterStatus.value
  alerts.value = await listAlerts(params)
}

const filteredAlerts = computed(() => alerts.value)

const showDetail = (row) => { currentAlert.value = row; detailVisible.value = true }
const acknowledge = async (row) => { await acknowledgeAlert(row.id); loadAlerts() }
const resolve = async (row) => { await resolveAlert(row.id); loadAlerts() }
const analyze = async (row) => {
  analyzingId.value = row.id
  try {
    await triggerAgentAnalysis({ equipment_id: row.equipment_id })
    await loadAlerts()
  } finally {
    analyzingId.value = null
  }
}

const getProgressColor = (v) => {
  if (v >= 70) return '#ef4444'
  if (v >= 50) return '#f97316'
  if (v >= 30) return '#eab308'
  return '#22c55e'
}
const getRulClass = (h) => {
  if (h < 72) return 'rul-danger'
  if (h < 240) return 'rul-warn'
  return 'rul-ok'
}
const getStatusType = (s) => ({ OPEN: 'danger', ACKNOWLEDGED: 'warning', RESOLVED: 'success', ESCALATED: 'danger', IGNORED: 'info' }[s] || 'info')
const formatTime = (t) => t ? new Date(t).toLocaleString() : ''
const formatRCA = (rca) => {
  if (!rca) return '（无）'
  try { return JSON.stringify(JSON.parse(rca), null, 2) } catch { return rca }
}

onMounted(loadAlerts)
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filters { display: flex; gap: 8px; }

.dark-table :deep(th.el-table__cell) { background: #334155 !important; color: #e2e8f0; }
.dark-table :deep(td.el-table__cell) { background: #0f172a !important; color: #e2e8f0; border-color: #334155; }
.dark-table :deep(.el-table__row--striped td.el-table__cell) { background: #1e293b !important; }

.severity-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-align: center; }
.severity-badge.low { background: #1e3a8a; color: #60a5fa; }
.severity-badge.medium { background: #78350f; color: #fbbf24; }
.severity-badge.high { background: #7c2d12; color: #fb923c; }
.severity-badge.critical { background: #7f1d1d; color: #f87171; }

.alert-title { font-weight: 600; color: #e2e8f0; }
.alert-desc { font-size: 12px; color: #64748b; margin-top: 2px; }
.muted { color: #64748b; }
.rul-danger { color: #ef4444; font-weight: 600; }
.rul-warn { color: #f97316; font-weight: 600; }
.rul-ok { color: #22c55e; }

.section-title { margin-top: 20px; color: #cbd5e1; border-left: 3px solid #60a5fa; padding-left: 8px; }
.diag-box { background: #0f172a; border-radius: 6px; padding: 14px; border: 1px solid #334155; }
.diag-text { color: #e2e8f0; line-height: 1.6; }
.rca-box { background: #0f172a; border-radius: 6px; padding: 14px; border: 1px solid #334155; max-height: 300px; overflow-y: auto; }
.rca-box pre { color: #94a3b8; font-size: 13px; white-space: pre-wrap; }

.dark-dialog :deep(.el-dialog) { background: #1e293b; color: #e2e8f0; }
.dark-dialog :deep(.el-dialog__header) { background: #334155; }
.dark-dialog :deep(.el-descriptions__label) { background: #334155 !important; color: #94a3b8 !important; }
.dark-dialog :deep(.el-descriptions__content) { background: #0f172a !important; color: #e2e8f0 !important; }
</style>
