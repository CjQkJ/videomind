<template>
  <div class="history-view">
    <div class="header-banner">
      <div class="title-group"><h1>历史解析记录</h1><p class="sub">你解码过的每一段视频，都在这里静静结晶</p></div>
      <n-button secondary @click="fetchHistory" :loading="loading">
        <template #icon><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg></template>刷新列表
      </n-button>
    </div>
    <n-card class="table-card" :bordered="false">
      <n-data-table :columns="columns" :data="jobs" :loading="loading" :bordered="false" :scroll-x="960" class="custom-table">
        <template #empty>
          <StoryEmpty title="还没有解码过的视频" description="你的第一段知识旅程，从工作台提交一个视频开始。" />
        </template>
      </n-data-table>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { api } from '@/utils/api'
import { useRouter } from 'vue-router'
import { NButton, NTag, NProgress, useMessage } from 'naive-ui'
import StoryEmpty from '@/components/StoryEmpty.vue'

const router = useRouter()
const message = useMessage()
const jobs = ref<any[]>([])
const loading = ref(false)

const columns = [
  { title: '任务名称 / ID', key: 'task',
    render(row: any) { return h('div', { class: 'task-cell' }, [h('div', { class: 'task-title' }, row.metadata?.title || '未命名视频解析'), h('div', { class: 'task-id' }, row.job_id)]) }
  },
  { title: '模式', key: 'mode', width: 120,
    render(row: any) { return h(NTag, { size: 'small', border: false, class: 'mode-tag' }, { default: () => row.mode || 'study_note' }) }
  },
  { title: '状态', key: 'status', width: 120,
    render(row: any) {
      let type: 'default' | 'success' | 'error' | 'warning' = 'default'; let label = row.status
      if (row.status === 'succeeded') { type = 'success'; label = '已完成' }
      else if (row.status === 'failed') { type = 'error'; label = '失败' }
      else if (row.status === 'running') { type = 'warning'; label = '解析中' }
      else if (row.status === 'queued') { type = 'default'; label = '排队中' }
      return h(NTag, { type, size: 'small', round: true }, { default: () => label })
    }
  },
  { title: '进度', key: 'progress', width: 180,
    render(row: any) { return h(NProgress, { type:'line', percentage:row.progress||0, indicatorPlacement:'inside', processing:row.status==='running', status:row.status==='failed'?'error':(row.status==='succeeded'?'success':'default') }) }
  },
  { title: '创建时间', key: 'created_at', width: 180,
    render(row: any) { return row.created_at ? new Date(row.created_at).toLocaleString() : '-' }
  },
  { title: '操作', key: 'actions', width: 100,
    render(row: any) { return h(NButton, { size:'small', type:'primary', secondary:true, onClick:()=>{ router.push({ name:'workbench', query:{ jobId:row.job_id } }) } }, { default: () => '查看结果' }) }
  },
]

const fetchHistory = async () => { loading.value=true; try { const res=await api<any>('/api/v1/jobs?limit=50'); jobs.value=res.items||[] } catch(err:any){ message.error('获取历史记录失败: '+err.message) } finally { loading.value=false } }
onMounted(()=>{ fetchHistory() })
</script>

<style scoped>
.history-view { max-width:1100px;width:100%;min-width:0;margin:0 auto }
.header-banner { display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:20px }
.title-group h1 { font-size:1.5rem;font-weight:800;color:var(--text-main);margin-bottom:4px }
.title-group .sub { font-size:0.9rem;color:var(--text-muted) }
.table-card { min-width:0;padding:4px;overflow:hidden }
:deep(.custom-table) { min-width:0 }
:deep(.task-cell) { display:flex;flex-direction:column;gap:2px }
:deep(.task-title) { font-weight:600;color:var(--text-main);font-size:0.92rem }
:deep(.task-id) { font-size:0.78rem;font-family:monospace;color:var(--text-dim) }
:deep(.mode-tag) { background:var(--emerald-soft) !important;color:var(--emerald-deep) !important }
@media (max-width: 640px) {
  .header-banner { flex-direction:column;align-items:stretch;gap:16px }
  .header-banner :deep(.n-button) { align-self:flex-start }
  .table-card { padding:4px }
}
</style>
