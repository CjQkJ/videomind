<template>
  <div class="guide-panel">
    <div class="guide-top">
      <StoryJourney size="lg" class="guide-journey" />
      <h2 class="guide-title">解码每一帧，<span class="grad-text">结晶你的知识</span></h2>
      <p class="guide-desc">提交一段视频，VideoMind 用原生多模态 AI 把画面、语音与细节，解码成结构化知识。</p>
    </div>

    <div class="guide-steps">
      <div class="step-card">
        <div class="step-icon"><StoryIcons name="frame" :size="22" /></div>
        <div class="step-info"><div class="step-name">提交素材</div><div class="step-desc">粘贴链接或上传视频</div></div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-card">
        <div class="step-icon"><StoryIcons name="decode" :size="22" /></div>
        <div class="step-info"><div class="step-name">AI 原生解码</div><div class="step-desc">音画同屏理解</div></div>
      </div>
      <div class="step-arrow">→</div>
      <div class="step-card">
        <div class="step-icon"><StoryIcons name="crystal" :size="22" /></div>
        <div class="step-info"><div class="step-name">结晶交付</div><div class="step-desc">笔记 / 卡片 / 讲义</div></div>
      </div>
    </div>

    <div class="guide-highlights">
      <span class="hl"><span class="hl-check">✓</span> 原生音画同屏理解</span>
      <span class="hl"><span class="hl-check">✓</span> 4 小时长视频切分</span>
      <span class="hl"><span class="hl-check">✓</span> 4 种输出模式</span>
    </div>

    <div class="guide-sample">
      <span class="sample-text">没有素材？试试这个 2 分钟教程</span>
      <n-button size="small" type="primary" secondary @click="$emit('use-sample')">填入测试视频</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import StoryJourney from '@/components/StoryJourney.vue'
import StoryIcons from '@/components/StoryIcons.vue'

defineEmits<{ (e: 'use-sample'): void }>()
</script>

<style scoped>
.guide-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 26px;
  padding: 48px 48px;
  background: var(--panel-gradient);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  box-shadow: 0 2px 12px -4px rgba(15, 23, 42, 0.06);
}
.guide-top { text-align: center }
.guide-journey { max-width: 520px; margin: 0 auto 10px }
.guide-title { font-size: 1.9rem; font-weight: 900; color: var(--text-main); margin: 0 0 10px; letter-spacing: -0.01em }
.grad-text { background: var(--brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text }
.guide-desc { font-size: 0.95rem; line-height: 1.75; color: var(--text-muted); max-width: 500px; margin: 0 auto }

.guide-steps { display: flex; align-items: stretch; gap: 10px; width: 100%; max-width: 620px }
.step-card {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 22px 14px; border-radius: 14px;
  background: var(--bg-card); border: 1px solid var(--border-strong);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.step-card:hover { border-color: rgba(14,159,110,0.45); transform: translateY(-2px); box-shadow: 0 8px 20px -8px rgba(14,159,110,0.2) }
.step-icon {
  width: 56px; height: 56px; border-radius: 14px;
  background: var(--emerald-soft); border: 1px solid rgba(14,159,110,0.3);
  display: flex; align-items: center; justify-content: center;
}
.step-info { text-align: center }
.step-name { font-size: 0.98rem; font-weight: 700; color: var(--text-main) }
.step-desc { font-size: 0.82rem; color: var(--text-muted); margin-top: 3px }
.step-arrow { display: flex; align-items: center; color: var(--emerald-primary); font-size: 1.2rem; font-weight: 700 }

.guide-highlights { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center }
.hl { display: inline-flex; align-items: center; gap: 7px; font-size: 0.85rem; font-weight: 500; color: var(--text-main); padding: 7px 16px; border-radius: 99px; background: var(--bg-card); border: 1px solid var(--border-strong) }
.hl-check { color: var(--emerald-primary); font-weight: 800 }

.guide-sample { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; justify-content: center }
.sample-text { font-size: 0.9rem; color: var(--text-muted) }

@media (max-width: 560px) {
  .guide-panel { padding: 28px 20px }
  .guide-steps { flex-direction: column; gap: 6px }
  .step-arrow { transform: rotate(90deg); justify-content: center; padding: 2px 0 }
  .step-card { flex-direction: row; align-items: center; justify-content: flex-start; padding: 14px 18px; text-align: left }
  .step-info { text-align: left }
  .step-icon { width: 46px; height: 46px }
}
</style>
