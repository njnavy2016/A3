<template>
  <div class="agent-chat-page">
    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><ChatDotRound /></el-icon> 智能体对话</span>
          <div>
            <el-tag :type="agentConfigured ? 'success' : 'info'" size="small">
              {{ agentConfigured ? 'LLM 已配置' : '模拟模式（无 API Key）' }}
            </el-tag>
          </div>
        </div>
      </template>

      <div class="chat-area">
        <div v-for="(msg, idx) in messages" :key="idx" class="chat-msg" :class="msg.role">
          <div class="avatar">
            <el-icon v-if="msg.role === 'user'"><User /></el-icon>
            <el-icon v-else><MagicStick /></el-icon>
          </div>
          <div class="bubble">
            <div v-if="msg.role === 'assistant'" class="assistant-content">{{ msg.content }}</div>
            <div v-else class="user-content">{{ msg.content }}</div>
          </div>
        </div>
        <div v-if="loading" class="chat-msg assistant">
          <div class="avatar"><el-icon><MagicStick /></el-icon></div>
          <div class="bubble">
            <div class="typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="3"
          placeholder="问智能体问题，例如：WT-GEAR-003 目前状态如何？"
          @keydown.enter.ctrl="send"
          :disabled="loading"
        />
        <el-button type="primary" :loading="loading" @click="send">
          <el-icon><Promotion /></el-icon> 发送
        </el-button>
      </div>
    </el-card>

    <!-- 快捷操作 -->
    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="6">
        <el-button @click="quickAsk('帮我分析 WT-GEAR-003 设备状态')" style="width: 100%">🔍 分析 WT-GEAR-003</el-button>
      </el-col>
      <el-col :span="6">
        <el-button @click="quickAsk('轴承点蚀的特征频率怎么计算？')" style="width: 100%">📐 轴承特征频率</el-button>
      </el-col>
      <el-col :span="6">
        <el-button @click="quickAsk('齿轮磨损有哪些典型故障信号？')" style="width: 100%">⚙️ 齿轮磨损特征</el-button>
      </el-col>
      <el-col :span="6">
        <el-button @click="quickAsk('油压下降可能是什么原因？')" style="width: 100%">🧈 油压下降分析</el-button>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { agentChat } from '../api/client'

const messages = ref([
  { role: 'assistant', content: '你好！我是 **PdM 预测性维护智能体** 🤖\n\n我可以帮你：\n- 分析传感器数据中的异常模式\n- 推演根因（RCA）并给出 RUL 预估\n- 推荐维护策略和检修计划\n- 回答关于齿轮箱故障诊断的技术问题\n\n试试输入：「帮我分析 WT-GEAR-003 设备状态」' }
])
const inputText = ref('')
const loading = ref(false)
const agentConfigured = ref(true)

const send = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return
  
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  
  try {
    const resp = await agentChat({ message: text })
    messages.value.push({ role: 'assistant', content: resp.response || '（无响应）' })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '❌ 对话失败：' + (e.response?.data?.detail || e.message) })
  } finally {
    loading.value = false
  }
}

const quickAsk = (q) => { inputText.value = q; send() }
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; }

.chat-area { min-height: 400px; max-height: 500px; overflow-y: auto; padding: 10px; }
.chat-msg { display: flex; gap: 10px; margin-bottom: 14px; }
.chat-msg.user { flex-direction: row-reverse; }
.avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: #334155; display: flex; align-items: center; justify-content: center;
  color: #60a5fa; font-size: 18px; flex-shrink: 0;
}
.chat-msg.user .avatar { background: #1e40af; }
.bubble {
  max-width: 70%; padding: 12px 16px; border-radius: 12px;
  background: #0f172a; border: 1px solid #334155;
}
.chat-msg.user .bubble { background: #1e3a5f; border-color: #3b82f6; }
.user-content { color: #f1f5f9; }
.assistant-content { color: #e2e8f0; white-space: pre-wrap; line-height: 1.7; }

.typing { display: flex; gap: 4px; }
.typing span { width: 8px; height: 8px; border-radius: 50%; background: #60a5fa; animation: bounce 1.4s infinite ease-in-out both; }
.typing span:nth-child(1) { animation-delay: -0.32s; }
.typing span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

.chat-input { display: flex; gap: 10px; margin-top: 14px; align-items: flex-end; }
.chat-input .el-textarea { flex: 1; }

button { width: 100%; }
</style>
