<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    class="story-icon"
    :style="{ color: iconColor }"
    aria-hidden="true"
  >
    <!-- 视频帧：圆角矩形 + 播放三角 -->
    <template v-if="name === 'frame'">
      <rect x="3" y="5" width="18" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.8" />
      <path d="M10 9.5v5l4.5-2.5z" fill="currentColor" />
    </template>

    <!-- 解码光束：扫描线 -->
    <template v-else-if="name === 'decode'">
      <path d="M4 5l16 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <path d="M4 12h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <path d="M4 19l16-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>

    <!-- 知识晶体：菱形 + 切面高光 -->
    <template v-else-if="name === 'crystal'">
      <path d="M12 3l7 9-7 9-7-9z" fill="currentColor" />
      <path d="M12 3L5 12l7 9" fill="#ffffff" opacity="0.4" />
    </template>

    <!-- 寻回原片：下载箭头到托盘 -->
    <template v-else-if="name === 'retrieve'">
      <path d="M12 3v11m0 0l-4-4m4 4l4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M4 18v1a2 2 0 002 2h12a2 2 0 002-2v-1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>

    <!-- 成果书册 -->
    <template v-else-if="name === 'book'">
      <path d="M4 5.5A2.5 2.5 0 016.5 3H20v15H6.5A2.5 2.5 0 004 20.5z" fill="currentColor" opacity="0.18" />
      <path d="M4 5.5A2.5 2.5 0 016.5 3H20v15H6.5A2.5 2.5 0 004 20.5z" fill="none" stroke="currentColor" stroke-width="1.6" />
      <path d="M9 7.5h7M9 11.5h7" stroke="currentColor" stroke-width="1.3" opacity="0.55" />
    </template>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: 'frame' | 'decode' | 'crystal' | 'retrieve' | 'book'
    size?: number
  }>(),
  { size: 24 },
)

const iconColor = computed(() => {
  switch (props.name) {
    case 'crystal': return '#d97706'
    case 'decode': return '#10b981'
    case 'retrieve': return '#047857'
    default: return '#059669'
  }
})
</script>
