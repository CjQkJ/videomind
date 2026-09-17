<template>
  <div
    class="story-journey"
    :class="[`size-${size}`, { compact }]"
    role="img"
    aria-label="从视频到知识的转化旅程"
  >
    <svg viewBox="0 0 320 120" class="journey-svg" aria-hidden="true">
      <!-- 素材：视频帧 -->
      <g class="stage-frame">
        <rect x="24" y="38" width="58" height="44" rx="7" fill="rgba(5,150,105,0.08)" stroke="#059669" stroke-width="2.5" class="frame-stroke" />
        <path d="M47 51v18l14-9z" fill="#059669" />
      </g>

      <!-- 解码：渐变光束 -->
      <g class="stage-beam">
        <path d="M86 60h148" stroke="#10b981" stroke-width="3.5" stroke-linecap="round" class="beam b1" />
        <path v-if="!compact" d="M94 44h104" stroke="#34d399" stroke-width="2" stroke-linecap="round" class="beam b2" />
        <path v-if="!compact" d="M94 76h104" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" class="beam b3" />
        <path v-if="!compact" d="M100 60h92" stroke="#a7f3d0" stroke-width="1.5" stroke-linecap="round" class="beam b4" />
      </g>

      <!-- 结晶：知识晶体 -->
      <g class="stage-crystal">
        <path d="M244 20l24 30-24 30-24-30z" fill="#d97706" />
        <path d="M244 20l-24 30 24 30" fill="#fbbf24" opacity="0.55" />
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'lg' | 'md' | 'sm'
    compact?: boolean
  }>(),
  { size: 'md', compact: false },
)
</script>

<style scoped>
.story-journey { width: 100% }
.journey-svg { width: 100%; height: auto; display: block }
.size-lg { max-width: 460px }
.size-md { max-width: 300px }
.size-sm { max-width: 200px }
.compact.size-lg { max-width: 320px }
.compact.size-md { max-width: 220px }
.compact.size-sm { max-width: 150px }

.frame-stroke { animation: frame-breathe 3s ease-in-out infinite; transform-origin: center }

.stage-beam .beam { animation: beam-pulse 2.2s ease-in-out infinite }
.stage-beam .b2 { animation-delay: 0.25s }
.stage-beam .b3 { animation-delay: 0.5s }
.stage-beam .b4 { animation-delay: 0.75s }

.stage-crystal { animation: crystal-breathe 2.6s ease-in-out infinite }
</style>
