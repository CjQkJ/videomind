<template>
  <div 
    ref="cardRef" 
    class="card-3d-wrapper"
    :style="cardStyle"
    @mousemove="handleMouseMove"
    @mouseleave="handleMouseLeave"
  >
    <div v-if="!disabled" class="glare-effect" :style="glareStyle"></div>
    <slot></slot>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = withDefaults(defineProps<{
  maxTilt?: number
  disabled?: boolean
}>(), {
  maxTilt: 3,
  disabled: false
})

const cardRef = ref<HTMLElement | null>(null)
const rotateX = ref(0)
const rotateY = ref(0)
const glareX = ref(50)
const glareY = ref(50)
const glareOpacity = ref(0)

const cardStyle = computed(() => {
  if (props.disabled) return {}
  return {
    transform: `perspective(1200px) rotateX(${rotateX.value}deg) rotateY(${rotateY.value}deg)`,
    transition: rotateX.value === 0 
      ? 'transform 0.5s ease, box-shadow 0.5s ease' 
      : 'transform 0.15s cubic-bezier(0.25, 1, 0.5, 1)'
  }
})

const glareStyle = computed(() => {
  return {
    background: `radial-gradient(circle at ${glareX.value}% ${glareY.value}%, rgba(16, 185, 129, 0.16) 0%, rgba(245, 158, 11, 0.07) 40%, transparent 80%)`,
    opacity: glareOpacity.value
  }
})

function handleMouseMove(e: MouseEvent) {
  if (props.disabled) return
  const card = cardRef.value
  if (!card) return

  const rect = card.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  const centerX = rect.width / 2
  const centerY = rect.height / 2

  // Subtle rotation with configurable maxTilt
  rotateX.value = -((y - centerY) / centerY) * props.maxTilt
  rotateY.value = ((x - centerX) / centerX) * props.maxTilt

  glareX.value = (x / rect.width) * 100
  glareY.value = (y / rect.height) * 100
  glareOpacity.value = 1
}

function handleMouseLeave() {
  if (props.disabled) return
  rotateX.value = 0
  rotateY.value = 0
  glareOpacity.value = 0
}
</script>

<style scoped>
.card-3d-wrapper {
  position: relative;
  width: 100%;
  transform-style: preserve-3d;
  will-change: transform;
  border-radius: 20px;
}

.glare-effect {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  z-index: 10;
  transition: opacity 0.3s ease;
}
</style>
