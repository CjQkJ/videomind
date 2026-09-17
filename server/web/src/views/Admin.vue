<template>
  <div class="admin-page">
    <header class="admin-head">
      <div>
        <h1>后台管理</h1>
        <p class="sub">用户 · 使用记录 · API 密钥 · 模型配置</p>
      </div>
      <n-tag type="warning" round>仅管理员可见</n-tag>
    </header>

    <n-tabs type="line" animated>
      <n-tab-pane name="overview" tab="概览">
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-label">注册用户</div>
            <div class="stat-value">{{ stats.users?.total ?? '-' }}</div>
            <div class="stat-foot">活跃 {{ stats.users?.active ?? 0 }} · 管理员 {{ stats.users?.admins ?? 0 }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">任务总数</div>
            <div class="stat-value">{{ stats.jobs?.total ?? '-' }}</div>
            <div class="stat-foot">今日 {{ stats.jobs?.today ?? 0 }} · 运行 {{ stats.jobs?.running ?? 0 }} · 排队 {{ stats.jobs?.queued ?? 0 }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">成功 / 失败</div>
            <div class="stat-value">{{ stats.jobs?.succeeded ?? 0 }} / {{ stats.jobs?.failed ?? 0 }}</div>
            <div class="stat-foot">API 密钥启用 {{ stats.api_keys?.active ?? 0 }} · 共 {{ stats.api_keys?.total ?? 0 }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">当前模型</div>
            <div class="stat-value model-mini">{{ stats.default_model || '-' }}</div>
            <div class="stat-foot">视频理解模型（运行时）</div>
          </div>
        </div>
      </n-tab-pane>

      <n-tab-pane name="users" tab="用户管理">
        <div class="toolbar">
          <n-input v-model:value="userQuery" placeholder="搜索邮箱" clearable style="max-width:280px" @keyup.enter="loadUsers" />
          <n-button type="primary" @click="loadUsers">搜索</n-button>
        </div>
        <n-data-table :columns="userColumns" :data="users" :loading="loadingUsers" :pagination="{ pageSize: 20 }" :bordered="false" size="small" />
      </n-tab-pane>

      <n-tab-pane name="jobs" tab="使用记录">
        <div class="toolbar">
          <n-select v-model:value="jobStatus" :options="statusOptions" placeholder="状态" clearable style="max-width:160px" @update:value="loadJobs" />
          <n-input v-model:value="jobEmail" placeholder="邮箱" clearable style="max-width:220px" @keyup.enter="loadJobs" />
          <n-button type="primary" @click="loadJobs">搜索</n-button>
        </div>
        <n-data-table :columns="jobColumns" :data="jobs" :loading="loadingJobs" :pagination="{ pageSize: 20 }" :bordered="false" size="small" />
      </n-tab-pane>

      <n-tab-pane name="keys" tab="API 密钥">
        <div class="toolbar">
          <n-input v-model:value="keyEmail" placeholder="邮箱" clearable style="max-width:220px" @keyup.enter="loadKeys" />
          <n-button type="primary" @click="loadKeys">搜索</n-button>
        </div>
        <n-data-table :columns="keyColumns" :data="keys" :loading="loadingKeys" :pagination="{ pageSize: 20 }" :bordered="false" size="small" />
      </n-tab-pane>

      <n-tab-pane name="model" tab="模型与配置">
        <n-card title="视频理解模型" :bordered="false" class="model-card">
          <div class="model-row">
            <div class="model-label">当前生效</div>
            <n-tag type="success" size="large" round>{{ settings.default_model || '未配置' }}</n-tag>
          </div>
          <div class="model-row">
            <div class="model-label">修改为</div>
            <n-input v-model:value="modelInput" placeholder="例如 gemini-3.6-flash-high" style="max-width:360px" />
            <n-button type="primary" :loading="savingModel" @click="saveModel">保存</n-button>
          </div>
          <n-alert type="info" :bordered="false" class="model-note">
            模型名修改后对下一个排队任务立即生效（无需重启）。环境变量默认值：<code>{{ settings.configured_model }}</code>
          </n-alert>
        </n-card>

        <n-card title="并发与配额（只读）" :bordered="false" class="model-card">
          <div class="kv-grid">
            <div><span>游客全局并发</span><strong>{{ settings.concurrency?.guest_global }}</strong></div>
            <div><span>用户并发</span><strong>{{ settings.concurrency?.user }}</strong></div>
            <div><span>VIP 并发</span><strong>{{ settings.concurrency?.vip }}</strong></div>
            <div><span>全站硬上限</span><strong>{{ settings.concurrency?.global_hard_cap }}</strong></div>
            <div><span>Worker 数</span><strong>{{ settings.worker_count }}</strong></div>
            <div><span>理解模式</span><strong>{{ settings.understand_mode }}</strong></div>
          </div>
          <n-alert type="warning" :bordered="false">
            并发上限与 Worker 数来自环境变量，修改后需重启 worker 服务才生效。
          </n-alert>
        </n-card>
      </n-tab-pane>
    </n-tabs>

    <n-modal v-model:show="userModalShow" preset="card" title="编辑用户" style="max-width:460px">
      <n-form label-placement="left" label-width="90">
        <n-form-item label="邮箱">{{ editUser?.email }}</n-form-item>
        <n-form-item label="等级">
          <n-select v-model:value="editForm.tier" :options="tierOptions" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="editForm.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="editForm.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="userModalShow = false">取消</n-button>
        <n-button type="primary" :loading="savingUser" @click="saveUser" style="margin-left:8px">保存</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, h, onMounted } from 'vue'
import { NButton, NTag, NSwitch, useMessage } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { api } from '@/utils/api'

interface AdminStats { users?: any; jobs?: any; api_keys?: any; default_model?: string }
interface AdminUser { id: number; email: string; tier: string; role: string; is_active: boolean; has_password: boolean; created_at: string | null; job_count: number; api_key_count: number }
interface AdminJob { job_id: string; status: string; stage: string; progress: number; mode: string; user_id: number | null; user_email: string | null; input_type: string | null; input_url: string | null; created_at: string | null; updated_at: string | null; error: string | null }
interface AdminKey { id: number; user_id: number; user_email: string | null; name: string; key_prefix: string; is_active: boolean; created_at: string | null; last_used_at: string | null }
interface AdminSettings { default_model?: string; configured_model?: string; concurrency?: any; worker_count?: number; understand_mode?: string; note?: string }

const _m: any = useMessage()
const message = _m || { success: (t: string) => console.log(t), error: (t: string) => console.error(t), warning: (t: string) => console.warn(t) }

const stats = ref<AdminStats>({})
const users = ref<AdminUser[]>([])
const jobs = ref<AdminJob[]>([])
const keys = ref<AdminKey[]>([])
const settings = ref<AdminSettings>({})

const userQuery = ref('')
const jobStatus = ref<string | null>(null)
const jobEmail = ref('')
const keyEmail = ref('')
const statusOptions = [
  { label: '排队', value: 'queued' },
  { label: '运行中', value: 'running' },
  { label: '成功', value: 'succeeded' },
  { label: '失败', value: 'failed' },
]
const tierOptions = [
  { label: '普通用户', value: 'user' },
  { label: 'VIP', value: 'vip' },
]
const roleOptions = [
  { label: '普通', value: 'user' },
  { label: '管理员', value: 'admin' },
]

const loadingUsers = ref(false)
const loadingJobs = ref(false)
const loadingKeys = ref(false)

const userModalShow = ref(false)
const editUser = ref<AdminUser | null>(null)
const editForm = reactive<{ tier: string; role: string; is_active: boolean }>({ tier: 'user', role: 'user', is_active: true })
const savingUser = ref(false)
const modelInput = ref('')
const savingModel = ref(false)

const statusType: Record<string, 'default' | 'info' | 'success' | 'error'> = { queued: 'default', running: 'info', succeeded: 'success', failed: 'error' }

function fmt(d: string | null) { return d ? new Date(d).toLocaleString('zh-CN', { hour12: false }) : '-' }

async function loadStats() { try { stats.value = await api('/api/v1/admin/stats') } catch (e: any) { message.error('加载统计失败: ' + e.message) } }
async function loadUsers() {
  loadingUsers.value = true
  try { const r: any = await api('/api/v1/admin/users?q=' + encodeURIComponent(userQuery.value) + '&page_size=200'); users.value = r.items } catch (e: any) { message.error('加载用户失败: ' + e.message) } finally { loadingUsers.value = false }
}
async function loadJobs() {
  loadingJobs.value = true
  try {
    const p = new URLSearchParams({ page_size: '200' })
    if (jobStatus.value) p.set('status', jobStatus.value)
    if (jobEmail.value.trim()) p.set('email', jobEmail.value.trim())
    const r: any = await api('/api/v1/admin/jobs?' + p.toString()); jobs.value = r.items
  } catch (e: any) { message.error('加载记录失败: ' + e.message) } finally { loadingJobs.value = false }
}
async function loadKeys() {
  loadingKeys.value = true
  try {
    const qs = keyEmail.value.trim() ? ('&email=' + encodeURIComponent(keyEmail.value.trim())) : ''
    const r: any = await api('/api/v1/admin/api-keys?page_size=200' + qs); keys.value = r.items
  } catch (e: any) { message.error('加载密钥失败: ' + e.message) } finally { loadingKeys.value = false }
}
async function loadSettings() { try { const r: any = await api('/api/v1/admin/settings'); settings.value = r; modelInput.value = r.default_model || '' } catch (e: any) { message.error('加载配置失败: ' + e.message) } }

function openEdit(u: AdminUser) { editUser.value = u; editForm.tier = u.tier; editForm.role = u.role; editForm.is_active = u.is_active; userModalShow.value = true }
async function saveUser() {
  if (!editUser.value) return
  savingUser.value = true
  try {
    await api('/api/v1/admin/users/' + editUser.value.id, { method: 'PATCH', json: { tier: editForm.tier, role: editForm.role, is_active: editForm.is_active } })
    message.success('已保存'); userModalShow.value = false; await loadUsers(); await loadStats()
  } catch (e: any) { message.error('保存失败: ' + e.message) } finally { savingUser.value = false }
}
async function toggleKey(k: AdminKey) {
  try { await api('/api/v1/admin/api-keys/' + k.id, { method: 'PATCH', json: { is_active: !k.is_active } }); message.success('已更新'); await loadKeys() }
  catch (e: any) { message.error('操作失败: ' + e.message) }
}
async function deleteKey(k: AdminKey) {
  if (!confirm('确认删除该 API 密钥？此操作不可恢复。')) return
  try { await api('/api/v1/admin/api-keys/' + k.id, { method: 'DELETE' }); message.success('已删除'); await loadKeys() }
  catch (e: any) { message.error('删除失败: ' + e.message) }
}
async function saveModel() {
  if (!modelInput.value.trim()) { message.warning('请输入模型名'); return }
  savingModel.value = true
  try { const r: any = await api('/api/v1/admin/settings', { method: 'PATCH', json: { default_model: modelInput.value.trim() } }); message.success('模型已更新为 ' + r.default_model); await loadSettings(); await loadStats() }
  catch (e: any) { message.error('保存失败: ' + e.message) } finally { savingModel.value = false }
}

const userColumns: DataTableColumns<AdminUser> = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '邮箱', key: 'email', ellipsis: { tooltip: true } },
  { title: '等级', key: 'tier', width: 90, render: (r) => h(NTag, { type: r.tier === 'vip' ? 'warning' : 'default', size: 'small', round: true }, { default: () => r.tier === 'vip' ? 'VIP' : '普通' }) },
  { title: '角色', key: 'role', width: 90, render: (r) => h(NTag, { type: r.role === 'admin' ? 'error' : 'default', size: 'small', round: true }, { default: () => r.role === 'admin' ? '管理员' : '用户' }) },
  { title: '任务', key: 'job_count', width: 70 },
  { title: '密钥', key: 'api_key_count', width: 70 },
  { title: '状态', key: 'is_active', width: 80, render: (r) => h(NTag, { type: r.is_active ? 'success' : 'error', size: 'small' }, { default: () => r.is_active ? '启用' : '禁用' }) },
  { title: '注册时间', key: 'created_at', width: 160, render: (r) => fmt(r.created_at) },
  { title: '操作', key: 'op', width: 90, render: (r) => h(NButton, { size: 'small', tertiary: true, onClick: () => openEdit(r) }, { default: () => '编辑' }) },
]
const jobColumns: DataTableColumns<AdminJob> = [
  { title: '任务ID', key: 'job_id', width: 200, ellipsis: { tooltip: true } },
  { title: '状态', key: 'status', width: 90, render: (r) => h(NTag, { type: statusType[r.status] || 'default', size: 'small' }, { default: () => r.status }) },
  { title: '模式', key: 'mode', width: 110 },
  { title: '进度', key: 'progress', width: 70, render: (r) => (r.progress || 0) + '%' },
  { title: '用户', key: 'user_email', ellipsis: { tooltip: true }, render: (r) => r.user_email || (r.user_id ? ('#' + r.user_id) : '游客') },
  { title: '输入', key: 'input_url', ellipsis: { tooltip: true }, render: (r) => r.input_url || r.input_type || '-' },
  { title: '时间', key: 'created_at', width: 160, render: (r) => fmt(r.created_at) },
]
const keyColumns: DataTableColumns<AdminKey> = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '用户', key: 'user_email', ellipsis: { tooltip: true }, render: (r) => r.user_email || ('#' + r.user_id) },
  { title: '名称', key: 'name', width: 120 },
  { title: '前缀', key: 'key_prefix', width: 120, render: (r) => r.key_prefix + '...' },
  { title: '状态', key: 'is_active', width: 80, render: (r) => h(NTag, { type: r.is_active ? 'success' : 'error', size: 'small' }, { default: () => r.is_active ? '启用' : '禁用' }) },
  { title: '最近使用', key: 'last_used_at', width: 160, render: (r) => fmt(r.last_used_at) },
  { title: '操作', key: 'op', width: 150, render: (r) => [h(NButton, { size: 'small', tertiary: true, type: r.is_active ? 'error' : 'success', onClick: () => toggleKey(r) }, { default: () => r.is_active ? '禁用' : '启用' }), h(NButton, { size: 'small', tertiary: true, type: 'error', onClick: () => deleteKey(r), style: 'margin-left:8px' }, { default: () => '删除' })] },
]

onMounted(() => { loadStats(); loadUsers(); loadJobs(); loadKeys(); loadSettings() })
</script>

<style scoped>
.admin-page { padding: 28px 36px 60px; max-width: 1200px; margin: 0 auto; }
.admin-head { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; }
.admin-head h1 { font-size: 1.7rem; font-weight: 800; color: var(--text-main); margin: 0; }
.admin-head .sub { color: var(--text-muted); margin: 6px 0 0; font-size: 0.92rem; }
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 8px; }
.stat-card { background: var(--bg-card); border: 1px solid var(--border-strong); border-radius: 14px; padding: 18px 20px; }
.stat-label { font-size: 0.82rem; color: var(--text-muted); }
.stat-value { font-size: 1.9rem; font-weight: 800; color: var(--emerald-deep); margin: 6px 0 2px; }
.stat-value.model-mini { font-size: 1.1rem; word-break: break-all; }
.stat-foot { font-size: 0.8rem; color: var(--text-dim); }
.toolbar { display: flex; gap: 10px; align-items: center; margin: 8px 0 16px; }
.model-card { margin-top: 14px; }
.model-row { display: flex; align-items: center; gap: 14px; margin: 10px 0; }
.model-label { width: 120px; color: var(--text-muted); font-size: 0.9rem; }
.model-note { margin-top: 14px; }
.kv-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; }
.kv-grid div { display: flex; justify-content: space-between; background: var(--bg-subtle); padding: 10px 14px; border-radius: 10px; font-size: 0.88rem; }
.kv-grid span { color: var(--text-muted); }
.kv-grid strong { color: var(--emerald-deep); }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } .kv-grid { grid-template-columns: 1fr; } }
</style>