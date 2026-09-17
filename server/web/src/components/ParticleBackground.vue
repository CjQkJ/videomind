<template>
  <div class="particles" ref="container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
const container = ref<HTMLElement | null>(null)

onMounted(() => {
  const el = container.value; if (!el) return
  const c = document.createElement('canvas')
  const ctx = c.getContext('2d'); if (!ctx) return
  el.appendChild(c)
  Object.assign(c.style, { position: 'fixed', inset: '0', zIndex: '0', pointerEvents: 'none' })

  let w = 0, h = 0
  const resize = () => { w = c.width = innerWidth; h = c.height = innerHeight }
  resize(); addEventListener('resize', resize)

  const particles = Array.from({ length: 40 }, () => ({
    x: Math.random() * w, y: Math.random() * h, r: Math.random() * 2 + 0.5,
    vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25,
    o: Math.random() * 0.6 + 0.1
  }))

  function animate() {
    ctx!.clearRect(0, 0, w, h)
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy
      if (p.x < 0) p.x = w; if (p.x > w) p.x = 0
      if (p.y < 0) p.y = h; if (p.y > h) p.y = 0
      ctx!.beginPath(); ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(5,150,105,${p.o * 0.5})`; ctx!.fill()
    }
    const conn = 140; ctx!.strokeStyle = 'rgba(5,150,105,0.12)'; ctx!.lineWidth = 0.5
    for (let i = 0; i < particles.length; i++)
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y
        if (dx * dx + dy * dy < conn * conn) { ctx!.beginPath(); ctx!.moveTo(particles[i].x, particles[i].y); ctx!.lineTo(particles[j].x, particles[j].y); ctx!.stroke() }
      }
    requestAnimationFrame(animate)
  }
  animate()
})
</script>
