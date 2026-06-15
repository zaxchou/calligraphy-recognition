<template>
  <canvas ref="canvasRef" class="weather-canvas" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

type EmotionState = 'sunny' | 'clear' | 'cloudy' | 'overcast' | 'rain' | 'storm' | 'snow'

const props = withDefaults(defineProps<{
  emotion?: EmotionState
  enabled?: boolean
}>(), {
  emotion: 'clear',
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
        this.speed = 10 + Math.random() * 16
        this.size = 1.5 + Math.random() * 2.5
        this.opacity = 0.35 + Math.random() * 0.45
        if (initial) this.y = Math.random() * h
        break
      case 'snow':
        this.speed = 0.4 + Math.random() * 0.8
        this.size = 2 + Math.random() * 4
        this.opacity = 0.35 + Math.random() * 0.5
        this.wobble = Math.random() * Math.PI * 2
        break
      case 'sun':
        this.speed = 0.3 + Math.random() * 0.6
        this.size = 1.5 + Math.random() * 4
        this.opacity = 0.2 + Math.random() * 0.3
        this.y = h + 10
        if (initial) this.y = Math.random() * h
        this.wobble = Math.random() * Math.PI * 2
        break
      case 'storm':
        this.speed = 16 + Math.random() * 24
        this.size = 2 + Math.random() * 3.5
        this.opacity = 0.55 + Math.random() * 0.4
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
    case 'clear': return 'sun'              // 晴间多云也用光点（少一点）
    case 'cloudy': return 'rain'
    case 'overcast': return 'rain'
    case 'rain': return 'storm'             // 复用 storm 粒子（暴烈程度低一些）
    case 'storm': return 'storm'
    case 'snow': return 'snow'
    default: return 'sun'
  }
}

function emotionToCount(e: EmotionState): number {
  return { sunny: 80, clear: 50, cloudy: 100, overcast: 130, rain: 180, storm: 240, snow: 80 }[e] || 60
}

function getSkyGradient(e: EmotionState) {
  switch (e) {
    case 'sunny': return { top: 'rgba(255,240,200,0.25)', bot: 'rgba(250,240,210,0.0)' }
    case 'clear': return { top: 'transparent', bot: 'transparent' }  // 平和不叠加颜色
    case 'cloudy': return { top: 'rgba(170,175,185,0.22)', bot: 'rgba(190,195,205,0.06)' }
    case 'overcast': return { top: 'rgba(130,135,148,0.32)', bot: 'rgba(150,155,168,0.10)' }
    case 'rain': return { top: 'rgba(90,95,110,0.40)', bot: 'rgba(110,115,128,0.18)' }
    case 'storm': return { top: 'rgba(50,55,68,0.55)', bot: 'rgba(70,78,90,0.25)' }
    case 'snow': return { top: 'rgba(180,195,215,0.32)', bot: 'rgba(200,210,225,0.08)' }
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
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
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

  // 闪电（仅 storm，频率提高 + 两次闪光）
  if (props.emotion === 'storm') {
    flashTimer--
    if (flashTimer <= 0 && Math.random() < 0.04) flashTimer = 6
    if (flashTimer > 0) {
      const alpha = flashTimer === 5 ? 0.12 : flashTimer === 4 ? 0.06 : flashTimer === 2 ? 0.04 : 0.02
      ctx.fillStyle = `rgba(255,255,245,${alpha})`
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
  // 移动端跳过粒子系统（性能考虑）
  if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) {
    return
  }
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
  z-index: 4;
}
@media (max-width: 768px) {
  .weather-canvas { display: none; }
}
</style>
