<template>
  <div class="story-empty">
    <div class="empty-art"><StoryJourney size="sm" compact /></div>
    <div v-if="title" class="empty-title">{{ title }}</div>
    <div v-if="description" class="empty-desc">{{ description }}</div>
    <div v-if="$slots.default" class="empty-extra"><slot></slot></div>
  </div>
</template>

<script setup lang="ts">
import StoryJourney from '@/components/StoryJourney.vue'

withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  { title: '', description: '' },
)
</script>

<style scoped>
.story-empty { display:flex;flex-direction:column;align-items:center;text-align:center;gap:8px;padding:24px 12px }
.empty-art { opacity:0.9;margin-bottom:4px }
.empty-title { font-size:1.15rem;font-weight:800;color:#0f172a }
.empty-desc { font-size:0.9rem;color:#475569;line-height:1.6;max-width:420px }
.empty-extra { margin-top:6px }
</style>
