<template>
  <div class="weather-card" :class="`wc-${emotion}`">
    <div class="wc-icon">{{ icon }}</div>
    <div class="wc-state">{{ stateName }}</div>
    <div class="wc-meta">
      <span class="wc-label">{{ contextLabel }}</span>
      <span v-if="paintingCount > 0" class="wc-count">{{ paintingCount }} 幅</span>
    </div>
    <div v-if="paintingCount > 0" class="wc-temp" :class="tempClass">
      {{ tempStr }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type EmotionState = 'sunny' | 'cloudy' | 'overcast' | 'storm' | 'snow'

const props = defineProps<{
  emotion: EmotionState
  /** 上下文标签：如时期名、城市名、"全程" */
  contextLabel: string
  /** 该上下文下的画作数（0 = 无情绪数据） */
  paintingCount: number
  /** 情绪温度 -5..+5 */
  temp: number
}>()

const ICONS: Record<EmotionState, string> = {
  sunny: '☀️',
  cloudy: '⛅',
  overcast: '☁️',
  storm: '⛈️',
  snow: '❄️',
}

const STATE_NAMES: Record<EmotionState, string> = {
  sunny: '晴 · 愉悦',
  cloudy: '多云 · 平和',
  overcast: '阴 · 失落',
  storm: '暴雨 · 悲愤',
  snow: '雪 · 宁静',
}

const icon = computed(() => ICONS[props.emotion])
const stateName = computed(() => STATE_NAMES[props.emotion])

const tempStr = computed(() => {
  const t = Math.round(props.temp * 10) / 10
  return (t >= 0 ? '+' : '') + t + '°'
})

const tempClass = computed(() => {
  if (props.temp >= 2) return 'hot'
  if (props.temp >= 0) return 'warm'
  if (props.temp >= -2) return 'cool'
  return 'cold'
})
</script>

<style scoped>
.weather-card {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 6;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid #e0dad0;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 14px rgba(44, 36, 22, 0.08);
  min-width: 140px;
  font-family: 'Noto Serif SC', serif;
  user-select: none;
  transition: border-color 0.4s, box-shadow 0.4s;
}
.wc-storm { border-color: #6a6080; box-shadow: 0 2px 18px rgba(74, 48, 64, 0.18); }
.wc-snow { border-color: #b8c4d4; }
.wc-sunny { border-color: #d4b878; }

.wc-icon {
  font-size: 28px;
  line-height: 1;
}
.wc-state {
  font-size: 14px;
  font-weight: 600;
  color: #2c2416;
  margin-top: 6px;
  letter-spacing: 0.04em;
}
.wc-meta {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 2px;
}
.wc-label {
  font-size: 12px;
  color: #8a7a5e;
  letter-spacing: 0.05em;
}
.wc-count {
  font-size: 11px;
  color: #b8a990;
}
.wc-temp {
  font-size: 22px;
  font-weight: 700;
  margin-top: 4px;
  font-family: 'Inter', system-ui, sans-serif;
}
.wc-temp.hot { color: #c45a3c; }
.wc-temp.warm { color: #c48a3c; }
.wc-temp.cool { color: #5a7a8a; }
.wc-temp.cold { color: #6a7a8a; }

@media (max-width: 768px) {
  .weather-card { top: 8px; right: 8px; padding: 8px 12px; min-width: 110px; }
  .wc-icon { font-size: 22px; }
  .wc-state { font-size: 12px; }
  .wc-temp { font-size: 18px; }
}
</style>
