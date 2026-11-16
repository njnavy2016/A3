import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    console.warn('API Error:', e.config?.url, e.message)
    return Promise.reject(e)
  }
)

// ============ Dashboard ============
export const getDashboardStats = () => api.get('/dashboard/stats').then(r => r.data)

// ============ Equipment ============
export const listEquipments = () => api.get('/equipment').then(r => r.data)
export const getEquipment = (id) => api.get(`/equipment/${id}`).then(r => r.data)
export const getEquipmentSensors = (id) => api.get(`/equipment/${id}/sensors`).then(r => r.data)

// ============ Sensors ============
export const getSensorRealtime = (id) => api.get(`/sensors/${id}/realtime`).then(r => r.data)

// ============ Alerts ============
export const listAlerts = (params = {}) => api.get('/alerts', { params }).then(r => r.data)
export const getAlert = (id) => api.get(`/alerts/${id}`).then(r => r.data)
export const acknowledgeAlert = (id) => api.patch(`/alerts/${id}/acknowledge`).then(r => r.data)
export const resolveAlert = (id) => api.patch(`/alerts/${id}/resolve`).then(r => r.data)

// ============ Work Orders ============
export const listWorkOrders = (params = {}) => api.get('/work-orders', { params }).then(r => r.data)
export const getWorkOrder = (id) => api.get(`/work-orders/${id}`).then(r => r.data)
export const createWorkOrder = (data) => api.post('/work-orders', data).then(r => r.data)
export const submitWorkOrder = (id) => api.post(`/work-orders/${id}/submit`).then(r => r.data)
export const startWorkOrder = (id) => api.post(`/work-orders/${id}/start`).then(r => r.data)
export const completeWorkOrder = (id) => api.post(`/work-orders/${id}/complete`).then(r => r.data)
export const getPendingApprovalCount = () => api.get('/work-orders/pending-count').then(r => r.data)

// ============ Approvals ============
export const listPendingApprovals = () => api.get('/approvals').then(r => r.data)
export const handleApproval = (id, action) => api.post(`/approvals/${id}/action`, action).then(r => r.data)
export const getApprovalRecords = (id) => api.get(`/approvals/${id}/records`).then(r => r.data)

// ============ Manuals ============
export const listManuals = (type) => api.get('/manuals', { params: { equipment_type: type } }).then(r => r.data)

// ============ Agent ============
const agentApi = axios.create({ baseURL: '/agent-api', timeout: 180000 })
export const triggerAgentAnalysis = (payload) => agentApi.post('/analyze', payload).then(r => r.data)
export const agentChat = (payload) => agentApi.post('/chat', payload).then(r => r.data)
export const getConversation = (sid) => agentApi.get(`/conversations/${sid}`).then(r => r.data)

// ============ Realtime ============
export const getRealtimeLatest = (code) => 
  axios.get(`/api/v1/realtime/latest`, { params: { equipment_code: code } }).then(r => r.data)
