<template>
  <div class="page-header">
    <div class="ph-title">
      <h1 class="ph-h1">{{ title }}</h1>
      <p v-if="subtitle" class="ph-sub">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="ph-actions"><slot name="actions"></slot></div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{ title: string; subtitle?: string }>(),
  { subtitle: '' },
)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 20px; flex-wrap: wrap }
.ph-h1 { font-size: 1.5rem; font-weight: 800; color: var(--text-main); margin: 0 0 4px }
.ph-sub { font-size: 0.9rem; color: var(--text-muted); margin: 0 }
.ph-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap }
</style>
