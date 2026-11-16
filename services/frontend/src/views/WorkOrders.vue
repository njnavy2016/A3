<template>
  <div class="wo-page">
    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Document /></el-icon> 工单管理</span>
          <el-button type="primary" size="small" @click="showCreateDialog = true">
            + 新建工单
          </el-button>
        </div>
      </template>

      <el-table :data="workOrders" class="dark-table">
        <el-table-column prop="order_no" label="编号" width="170">
          <template #default="{ row }"><code>{{ row.order_no }}</code></template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            {{ row.title }}
            <el-tag v-if="row.created_by === 'AGENT'" size="small" type="success" style="margin-left: 6px">🤖</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-tag :type="getOrderTypeColor(row.order_type)">{{ row.order_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" effect="dark">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="160">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="dark">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批" width="120">
          <template #default="{ row }">
            <span v-if="row.requires_human_approval" class="approval-required">
              🔒 {{ row.approval_policy || 'LEVEL1' }}
            </span>
            <span v-else class="muted">无需审批</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }"><span class="muted">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" v-if="row.status === 'DRAFT'" @click="submitWo(row)">提交审批</el-button>
            <el-button size="small" v-if="row.status === 'APPROVED'" type="primary" @click="startWo(row)">开始</el-button>
            <el-button size="small" v-if="row.status === 'IN_PROGRESS'" type="success" @click="completeWo(row)">完成</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建工单" width="500px" class="dark-dialog">
      <el-form label-position="top">
        <el-form-item label="设备">
          <el-select v-model="newWo.equipment_id" style="width: 100%">
            <el-option v-for="eq in equipments" :key="eq.id" :label="eq.equipment_code + ' - ' + eq.name" :value="eq.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单类型">
          <el-select v-model="newWo.order_type" style="width: 100%">
            <el-option value="PREVENTIVE" label="预防性维护" />
            <el-option value="CORRECTIVE" label="故障维修" />
            <el-option value="EMERGENCY" label="紧急抢修" />
            <el-option value="SHUTDOWN_REQUEST" label="停机申请" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单标题">
          <el-input v-model="newWo.title" placeholder="简短描述维护内容" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="newWo.priority" style="width: 100%">
            <el-option value="LOW" />
            <el-option value="MEDIUM" />
            <el-option value="HIGH" />
            <el-option value="CRITICAL" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createWo">创建并提交审批</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listWorkOrders, listEquipments, createWorkOrder, submitWorkOrder, startWorkOrder, completeWorkOrder } from '../api/client'

const workOrders = ref([])
const equipments = ref([])
const showCreateDialog = ref(false)
const newWo = reactive({ equipment_id: null, order_type: 'PREVENTIVE', title: '', priority: 'MEDIUM' })

const load = async () => {
  workOrders.value = await listWorkOrders({ limit: 200 })
  equipments.value = await listEquipments()
}

const createWo = async () => {
  await createWorkOrder(newWo)
  await load()
  showCreateDialog.value = false
  newWo.title = ''
}
const submitWo = async (row) => { await submitWorkOrder(row.id); await load() }
const startWo = async (row) => { await startWorkOrder(row.id); await load() }
const completeWo = async (row) => { await completeWorkOrder(row.id); await load() }

const getOrderTypeColor = (t) => ({ PREVENTIVE: '', CORRECTIVE: 'warning', EMERGENCY: 'danger', SHUTDOWN_REQUEST: 'danger' }[t])
const getPriorityType = (p) => ({ LOW: 'info', MEDIUM: '', HIGH: 'warning', CRITICAL: 'danger' }[p])
const getStatusType = (s) => ({ DRAFT: 'info', PENDING_APPROVAL: 'warning', APPROVED: 'success', REJECTED: 'danger', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' }[s])
const formatTime = (t) => t ? new Date(t).toLocaleString() : ''

onMounted(load)
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; }
.dark-table :deep(th.el-table__cell) { background: #334155 !important; color: #e2e8f0; }
.dark-table :deep(td.el-table__cell) { background: #0f172a !important; color: #e2e8f0; border-color: #334155; }
code { background: #1e293b; padding: 2px 6px; border-radius: 4px; color: #60a5fa; font-family: monospace; }
.muted { color: #64748b; font-size: 12px; }
.approval-required { color: #fbbf24; font-size: 12px; }

.dark-dialog :deep(.el-dialog) { background: #1e293b; color: #e2e8f0; }
.dark-dialog :deep(.el-dialog__header) { background: #334155; }
.dark-dialog :deep(.el-input__wrapper), .dark-dialog :deep(.el-select__wrapper) { background: #0f172a !important; }
</style>
