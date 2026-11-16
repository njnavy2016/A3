<template>
  <div class="approvals-page">
    <el-alert
      type="warning"
      :closable="false"
      class="banner"
      show-icon
    >
      <template #title>
        <strong>⚠️ HITL 审批拦截机制</strong>
        <span style="margin-left: 12px">
          PdM 智能体生成的所有工单都会被拦截在此，必须由人工审批后才能执行。
          <el-tag type="danger" size="small" style="margin-left: 8px">停机申请 → 必须 SUPERVISOR+ 审批</el-tag>
        </span>
      </template>
    </el-alert>

    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Stamp /></el-icon> 待审批工单</span>
          <el-tag type="warning" effect="dark" size="large">
            {{ approvals.length }} 项待审批
          </el-tag>
        </div>
      </template>

      <el-table :data="approvals" class="dark-table" style="width: 100%">
        <el-table-column label="紧急度" width="110">
          <template #default="{ row }">
            <el-tag :type="getPriorityTag(row.priority)" effect="dark" size="large">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <div class="order-type" :class="row.order_type.toLowerCase()">
              {{ row.order_type }}
              <span v-if="row.order_type === 'SHUTDOWN_REQUEST'" class="shutdown-badge">⚠️ 停机</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="工单标题" prop="title" min-width="250">
          <template #default="{ row }">
            <div class="wo-title">{{ row.title }}</div>
            <div class="wo-desc">{{ row.description?.substring(0, 80) }}{{ row.description?.length > 80 ? '...' : '' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="诊断" min-width="200">
          <template #default="{ row }">
            <div class="diag-small">{{ row.diagnosis || '（无）' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="工单编号" width="170" prop="order_no">
          <template #default="{ row }"><code>{{ row.order_no }}</code></template>
        </el-table-column>
        <el-table-column label="审批策略" width="150">
          <template #default="{ row }">
            <el-tag size="small" :type="getPolicyType(row.approval_policy)">
              {{ row.approval_policy || 'LEVEL1' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建者" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.created_by === 'AGENT'" type="success" size="small" effect="dark">🤖 AGENT</el-tag>
            <el-tag v-else type="info" size="small">{{ row.created_by }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }"><span class="muted">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="审批操作" width="300">
          <template #default="{ row }">
            <el-button
              type="success"
              size="small"
              @click="openApprovalDialog(row, 'APPROVE')"
            >✅ 批准</el-button>
            <el-button
              type="danger"
              size="small"
              @click="openApprovalDialog(row, 'REJECT')"
            >❌ 拒绝</el-button>
            <el-button
              type="warning"
              size="small"
              @click="openApprovalDialog(row, 'EDIT')"
            >✏️ 修改</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!approvals.length" description="没有待审批工单 🎉" />
    </el-card>

    <!-- 审批对话框 -->
    <el-dialog v-model="dialogVisible" :title="getDialogTitle()" width="500px" class="dark-dialog">
      <el-form v-if="currentWo" label-position="top">
        <el-form-item label="审批角色">
          <el-select v-model="dialogData.approver_role" style="width: 100%">
            <el-option label="TECHNICIAN (技术员)" value="TECHNICIAN" />
            <el-option label="TECHNICIAN_LEAD (技术主管)" value="TECHNICIAN_LEAD" />
            <el-option label="SUPERVISOR (值班长)" value="SUPERVISOR" />
            <el-option label="MANAGER (经理)" value="MANAGER" />
          </el-select>
        </el-form-item>
        
        <!-- EDIT 模式下可修改字段 -->
        <template v-if="dialogData.action === 'EDIT'">
          <el-form-item label="修改工单标题">
            <el-input v-model="currentWo.title" />
          </el-form-item>
          <el-form-item label="修改优先级">
            <el-select v-model="currentWo.priority" style="width: 100%">
              <el-option value="LOW" label="LOW" />
              <el-option value="MEDIUM" label="MEDIUM" />
              <el-option value="HIGH" label="HIGH" />
              <el-option value="CRITICAL" label="CRITICAL" />
            </el-select>
          </el-form-item>
        </template>
        
        <el-form-item :label="dialogData.action === 'REJECT' ? '拒绝理由（必填）' : '审批备注'">
          <el-input
            v-model="dialogData.comment"
            type="textarea"
            :rows="3"
            :placeholder="dialogData.action === 'REJECT' ? '请说明拒绝原因...' : '可选备注...'"
          />
        </el-form-item>

        <!-- 安全提示 -->
        <el-alert
          v-if="currentWo?.order_type === 'SHUTDOWN_REQUEST' && dialogData.action === 'APPROVE'"
          type="error"
          show-icon
          :closable="false"
          style="margin-top: 12px"
        >
          <template #title>
            <strong>⚠️ 安全警告：停机申请</strong><br/>
            你即将批准一次停机操作！此操作会影响生产。
            请确认你拥有 SUPERVISOR 或 MANAGER 级别权限，并确认审批角色选择正确。
          </template>
        </el-alert>
      </el-form>
      
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="dialogData.action === 'APPROVE'"
          type="success"
          :loading="submitting"
          @click="submitApproval"
        >确认批准</el-button>
        <el-button
          v-else-if="dialogData.action === 'REJECT'"
          type="danger"
          :loading="submitting"
          :disabled="!dialogData.comment"
          @click="submitApproval"
        >确认拒绝</el-button>
        <el-button
          v-else
          type="warning"
          :loading="submitting"
          @click="submitApproval"
        >提交修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listPendingApprovals, handleApproval } from '../api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const approvals = ref([])
const dialogVisible = ref(false)
const currentWo = ref(null)
const dialogData = reactive({ action: '', approver_role: 'TECHNICIAN_LEAD', comment: '' })
const submitting = ref(false)

const loadApprovals = async () => {
  approvals.value = await listPendingApprovals()
}

const openApprovalDialog = (wo, action) => {
  currentWo.value = wo
  dialogData.action = action
  dialogData.comment = ''
  dialogVisible.value = true
  
  // 停机申请默认需要 SUPERVISOR
  if (wo.order_type === 'SHUTDOWN_REQUEST' && action === 'APPROVE') {
    dialogData.approver_role = 'SUPERVISOR'
  } else if (wo.priority === 'CRITICAL') {
    dialogData.approver_role = 'SUPERVISOR'
  } else {
    dialogData.approver_role = 'TECHNICIAN_LEAD'
  }
}

const getDialogTitle = () => {
  const titles = { APPROVE: '✅ 批准工单', REJECT: '❌ 拒绝工单', EDIT: '✏️ 修改工单' }
  return titles[dialogData.action] || '审批'
}

const submitApproval = async () => {
  submitting.value = true
  try {
    // 二次确认（拒绝/停机批准）
    if (dialogData.action === 'REJECT') {
      await ElMessageBox.confirm(
        `确定拒绝工单 ${currentWo.value.order_no} 吗？`,
        '确认拒绝',
        { type: 'warning' }
      )
    }
    if (currentWo.value.order_type === 'SHUTDOWN_REQUEST' && dialogData.action === 'APPROVE') {
      await ElMessageBox.confirm(
        `⚠️ 即将批准停机申请！\n工单：${currentWo.value.order_no}\n请再次确认你拥有相应权限。`,
        '安全确认',
        { type: 'error', confirmButtonText: '我确认批准停机' }
      )
    }
    
    const payload = {
      action: dialogData.action,
      approver: 'manual_user',
      approver_role: dialogData.approver_role,
      comment: dialogData.comment,
    }
    
    // EDIT 时附带修改后的字段
    if (dialogData.action === 'EDIT') {
      payload.edited_fields = {
        title: currentWo.value.title,
        priority: currentWo.value.priority,
      }
    }
    
    await handleApproval(currentWo.value.id, payload)
    ElMessage.success('审批操作成功')
    dialogVisible.value = false
    await loadApprovals()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || '审批失败：' + (e.message || e))
    }
  } finally {
    submitting.value = false
  }
}

const getPriorityTag = (p) => ({ LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }[p] || 'info')
const getPolicyType = (t) => ({ AUTO: 'success', LEVEL1: '', LEVEL2: 'warning', CRITICAL: 'danger', CRITICAL_SHUTDOWN: 'danger' }[t] || '')
const formatTime = (t) => t ? new Date(t).toLocaleString() : ''

onMounted(loadApprovals)
</script>

<style>
.banner { margin-bottom: 16px; }
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }

.dark-table :deep(th.el-table__cell) { background: #334155 !important; color: #e2e8f0; }
.dark-table :deep(td.el-table__cell) { background: #0f172a !important; color: #e2e8f0; border-color: #334155; }
.dark-table :deep(.el-table__row--striped td.el-table__cell) { background: #1e293b !important; }

.order-type { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
.order-type.preventive { color: #60a5fa; }
.order-type.corrective { color: #fbbf24; }
.order-type.emergency { color: #fb923c; }
.order-type.shutdown_request { color: #f87171; }
.shutdown-badge { font-size: 11px; color: #ef4444; }

.wo-title { font-weight: 600; color: #e2e8f0; }
.wo-desc { font-size: 12px; color: #64748b; margin-top: 2px; }
.diag-small { font-size: 13px; color: #cbd5e1; }
code { background: #1e293b; padding: 2px 6px; border-radius: 4px; color: #60a5fa; font-family: monospace; }
.muted { color: #64748b; font-size: 12px; }

.dark-dialog :deep(.el-dialog) { background: #1e293b; color: #e2e8f0; }
.dark-dialog :deep(.el-dialog__header) { background: #334155; }
.dark-dialog :deep(.el-input__wrapper),
.dark-dialog :deep(.el-textarea__inner),
.dark-dialog :deep(.el-select__wrapper) { background: #0f172a !important; }
.dark-dialog :deep(.el-form-item__label) { color: #cbd5e1; }
</style>
