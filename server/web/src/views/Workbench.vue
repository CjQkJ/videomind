<template>
  <div class="wb-split">
    <!-- 左栏：提交 + 最近任务 -->
    <section class="wb-left">
      <n-card class="wb-card submit-card" :bordered="false">
        <div class="card-title"><span class="card-title-dot"></span>提交任务</div>
        <n-tabs type="segment" v-model:value="inputMode" animated class="custom-tabs">
          <n-tab-pane name="url"><template #tab>B 站链接</template>
            <div class="input-box-wrapper">
              <n-input v-model:value="bilibiliUrl" placeholder="粘贴 B 站视频链接 (BV... 或 b23.tv)" size="large" clearable>
                <template #prefix><span class="bilibili-icon">BILI</span></template>
              </n-input>
            </div>
          </n-tab-pane>
          <n-tab-pane name="upload"><template #tab>本地上传</template>
            <div class="input-box-wrapper">
              <n-upload action="/api/v1/uploads" :headers="uploadHeaders" accept="video/*" :max="1" @finish="handleUploadFinish" @error="handleUploadError">
                <n-upload-dragger class="custom-dragger">
                  <div class="dragger-text">点击或拖拽视频</div>
                  <div class="dragger-subtext">mp4 / mov / mkv / webm / m4v，最大 500M</div>
                </n-upload-dragger>
              </n-upload>
            </div>
          </n-tab-pane>
        </n-tabs>

        <div class="mode-section">
          <div class="mode-label">选择输出模式</div>
          <ModeSelectGrid v-model="outputMode" :options="modeOptions" />
        </div>

        <div class="action-footer">
          <n-button type="primary" size="large" block class="start-btn" @click="startJob" :loading="starting" :disabled="(inputMode==='url' && !bilibiliUrl) || (inputMode==='upload' && !fileId)">⚡ 开启萃取</n-button>
          <div v-if="createHint" class="create-hint-msg">{{ createHint }}</div>
        </div>
      </n-card>
    </section>

    <!-- 右栏：状态 / 结果 -->
    <section class="wb-right">
      <!-- 空闲 -->
      <div v-if="!jobId" class="wb-idle">
        <WorkbenchGuide @use-sample="fillSampleUrl" />
      </div>

      <!-- 运行中 -->
      <n-card v-else-if="status==='queued' || status==='running' || status===''" class="wb-card progress-card" :bordered="false">
        <ProgressTimeline
          :stage-step="stageStep"
          :progress="progress"
          :message="progressMsg || '正在深度理解视频画面与语音...'"
          :segment-info="segmentInfo"
          :title="status==='queued' ? '任务正在队列中等待调度...' : 'Gemini 原生多模态解析中...'"
          :running="status==='running'"
        >
          <template #action><n-button size="small" secondary @click="reset">返回</n-button></template>
        </ProgressTimeline>
      </n-card>

      <!-- 结果 -->
      <n-card v-else class="wb-card result-card" :bordered="false">
        <div class="result-header">
          <div class="title-group">
            <h2 :class="{ 'error-title': status==='failed' }">{{ status==='failed' ? '解析执行中断' : ((metadata.title) || '交付结果') }}</h2>
            <div class="meta-row" v-if="status==='succeeded'">
              <span class="meta-pill crystal-pill"><StoryIcons name="crystal" :size="13" /> 知识已结晶</span>
              <span class="meta-pill">UP: {{ metadata.uploader || '未知' }}</span>
              <span class="meta-pill">时长 {{ metadata.duration_sec || 0 }}s</span>
              <span class="meta-pill gold-pill">模式: {{ currentResultMode }}</span>
            </div>
          </div>
          <n-button size="small" secondary @click="reset">创建新任务</n-button>
        </div>
        <div class="error-msg-box" v-if="status==='failed'">
          <div class="err-icon">⚠️</div>
          <div class="err-content"><div class="err-title">执行异常说明</div><div class="err-desc">{{ progressMsg }}</div></div>
        </div>
        <div class="result-body" v-if="status==='succeeded'">
          <ResultToolbar
            v-model:result-view="resultView"
            v-model:rerender-mode="rerenderMode"
            :mode-options="modeOptions"
            :current-result-mode="currentResultMode"
            :rerendering="rerendering"
            :html-preview-loading="htmlPreviewLoading"
            @rerender="handleRerender"
            @copy="copyMarkdown"
            @download-md="downloadMarkdown"
            @download-json="downloadJson"
            @open-html="openHtml"
          />
          <div class="result-content-container">
            <div class="markdown-view" v-if="resultView==='md'"><div class="markdown-body" v-html="renderedMarkdown"></div></div>
            <div class="json-view" v-if="resultView==='json'"><pre class="code-block"><code>{{ resultJsonStr }}</code></pre></div>
          </div>
        </div>
      </n-card>
    </section>

    <n-modal v-model:show="htmlPreviewVisible" preset="card" title="网页讲义预览" class="html-preview-modal">
      <iframe
        class="html-preview-frame"
        title="网页讲义安全预览"
        sandbox=""
        referrerpolicy="no-referrer"
        :srcdoc="teachingHtmlPreview"
      ></iframe>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/utils/api'
import { renderSafeMarkdown, renderSandboxedHtml } from '@/utils/safeMarkdown'
import { useMessage } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import ModeSelectGrid from '@/components/ModeSelectGrid.vue'
import ProgressTimeline from '@/components/ProgressTimeline.vue'
import ResultToolbar from '@/components/ResultToolbar.vue'
import WorkbenchGuide from '@/components/WorkbenchGuide.vue'
import StoryIcons from '@/components/StoryIcons.vue'

const authStore = useAuthStore()
const message = useMessage()
const route = useRoute()
const router = useRouter()

const showInput = ref(true)
const inputMode = ref<'url'|'upload'>('url')
const bilibiliUrl = ref('')
const fileId = ref('')
const outputMode = ref('study_note')
const createHint = ref('')
const starting = ref(false)

const modeOptions = [
  { label:'学习笔记', value:'study_note', icon:'📝', desc:'深度提炼核心概念、逻辑步骤与关键论点，适合日常高效吸收。' },
  { label:'对外成稿', value:'article', icon:'📰', desc:'转换为行文流畅的长文/博客排版，适合直接公开发布与分享。' },
  { label:'知识卡片', value:'cards', icon:'🎴', desc:'极简金句与重点清单抽取，适合快刷与卡片笔记沉淀。' },
  { label:'教学讲义 HTML', value:'teaching_html', icon:'🏫', desc:'自动生成带视觉排版与结构模块划分的可视化网页教学课件。' },
]

const uploadHeaders = computed(() => authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {})
const handleUploadFinish = ({ event }: { event?: ProgressEvent }) => {
  try { const r = JSON.parse((event?.target as XMLHttpRequest).response); fileId.value = r.file_id; message.success('视频文件已成功上传') } catch { message.error('上传解析失败') }
}
const handleUploadError = () => message.error('视频上传失败')

const jobId = ref('')
const status = ref('')
const progress = ref(0)
const progressMsg = ref('')
const segmentInfo = ref('')
const metadata = ref<any>({})
const currentResultMode = ref('')
const markdownContent = ref('')
const resultJsonStr = ref('')
const resultView = ref<'md'|'json'>('md')
const rerenderMode = ref('study_note')
const rerendering = ref(false)
const htmlPreviewVisible = ref(false)
const htmlPreviewLoading = ref(false)
const teachingHtmlPreview = ref('')
const MAX_POLL_FAILURES = 3
const pollFailureCount = ref(0)
let pollTimer: number | null = null
let pollGeneration = 0

const stageStep = computed(() => {
  if (status.value === 'queued') return 1
  if (progress.value < 25) return 2
  if (progress.value < 80) return 3
  return 4
})
const renderedMarkdown = computed(() => renderSafeMarkdown(markdownContent.value))

const fillSampleUrl = () => {
  bilibiliUrl.value = 'https://www.bilibili.com/video/BV1WEg463EGK'
  inputMode.value = 'url'
  message.info('已填入 2 分钟教程视频，点击「开启萃取」即可体验')
}

const startJob = async () => {
  starting.value = true; createHint.value = ''
  try {
    const payload = { input: inputMode.value === 'url' ? { type:'bilibili_url', url:bilibiliUrl.value } : { type:'upload', file_id:fileId.value }, output: { mode:outputMode.value, formats:['json','markdown'] }, options:{ show_source:true } }
    const res = await api<any>('/api/v1/jobs', { method:'POST', json:payload })
    jobId.value = res.job_id; createHint.value = res.can_start_now ? '任务已提交，正在开启 Gemini 原生计算' : `已排队等待资源: ${res.queue_reason}`
    showInput.value = false; status.value = 'queued'; progress.value = 5; progressMsg.value = '等待调度...'
    startPoll(); router.replace({ query:{ jobId:jobId.value } })
  } catch (e:any) { message.error(e.message) } finally { starting.value = false }
}

const stopPolling = () => {
  pollGeneration += 1
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

const startPoll = () => {
  stopPolling()
  const generation = pollGeneration
  pollFailureCount.value = 0
  const tick = async () => {
    if (generation !== pollGeneration || !jobId.value) return
    await checkJobStatus(generation)
    if (generation !== pollGeneration || !jobId.value || status.value === 'succeeded' || status.value === 'failed') return
    pollTimer = window.setTimeout(() => { void tick() }, 2000)
  }
  void tick()
}

const checkJobStatus = async (generation = pollGeneration) => {
  if (!jobId.value) return
  const requestedJobId = jobId.value
  try {
    const res = await api<any>(`/api/v1/jobs/${requestedJobId}`)
    if (generation !== pollGeneration || jobId.value !== requestedJobId) return
    pollFailureCount.value = 0
    status.value = res.status; progress.value = res.progress || 0; progressMsg.value = res.message || res.error || ''
    if (res.quota) authStore.quota = res.quota
    segmentInfo.value = res.segment_total > 0 ? `分段 ${res.segment_done||0}/${res.segment_total}` : ''
    if (res.status === 'succeeded') { stopPolling(); await fetchResult() }
    else if (res.status === 'failed') { stopPolling(); message.error(progressMsg.value) }
  } catch {
    if (generation !== pollGeneration || jobId.value !== requestedJobId) return
    pollFailureCount.value += 1
    if (pollFailureCount.value >= MAX_POLL_FAILURES) {
      stopPolling()
      status.value = 'failed'
      progressMsg.value = '任务状态连续 3 次获取失败，请检查网络后重试。'
      message.error(progressMsg.value)
    }
  }
}

const fetchResult = async () => {
  const requestedJobId = jobId.value
  try {
    const meta = await api<any>(`/api/v1/jobs/${requestedJobId}/result`)
    if (jobId.value !== requestedJobId) return
    metadata.value = meta.metadata || {}; currentResultMode.value = meta.mode || ''; rerenderMode.value = currentResultMode.value || 'study_note'
    const markdown = await api<string>(`/api/v1/jobs/${requestedJobId}/result.md`)
    if (jobId.value !== requestedJobId) return
    markdownContent.value = markdown
    try {
      const j = await api<any>(`/api/v1/jobs/${requestedJobId}/result.json`)
      if (jobId.value === requestedJobId) resultJsonStr.value = JSON.stringify(j,null,2)
    } catch {
      if (jobId.value === requestedJobId) resultJsonStr.value = '{}'
    }
  } catch (e:any) {
    if (jobId.value === requestedJobId) message.error('获取结果失败: '+e.message)
  }
}

const handleRerender = async () => {
  const requestedJobId = jobId.value
  rerendering.value = true
  try {
    const res = await api<any>(`/api/v1/jobs/${requestedJobId}/rerender`, { method:'POST', json:{ mode:rerenderMode.value, show_source:true } })
    if (jobId.value !== requestedJobId) return
    markdownContent.value = res.markdown || ''; currentResultMode.value = res.mode; message.success(`重渲为 [${res.mode}] 成功`)
  } catch (e:any) {
    if (jobId.value === requestedJobId) message.error(e.message)
  } finally {
    if (jobId.value === requestedJobId) rerendering.value = false
  }
}

const copyMarkdown = async () => { try { await navigator.clipboard.writeText(markdownContent.value); message.success('Markdown 已复制到剪贴板') } catch { message.error('复制失败') } }
const downloadMarkdown = () => { const b=new Blob([markdownContent.value],{type:'text/markdown;charset=utf-8'}); const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download=`VideoMind_${(metadata.value.title||jobId.value).replace(/[^\w一-鿿\-]+/g,'_')}_${currentResultMode.value}.md`; a.click(); URL.revokeObjectURL(a.href); message.success('Markdown 笔记已开始下载') }
const downloadJson = () => { const b=new Blob([resultJsonStr.value],{type:'application/json;charset=utf-8'}); const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download=`VideoMind_${(metadata.value.title||jobId.value).replace(/[^\w一-鿿\-]+/g,'_')}_canonical.json`; a.click(); URL.revokeObjectURL(a.href); message.success('Canonical JSON 数据已开始下载') }
const openHtml = async () => {
  const requestedJobId = jobId.value
  htmlPreviewLoading.value = true
  try {
    const html = await api<string>(`/api/v1/jobs/${requestedJobId}/result.html`)
    if (jobId.value !== requestedJobId) return
    teachingHtmlPreview.value = renderSandboxedHtml(html)
    htmlPreviewVisible.value = true
  } catch (e:any) {
    if (jobId.value === requestedJobId) message.error('获取网页讲义失败: '+e.message)
  } finally {
    if (jobId.value === requestedJobId) htmlPreviewLoading.value = false
  }
}
const reset = () => {
  stopPolling()
  pollFailureCount.value=0
  bilibiliUrl.value=''
  fileId.value=''
  outputMode.value='study_note'
  inputMode.value='url'
  createHint.value=''
  starting.value=false
  status.value=''
  progress.value=0
  progressMsg.value=''
  segmentInfo.value=''
  metadata.value={}
  currentResultMode.value=''
  markdownContent.value=''
  resultJsonStr.value=''
  resultView.value='md'
  rerenderMode.value='study_note'
  rerendering.value=false
  htmlPreviewVisible.value=false
  htmlPreviewLoading.value=false
  teachingHtmlPreview.value=''
  jobId.value=''
  showInput.value=true
  router.replace({query:{}})
}

watch(()=>route.query.jobId, async (newId) => {
  if (newId) { const nextId=String(newId); stopPolling(); pollFailureCount.value=0;htmlPreviewVisible.value=false;htmlPreviewLoading.value=false;teachingHtmlPreview.value='';jobId.value=nextId;showInput.value=false
    try { const res=await api<any>(`/api/v1/jobs/${nextId}`); if (jobId.value !== nextId) return; pollFailureCount.value=0; status.value=res.status||'';progress.value=res.progress||0;progressMsg.value=res.message||res.error||'';if(res.quota) authStore.quota=res.quota;segmentInfo.value=res.segment_total>0?`分段 ${res.segment_done||0}/${res.segment_total}`:''
       if(res.status==='succeeded') await fetchResult(); else if(res.status==='failed'){} else startPoll() } catch { if (jobId.value !== nextId) return; status.value='running';startPoll() }
  } else { stopPolling(); pollFailureCount.value=0;jobId.value='';showInput.value=true;status.value='';progress.value=0;progressMsg.value='';segmentInfo.value='';metadata.value={};currentResultMode.value='';markdownContent.value='';resultJsonStr.value='';htmlPreviewVisible.value=false;htmlPreviewLoading.value=false;teachingHtmlPreview.value='' }
},{immediate:true})

onUnmounted(() => { stopPolling() })
</script>

<style scoped>
.wb-split { display: flex; gap: 24px; align-items: flex-start; justify-content: center }
.wb-left { width: 440px; flex-shrink: 0; display: flex; flex-direction: column; gap: 18px; position: sticky; top: 84px }
.wb-right { flex: 0 1 780px; min-width: 0; max-width: 780px }
.wb-card { padding: 14px 10px }
.card-title { display: flex; align-items: center; gap: 9px; font-size: 1.05rem; font-weight: 700; color: var(--text-main); margin-bottom: 16px }
.card-title-dot { width: 9px; height: 9px; border-radius: 2px; background: var(--emerald-primary); box-shadow: 0 0 6px rgba(14,159,110,0.5) }
.input-box-wrapper { padding: 14px 0 6px }
.bilibili-icon { background: #fb7299; color: #fff; font-weight: 800; font-size: 0.65rem; padding: 2px 5px; border-radius: 4px }
.custom-dragger { background: var(--bg-subtle) !important; border: 1px dashed var(--border-strong) !important; border-radius: 10px }
.dragger-text { font-size: 1rem; font-weight: 700; color: var(--text-main) } .dragger-subtext { font-size: 0.82rem; color: var(--text-muted); margin-top: 4px }
.mode-section { margin-top: 14px; margin-bottom: 16px }
.mode-label { font-size: 0.95rem; font-weight: 600; color: var(--text-muted); margin-bottom: 12px }
.start-btn { height: 54px; font-size: 1.05rem; border-radius: 11px }
.create-hint-msg { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: var(--text-muted) }

.wb-idle { display: flex; align-items: flex-start; justify-content: center }
.progress-card { padding: 16px }
.result-card { padding: 8px 4px }
.result-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--border-soft) }
.title-group h2 { font-size: 1.4rem; font-weight: 800; color: var(--text-main); margin-bottom: 8px; word-break: break-word }
.error-title { color: var(--danger) !important }
.meta-row { display: flex; gap: 8px; flex-wrap: wrap }
.meta-pill { font-size: 0.78rem; padding: 3px 10px; border-radius: 6px; background: var(--bg-subtle); border: 1px solid var(--border-soft); color: var(--text-muted) }
.meta-pill.gold-pill { background: var(--warning-soft); color: var(--warning); border-color: rgba(217,119,6,0.3) }
.crystal-pill { display: inline-flex; align-items: center; gap: 5px; background: var(--warning-soft); color: var(--warning); border-color: rgba(217,119,6,0.3); font-weight: 600 }
.error-msg-box { display: flex; gap: 14px; padding: 16px; background: var(--danger-soft); border: 1px solid rgba(220,38,38,0.25); border-radius: 10px; margin-bottom: 14px }
.err-icon { font-size: 1.6rem } .err-title { font-weight: 700; color: var(--danger); margin-bottom: 4px } .err-desc { color: #b91c1c; font-size: 0.88rem }
.result-content-container { background: var(--bg-card); border: 1px solid var(--border-strong); border-radius: 10px; padding: 24px; max-height: 70vh; overflow-y: auto }
.markdown-body { font-size: 0.96rem; line-height: 1.8; color: var(--text-main) }
.markdown-body :deep(h1){font-size:1.6rem;border-bottom:1px solid var(--border-soft);padding-bottom:10px;margin:14px 0 16px;color:var(--text-main)}
.markdown-body :deep(h2){font-size:1.3rem;margin:22px 0 12px;color:var(--emerald-deep)}
.markdown-body :deep(h3){font-size:1.1rem;margin:18px 0 8px;color:var(--text-main)}
.markdown-body :deep(blockquote){border-left:3px solid var(--warning);padding:8px 16px;background:var(--warning-soft);border-radius:0 8px 8px 0;margin:14px 0;color:#92400e}
.markdown-body :deep(code){background:var(--emerald-soft);padding:2px 6px;border-radius:5px;font-family:monospace;font-size:0.9em;color:var(--emerald-deep)}
.markdown-body :deep(pre){background:#0f2e22;border:1px solid rgba(14,159,110,0.4);padding:16px;border-radius:10px;overflow-x:auto}
.markdown-body :deep(pre code){background:transparent;padding:0;color:#bbf7d0}
.markdown-body :deep(a){color:var(--emerald-deep)}
.code-block { font-family:monospace; font-size:0.9rem; color:var(--text-main); white-space:pre-wrap; word-break:break-all }
.html-preview-modal { width: min(1200px, calc(100vw - 32px)) }
.html-preview-frame { display: block; width: 100%; height: min(78vh, 900px); border: 0; background: #fff }

@media (max-width: 900px) {
  .wb-split { flex-direction: column }
  .wb-left { width: 100%; position: static }
  .wb-right { width: 100% }
  .wb-idle { min-height: 300px }
}
</style>
