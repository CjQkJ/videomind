<template>
  <div class="apikeys-view">
    <PageHeader title="API Keys 密钥管理" subtitle="管理你的解码凭证，让 API 替你持续结晶知识" />
    <n-card class="view-card" :bordered="false">
      <div class="pb-6 mb-6 border-b" style="border-color:rgba(5,150,105,0.22)">
        <div class="text-sm font-bold mb-3" style="color:#0f172a">创建新 API Key</div>
        <div class="flex flex-wrap gap-3">
          <n-input v-model:value="newKeyName" placeholder="输入 Key 备注名称 (例如: ci)" size="large" style="max-width:380px" @keydown.enter.prevent="createKey" />
          <n-button type="primary" size="large" @click="createKey" :loading="creating">生成 Key</n-button>
        </div>
      </div>
      <n-alert v-if="newlyCreatedKey" type="warning" title="🔑 请妥善保存您的 API 密钥" class="mb-6">
        <div class="flex items-center gap-4 my-2">
          <code class="key-code">{{ newlyCreatedKey }}</code>
          <n-button size="small" type="warning" @click="copyKey">复制密钥</n-button>
        </div>
        <p class="text-xs" style="color:#b45309">出于安全保护考虑，完整 Key 明文仅在创建成功时展示一次，离开页面后将无法再次显示。</p>
      </n-alert>
      <div>
        <div class="text-sm font-bold mb-4" style="color:#0f172a">已有的 API Key 列表</div>
        <n-data-table :columns="columns" :data="keys" :loading="loading" :bordered="false">
          <template #empty>
            <StoryEmpty title="还没有解码凭证" description="创建一个 API Key，让自动化流程替你结晶知识。" />
          </template>
        </n-data-table>
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import { api } from '@/utils/api'
import { NButton, NTag, useMessage, useDialog } from 'naive-ui'
import PageHeader from '@/components/PageHeader.vue'
import StoryEmpty from '@/components/StoryEmpty.vue'

const message = useMessage()
const dialog = useDialog()
const keys = ref<any[]>([])
const loading = ref(false)
const newKeyName = ref('')
const creating = ref(false)
const newlyCreatedKey = ref('')

const columns = [
  { title: 'Key 前缀', key: 'key_prefix', render(row:any) { return h('code', { class: 'key-prefix-code' }, `${row.key_prefix}...`) } },
  { title: '备注名称', key: 'name', render(row:any) { return h('span', { style:'font-weight:700;color:#0f172a' }, row.name) } },
  { title: '状态', key: 'is_active', width:100, render(row:any) { return h(NTag, { type:row.is_active?'success':'default', size:'small', round:true }, { default: ()=>row.is_active?'正常':'已禁用' }) } },
  { title: '创建时间', key: 'created_at', render(row:any) { return new Date(row.created_at).toLocaleString() } },
  { title: '操作', key: 'actions', width:100, render(row:any) { return h(NButton, { size:'small', type:'error', ghost:true, disabled:!row.is_active, onClick:()=>confirmDelete(row) }, { default: ()=>'禁用' }) } },
]

const fetchKeys = async () => { loading.value=true; try { keys.value = await api<any[]>('/api/v1/api-keys')||[] } catch(e:any){ message.error('获取 Keys 失败: '+e.message) } finally { loading.value=false } }
const createKey = async () => { if(!newKeyName.value.trim()) newKeyName.value='default'; creating.value=true; try { const res=await api<any>('/api/v1/api-keys',{method:'POST',json:{name:newKeyName.value.trim()}}); newlyCreatedKey.value=res.key; newKeyName.value=''; fetchKeys() } catch(e:any){ message.error('创建失败: '+e.message) } finally { creating.value=false } }
const copyKey = async () => { try { await navigator.clipboard.writeText(newlyCreatedKey.value); message.success('密钥已复制到剪贴板'); newlyCreatedKey.value='' } catch { message.error('复制失败') } }
const confirmDelete = (row:any) => { dialog.warning({ title:'确认禁用 API Key', content:`确定要禁用 Key "${row.name}" (${row.key_prefix}...) 吗？`, positiveText:'确认禁用', negativeText:'取消', onPositiveClick:async()=>{ try { await api(`/api/v1/api-keys/${row.id}`,{method:'DELETE'}); message.success('API Key 已禁用'); fetchKeys() } catch(e:any){ message.error('禁用失败: '+e.message) } } }) }
onMounted(()=>{ fetchKeys() })
</script>

<style scoped>
.apikeys-view { max-width:920px;margin:0 auto }
.view-card { padding:16px 24px }
.key-code { background:var(--bg-subtle);padding:8px 16px;border-radius:8px;font-family:monospace;font-size:0.9rem;color:var(--warning);border:1px solid rgba(217,119,6,0.3) }
:deep(.key-prefix-code) { background:var(--emerald-soft);padding:2px 8px;border-radius:6px;font-family:monospace;color:var(--emerald-deep);border:1px solid rgba(14,159,110,0.3);font-size:0.82rem }
</style>
