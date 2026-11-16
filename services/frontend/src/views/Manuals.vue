<template>
  <div class="manuals-page">
    <el-card class="dark-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Reading /></el-icon> 维修手册（RAG 知识源）</span>
          <el-tag type="success">共 {{ manuals.length }} 个手册 / {{ totalChunks }} 个章节</el-tag>
        </div>
      </template>
      
      <div v-for="manual in manuals" :key="manual.id" class="manual-section">
        <div class="manual-header">
          <el-icon><Document /></el-icon>
          <strong>{{ manual.title }}</strong>
          <el-tag size="small">{{ manual.equipment_type }}</el-tag>
          <span class="muted">v{{ manual.version }} · {{ manual.vendor }}</span>
        </div>
        <div class="chunks">
          <div v-for="chunk in manual.chunks" :key="chunk.id" class="chunk-card">
            <div class="chunk-title">
              <el-tag size="small" type="warning">章节 {{ chunk.chapter }}</el-tag>
              <span>{{ chunk.section_title }}</span>
            </div>
            <div class="chunk-content">{{ chunk.content }}</div>
            <div class="chunk-keywords">
              <el-tag v-for="kw in (chunk.keywords || '').split(',').filter(k => k)" :key="kw" size="small" type="info">
                {{ kw.trim() }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <el-empty v-if="!manuals.length" description="暂无手册" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listManuals } from '../api/client'

const manuals = ref([])
const totalChunks = computed(() => manuals.value.reduce((s, m) => s + m.chunk_count, 0))

onMounted(async () => {
  manuals.value = await listManuals()
})
</script>

<style>
.dark-card { background: #1e293b; border-color: #334155; color: #e2e8f0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }

.manual-section { margin-bottom: 24px; }
.manual-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #0f172a; border-radius: 8px; margin-bottom: 10px; }
.manual-header strong { color: #f1f5f9; font-size: 15px; }
.muted { color: #64748b; font-size: 13px; margin-left: auto; }

.chunks { display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 1fr)); gap: 12px; }
.chunk-card {
  background: #0f172a; border-radius: 8px; padding: 14px;
  border: 1px solid #334155;
}
.chunk-title { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 14px; color: #cbd5e1; }
.chunk-content { font-size: 13px; color: #94a3b8; line-height: 1.7; max-height: 180px; overflow-y: auto; margin-bottom: 8px; }
.chunk-keywords { display: flex; flex-wrap: wrap; gap: 4px; }
</style>
