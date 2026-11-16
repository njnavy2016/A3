<template>
  <div class="equipment-page">
    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Cpu /></el-icon> 设备管理</span>
          <el-button type="primary" size="small" @click="$router.push('/dashboard')">
            ← 返回大屏
          </el-button>
        </div>
      </template>

      <el-table :data="equipments" class="dark-table">
        <el-table-column prop="equipment_code" label="编码" width="180">
          <template #default="{ row }">
            <code>{{ row.equipment_code }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="设备名称" min-width="200" />
        <el-table-column prop="model" label="型号" width="140" />
        <el-table-column prop="manufacturer" label="厂商" width="120" />
        <el-table-column label="健康分数" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.health_score" :color="getColor(row.health_score)" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" effect="dark">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="$router.push(`/equipment/${row.id}`)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listEquipments } from '../api/client'

const equipments = ref([])
onMounted(async () => { equipments.value = await listEquipments() })

const getColor = (h) => h >= 80 ? '#22c55e' : h >= 60 ? '#eab308' : h >= 40 ? '#f97316' : '#ef4444'
const getStatusType = (s) => ({ RUNNING: 'success', MAINTENANCE: 'warning', CRITICAL: 'danger', STOPPED: 'info' }[s] || 'info')
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; }
.dark-table :deep(th.el-table__cell) { background: #334155 !important; color: #e2e8f0; }
.dark-table :deep(td.el-table__cell) { background: #0f172a !important; color: #e2e8f0; border-color: #334155; }
code { background: #1e293b; padding: 2px 6px; border-radius: 4px; color: #60a5fa; font-family: monospace; }
</style>
