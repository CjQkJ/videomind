<template>
  <div class="mode-cards-grid">
    <button
      v-for="m in options"
      :key="m.value"
      type="button"
      class="mode-card"
      :class="{ active: modelValue === m.value }"
      @click="$emit('update:modelValue', m.value)"
    >
      <span class="mode-icon">{{ m.icon }}</span>
      <span class="mode-info">
        <span class="mode-name">{{ m.label }}</span>
        <span class="mode-desc">{{ m.desc }}</span>
      </span>
      <span v-if="modelValue === m.value" class="check-badge">✓</span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface ModeOption {
  label: string
  value: string
  icon: string
  desc: string
}

defineProps<{ modelValue: string; options: ModeOption[] }>()
defineEmits<{ (e: 'update:modelValue', value: string): void }>()
</script>

<style scoped>
.mode-cards-grid { display:grid;grid-template-columns:repeat(2,1fr);gap:14px }
@media(max-width:640px){ .mode-cards-grid{grid-template-columns:1fr} }
.mode-card { position:relative;display:flex;align-items:flex-start;gap:14px;padding:20px 16px;background:var(--bg-card);border:1px solid var(--border-strong);border-radius:12px;cursor:pointer;text-align:left;font-family:inherit;transition:all 0.25s ease }
.mode-card:hover { border-color:rgba(217,119,6,0.5);transform:translateY(-2px);box-shadow:0 10px 26px -8px rgba(15,23,42,0.16) }
.mode-card.active { background:var(--emerald-soft);border-color:var(--emerald-primary);box-shadow:0 0 0 1px var(--emerald-primary),0 6px 20px -6px rgba(14,159,110,0.3) }
.mode-icon { font-size:1.7rem;line-height:1;filter:drop-shadow(0 1px 2px rgba(14,159,110,0.3)) }
.mode-info { display:flex;flex-direction:column;gap:5px;min-width:0 }
.mode-name { font-size:1.02rem;font-weight:800;color:var(--text-main) }
.mode-card.active .mode-name { color:var(--emerald-deep) }
.mode-desc { font-size:0.86rem;color:var(--text-muted);line-height:1.55 }
.check-badge { position:absolute;top:12px;right:12px;width:24px;height:24px;border-radius:50%;background:var(--emerald-primary);color:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 0 12px rgba(14,159,110,0.45);font-size:0.82rem;font-weight:800 }
</style>
