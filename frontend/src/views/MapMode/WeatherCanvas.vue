<template>
  <canvas ref="canvasRef" class="weather-canvas" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

type EmotionState = 'sunny' | 'cloudy' | 'overcast' | 'storm' | 'snow'

const props = withDefaults(defineProps<{
  emotion?: EmotionState
  enabled?: boolean
}>(), {
  emotion: 'sunny',
  enabled: true,
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let particles: Particle[] = []
let animFrame: number | null = null
let resizeObserver: ResizeObserver | null = null
let flashTimer = 0

class Particle {
  type: string
  x = 0
  y = 0
  speed = 0
  wobble = 0
  opacity = 0
  size = 0

  constructor(type: string, w: number, h: number) {
    this.type = type
    this.reset(w, h, true)
  }

  reset(w: number, h: number, initial = false) {
    this.x = Math.random() * w
    this.y = this.type === 'snow' ? -10 : Math.random() * (initial ? h : -h)
    switch (this.type) {
      case 'rain':
        this.speed = 8 + Math.random() * 12
        this.size = 1 + Math.random() * 1.5
        this.opacity = 0.3 + Math.random() * 0.4
        if (initial) this.y = Math.random() * h
        break
      case 'snow':
        this.speed = 0.4 + Math.random() * 0.8
        this.size = 2 + Math.random() * 4
        this.opacity = 0.3 + Math.random() * 0.5
        this.wobble = Math.random() * Math.PI * 2
        break
      case 'sun':
        this.speed = 0.3 + Math.random() * 0.6
        this.size = 1 + Math.random() * 3
        this.opacity = 0.15 + Math.random() * 0.25
        this.y = h + 10
        if (initial) this.y = Math.random() * h
        this.wobble = Math.random() * Math.PI * 2
        break
      case 'storm':
        this.speed = 12 + Math.random() * 18
        this.size = 1.5 + Math.random() * 2.5
        this.opacity = 0.5 + Math.random() * 0.4
        if (initial) this.y = Math.random() * h
        break
    }
  }

  update(w: number, h: number) {
    switch (this.type) {
      case 'rain':
      case 'storm':
        this.y += this.speed
        this.x -= this.speed * 0.2
        if (this.y > h) this.reset(w, h)
        break
      case 'snow':
        this.y += this.speed
        this.wobble += 0.02
        this.x += Math.sin(this.wobble) * 0.5
        if (this.y > h + 10) this.reset(w, h)
        break
      case 'sun':
        this.y -= this.speed
        this.x += Math.sin(this.wobble) * 0.3
        this.wobble += 0.03
        if (this.y < -10) this.reset(w, h)
        break
    }
  }

  draw(c: CanvasRenderingContext2D) {
    c.save()
    switch (this.type) {
      case 'rain':
        c.strokeStyle = `rgba(120,150,180,${this.opacity})`
        c.lineWidth = this.size * 0.5
        c.beginPath()
        c.moveTo(this.x, this.y)
        c.lineTo(this.x + 2, this.y + this.size * 5)
        c.stroke()
        break
      case 'snow':
        c.fillStyle = `rgba(200,215,230,${this.opacity})`
        c.beginPath()
        c.arc(this.x, this.y, this.size, 0, Math.PI * 2)
        c.fill()
        break
      case 'sun':
        c.fillStyle = `rgba(240,200,80,${this.opacity})`
        c.beginPath()
        c.arc(this.x, this.y, this.size, 0, Math.PI * 2)
        c.fill()
        break
      case 'storm':
        c.strokeStyle = `rgba(180,190,200,${this.opacity})`
        c.lineWidth = this.size * 0.6
        c.beginPath()
        c.moveTo(this.x, this.y)
        c.lineTo(this.x + 6, this.y + this.size * 6)
        c.stroke()
        break
    }
    c.restore()
  }
}

function emotionToParticleType(e: EmotionState): string {
  switch (e) {
    case 'sunny': return 'sun'
    case 'cloudy': return 'rain'
    case 'overcast': return 'rain'
    case 'storm': return 'storm'
    case 'snow': return 'snow'
    default: return 'sun'
  }
}

function emotionToCount(e: EmotionState): number {
  return { sunny: 50, cloudy: 60, overcast: 70, storm: 120, snow: 55 }[e] || 50
}

function getSkyGradient(e: EmotionState) {
  switch (e) {
    case 'sunny': return { top: 'rgba(255,245,220,0.18)', bot: 'rgba(250,240,220,0.0)' }
    case 'cloudy': return { top: 'rgba(180,185,195,0.18)', bot: 'rgba(200,200,210,0.04)' }
    case 'overcast': return { top: 'rgba(140,145,155,0.22)', bot: 'rgba(160,165,175,0.06)' }
    case 'storm': return { top: 'rgba(60,65,75,0.32)', bot: 'rgba(80,85,95,0.12)' }
    case 'snow': return { top: 'rgba(200,210,225,0.18)', bot: 'rgba(220,225,235,0.04)' }
    default: return { top: 'transparent', bot: 'transparent' }
  }
}

function rebuildParticles() {
  if (!canvasRef.value) return
  const w = canvasRef.value.width
  const h = canvasRef.value.height
  const type = emotionToParticleType(props.emotion)
  const count = emotionToCount(props.emotion)
  particles = []
  for (let i = 0; i < count; i++) {
    particles.push(new Particle(type, w, h))
  }
}

function resizeCanvas() {
  if (!canvasRef.value) return
  const dpr = window.devicePixelRatio || 1
  const rect = canvasRef.value.getBoundingClientRect()
  canvasRef.value.width = rect.width * dpr
  canvasRef.value.height = rect.height * dpr
  if (ctx) ctx.scale(dpr, dpr)
  // Use logical px for animation; reset particles after resize
  rebuildParticles()
}

function animate() {
  if (!ctx || !canvasRef.value) return
  const w = canvasRef.value.width / (window.devicePixelRatio || 1)
  const h = canvasRef.value.height / (window.devicePixelRatio || 1)
  ctx.clearRect(0, 0, w, h)

  // 天空渐变（覆盖整个 canvas 的上半部分）
  const grad = getSkyGradient(props.emotion)
  if (grad.top !== 'transparent') {
    const linear = ctx.createLinearGradient(0, 0, 0, h * 0.6)
    linear.addColorStop(0, grad.top)
    linear.addColorStop(1, grad.bot)
    ctx.fillStyle = linear
    ctx.fillRect(0, 0, w, h)
  }

  // 粒子
  for (const p of particles) {
    p.update(w, h)
    p.draw(ctx)
  }

  // 闪电（仅 storm）
  if (props.emotion === 'storm') {
    flashTimer--
    if (flashTimer <= 0 && Math.random() < 0.02) flashTimer = 4
    if (flashTimer > 0) {
      ctx.fillStyle = `rgba(255,255,240,${flashTimer * 0.04})`
      ctx.fillRect(0, 0, w, h)
    }
  }

  animFrame = requestAnimationFrame(animate)
}

function start() {
  if (animFrame !== null) return
  animate()
}

function stop() {
  if (animFrame !== null) {
    cancelAnimationFrame(animFrame)
    animFrame = null
  }
}

onMounted(() => {
  if (!canvasRef.value) return
  ctx = canvasRef.value.getContext('2d')
  resizeCanvas()
  if (props.enabled) start()

  // ResizeObserver 保证 canvas 跟随容器尺寸
  resizeObserver = new ResizeObserver(() => resizeCanvas())
  resizeObserver.observe(canvasRef.value)
})

onBeforeUnmount(() => {
  stop()
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

watch(() => props.emotion, () => rebuildParticles())
watch(() => props.enabled, (val) => { val ? start() : stop() })
</script>

<style scoped>
.weather-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 2;
}
</style>
