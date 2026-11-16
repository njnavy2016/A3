<template>
  <el-container class="app-container">
    <!-- 顶部导航 -->
    <el-header class="app-header">
      <div class="header-left">
        <el-icon class="logo-icon"><Tools /></el-icon>
        <h1 class="app-title">PdM Agent · 预测性维护智能体</h1>
      </div>
      <div class="header-right">
        <el-tag v-if="criticalCount > 0" type="danger" effect="dark" size="large">
          <el-badge :value="criticalCount" :max="9">
            <el-icon><WarningFilled /></el-icon> 严重告警
          </el-badge>
        </el-tag>
        <el-tag v-if="pendingApprovals > 0" type="warning" effect="dark" size="large">
          <el-badge :value="pendingApprovals" :max="9">
            <el-icon><Stamp /></el-icon> 待审批
          </el-badge>
        </el-tag>
        <el-tag type="success" effect="dark" size="large">
          <el-icon><Connection /></el-icon> 系统在线
        </el-tag>
      </div>
    </el-header>

    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="220px" class="app-aside">
        <el-menu
          :default-active="$route.path"
          router
          background-color="#1f2937"
          text-color="#cbd5e1"
          active-text-color="#60a5fa"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataBoard /></el-icon>
            <span>监控大屏</span>
          </el-menu-item>
          <el-menu-item index="/equipment">
            <el-icon><Cpu /></el-icon>
            <span>设备管理</span>
          </el-menu-item>
          <el-menu-item index="/alerts">
            <el-icon><Bell /></el-icon>
            <span>告警中心</span>
            <el-badge v-if="openAlerts > 0" :value="openAlerts" :max="9" class="menu-badge" />
          </el-menu-item>
          <el-menu-item index="/work-orders">
            <el-icon><Document /></el-icon>
            <span>工单管理</span>
          </el-menu-item>
          <el-menu-item index="/approvals">
            <el-icon><Stamp /></el-icon>
            <span>审批工作台</span>
            <el-badge v-if="pendingApprovals > 0" :value="pendingApprovals" :max="9" class="menu-badge" />
          </el-menu-item>
          <el-menu-item index="/manuals">
            <el-icon><Reading /></el-icon>
            <span>维修手册</span>
          </el-menu-item>
          <el-menu-item index="/agent-chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>智能体对话</span>
          </el-menu-item>
        </el-menu>

        <div class="agent-status">
          <div class="status-title">
            <span class="pulse-dot"></span>
            智能体状态
          </div>
          <div class="status-row">
            <span>LLM 推理</span>
            <el-tag size="small" :type="agentConfigured ? 'success' : 'info'">
              {{ agentConfigured ? '已配置' : '模拟模式' }}
            </el-tag>
          </div>
          <div class="status-row">
            <span>自动分析</span>
            <el-tag size="small" type="success">开启</el-tag>
          </div>
        </div>
      </el-aside>

      <!-- 主内容 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getDashboardStats } from './api/client'

const criticalCount = ref(0)
const openAlerts = ref(0)
const pendingApprovals = ref(0)
const agentConfigured = ref(true)
let pollTimer = null

const pollStats = async () => {
  try {
    const data = await getDashboardStats()
    criticalCount.value = data.critical_alerts || 0
    openAlerts.value = data.open_alerts || 0
    pendingApprovals.value = data.pending_work_orders || 0
  } catch (e) {
    console.warn('Dashboard stats 获取失败', e)
  }
}

onMounted(() => {
  pollStats()
  pollTimer = setInterval(pollStats, 15000)
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; padding: 0; font-family: 'Inter', 'PingFang SC', sans-serif; background: #0f172a; color: #e2e8f0; }

.app-container { height: 100vh; background: #0f172a; }
.app-header {
  background: linear-gradient(90deg, #1e3a5f, #0f172a);
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #334155; padding: 0 20px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.logo-icon { font-size: 28px; color: #60a5fa; }
.app-title { font-size: 18px; margin: 0; font-weight: 600; color: #f1f5f9; }
.header-right { display: flex; gap: 12px; align-items: center; }

.app-aside { background: #1f2937; border-right: 1px solid #334155; overflow-y: auto; }
.el-menu { border-right: none !important; }
.menu-badge { margin-left: 8px; }

.agent-status {
  margin: 16px; padding: 12px; background: #111827; border-radius: 8px;
  border: 1px solid #334155;
}
.status-title { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #94a3b8; margin-bottom: 10px; }
.pulse-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.status-row { display: flex; justify-content: space-between; font-size: 12px; color: #64748b; margin-top: 6px; }

.app-main { background: #0f172a; padding: 20px; overflow-y: auto; }

.el-menu-item.is-active { background: rgba(96,165,250,0.1) !important; border-left: 3px solid #60a5fa; }
</style>
