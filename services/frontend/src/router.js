import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '监控大屏' } },
  { path: '/equipment', component: () => import('./views/Equipment.vue'), meta: { title: '设备管理' } },
  { path: '/equipment/:id', component: () => import('./views/EquipmentDetail.vue'), meta: { title: '设备详情' } },
  { path: '/alerts', component: () => import('./views/Alerts.vue'), meta: { title: '告警中心' } },
  { path: '/work-orders', component: () => import('./views/WorkOrders.vue'), meta: { title: '工单管理' } },
  { path: '/approvals', component: () => import('./views/Approvals.vue'), meta: { title: '审批工作台' } },
  { path: '/manuals', component: () => import('./views/Manuals.vue'), meta: { title: '维修手册' } },
  { path: '/agent-chat', component: () => import('./views/AgentChat.vue'), meta: { title: '智能体对话' } },
]

export default createRouter({
  history: createWebHashHistory(),
  routes
})
