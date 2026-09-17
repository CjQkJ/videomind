<template>
  <div class="progress-block">
    <div class="progress-header">
      <div class="status-title-box">
        <n-spin size="small" v-if="running" />
        <span class="title-text">{{ title }}</span>
      </div>
      <slot name="action"></slot>
    </div>
    <div class="stage-timeline">
      <div class="stage-item" :class="{ active: stageStep>=1, done: stageStep>1 }"><div class="step-icon"><StoryIcons name="frame" :size="20" /></div><div class="step-name">素材入库</div></div>
      <div class="stage-line" :class="{ active: stageStep>1 }"></div>
      <div class="stage-item" :class="{ active: stageStep>=2, done: stageStep>2 }"><div class="step-icon"><StoryIcons name="retrieve" :size="20" /></div><div class="step-name">寻回原片</div></div>
      <div class="stage-line" :class="{ active: stageStep>2 }"></div>
      <div class="stage-item" :class="{ active: stageStep>=3, done: stageStep>3 }"><div class="step-icon"><StoryIcons name="decode" :size="20" /></div><div class="step-name">AI 解码</div></div>
      <div class="stage-line" :class="{ active: stageStep>3 }"></div>
      <div class="stage-item" :class="{ active: stageStep>=4, done: stageStep>=4 }"><div class="step-icon"><StoryIcons name="crystal" :size="20" /></div><div class="step-name">知识结晶</div></div>
    </div>
    <n-progress
      type="line"
      :percentage="progress"
      indicator-placement="inside"
      processing
      :color="'#10b981'"
      :rail-color="'rgba(16,185,129,0.15)'"
      height="20"
    />
    <div class="progress-footer-info">
      <span class="msg-text">{{ message }}</span>
      <span v-if="segmentInfo" class="seg-text">{{ segmentInfo }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import StoryIcons from '@/components/StoryIcons.vue'

defineProps<{
  stageStep: number
  progress: number
  message: string
  segmentInfo: string
  title: string
  running: boolean
}>()
</script>

<style scoped>
.progress-block { width:100% }
.progress-header { display:flex;justify-content:space-between;align-items:center;margin-bottom:24px }
.status-title-box { display:flex;align-items:center;gap:12px }
.title-text { font-size:1.3rem;font-weight:800;color:#0f172a }
.stage-timeline { display:flex;align-items:center;justify-content:space-between;margin-bottom:32px;padding:0 16px }
.stage-item { display:flex;flex-direction:column;align-items:center;gap:8px;z-index:2 }
.step-icon { width:38px;height:38px;border-radius:50%;background:#ffffff;border:1px solid rgba(5,150,105,0.3);display:flex;align-items:center;justify-content:center;color:#475569;transition:all 0.3s ease }
.stage-item.active .step-icon { background:rgba(16,185,129,0.12);border-color:#d97706;box-shadow:0 0 18px rgba(16,185,129,0.45),0 0 8px rgba(245,158,11,0.25) }
.stage-item.done .step-icon { background:rgba(245,158,11,0.14);border-color:#d97706;box-shadow:0 0 12px rgba(245,158,11,0.35) }
.step-name { font-size:0.88rem;color:#475569;font-weight:500;white-space:nowrap }
.stage-item.active .step-name { color:#b45309;font-weight:700 }
.stage-item.done .step-name { color:#065f46;font-weight:600 }
.stage-line { flex:1;height:2px;background:rgba(5,150,105,0.2);margin:0 8px 24px }
.stage-line.active { background:linear-gradient(90deg,#10b981,#f59e0b) }
.progress-footer-info { display:flex;justify-content:space-between;margin-top:12px;font-size:0.9rem;color:#475569 }
</style>
