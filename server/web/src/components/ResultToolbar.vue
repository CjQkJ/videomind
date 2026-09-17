<template>
  <div class="toolbar">
    <n-radio-group :value="resultView" size="medium" @update:value="(v: any) => emit('update:resultView', v)">
      <n-radio-button value="md">Markdown 预览</n-radio-button>
      <n-radio-button value="json">Canonical JSON</n-radio-button>
    </n-radio-group>
    <div class="right-tools">
      <n-select
        :value="rerenderMode"
        :options="modeOptions"
        style="width:140px"
        size="small"
        @update:value="(v: string) => emit('update:rerenderMode', v)"
      />
      <n-button size="small" secondary @click="emit('rerender')" :loading="rerendering">切换重渲</n-button>
      <n-button size="small" type="primary" secondary @click="emit('copy')">复制 MD</n-button>
      <n-button size="small" type="success" secondary @click="emit('download-md')">📥 下载 MD</n-button>
      <n-button size="small" type="warning" secondary @click="emit('download-json')">📥 下载 JSON</n-button>
      <n-button v-if="currentResultMode==='teaching_html'" size="small" type="info" secondary @click="emit('open-html')" :loading="htmlPreviewLoading">网页讲义</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ModeOption } from '@/components/ModeSelectGrid.vue'

defineProps<{
  resultView: 'md' | 'json'
  rerenderMode: string
  modeOptions: ModeOption[]
  currentResultMode: string
  rerendering: boolean
  htmlPreviewLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:resultView', v: 'md' | 'json'): void
  (e: 'update:rerenderMode', v: string): void
  (e: 'rerender'): void
  (e: 'copy'): void
  (e: 'download-md'): void
  (e: 'download-json'): void
  (e: 'open-html'): void
}>()
</script>

<style scoped>
.toolbar { display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:12px }
.right-tools { display:flex;align-items:center;gap:10px;flex-wrap:wrap }
</style>
