<template>
  <svg
    v-if="width > 0 && height > 0"
    class="overlay"
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="none"
  >
    <defs>
      <!-- 箭头 marker — 更大更醒目 -->
      <marker
        v-for="(style, idx) in arrowStyles"
        :id="`arrowhead-${idx}`"
        :key="`marker-${idx}`"
        markerWidth="14"
        markerHeight="10"
        refX="13"
        refY="5"
        orient="auto"
      >
        <polygon :points="'0 0, 14 5, 0 10'" :fill="style.color" />
      </marker>
      <!-- 文字阴影滤镜 -->
      <filter id="text-shadow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity="0.5" />
      </filter>
    </defs>

    <image
      v-if="annotations?.heatmap"
      :href="annotations.heatmap"
      x="0"
      y="0"
      :width="width"
      :height="height"
      opacity="0.35"
      preserveAspectRatio="none"
    />

    <!-- 起承转合箭头 — 直线 + 发光效果，标签在线段起点 -->
    <g v-if="Array.isArray(annotations?.arrows) && annotations.arrows.length > 0">
      <!-- 发光底层（更宽更透明的同色线） -->
      <line
        v-for="(a, idx) in annotations.arrows"
        :key="`glow-${idx}`"
        :x1="a[0]"
        :y1="a[1]"
        :x2="a[2]"
        :y2="a[3]"
        fill="none"
        :stroke="getArrowColor(idx)"
        :stroke-width="12"
        stroke-linecap="round"
        opacity="0.25"
      />
      <!-- 主箭头线 -->
      <line
        v-for="(a, idx) in annotations.arrows"
        :key="`arrow-${idx}`"
        :x1="a[0]"
        :y1="a[1]"
        :x2="a[2]"
        :y2="a[3]"
        fill="none"
        :stroke="getArrowColor(idx)"
        :stroke-width="5"
        stroke-linecap="round"
        stroke-dasharray="none"
        :marker-end="`url(#arrowhead-${arrowColorIndex(idx)})`"
      />
      <!-- 箭头标签 — 放在线段起点 -->
      <g v-for="(a, idx) in annotations.arrows" :key="`label-${idx}`">
        <!-- 标签位置：线段起点偏移一点，避免和箭头重叠 -->
        <g :transform="`translate(${labelStartPos(a, idx).x}, ${labelStartPos(a, idx).y})`">
          <!-- 标签底板（圆角矩形 + 阴影） -->
          <rect
            x="-22"
            y="-18"
            width="44"
            height="32"
            rx="6"
            :fill="getArrowColor(idx)"
            opacity="0.92"
          />
          <!-- 高光条 -->
          <rect
            x="-20"
            y="-16"
            width="40"
            height="12"
            rx="4"
            fill="#fff"
            opacity="0.2"
          />
          <!-- 文字 -->
          <text
            x="0"
            y="6"
            text-anchor="middle"
            fill="#fff"
            font-size="18"
            font-weight="bold"
            font-family="Microsoft YaHei, PingFang SC, sans-serif"
            filter="url(#text-shadow)"
          >{{ arrowLabel(idx) }}</text>
        </g>
      </g>
    </g>

    <g v-if="Array.isArray(annotations?.good_crosses)">
      <circle
        v-for="(p, idx) in annotations.good_crosses"
        :key="`good-${idx}`"
        :cx="p[0]"
        :cy="p[1]"
        r="10"
        fill="#2e7d32"
        opacity="0.85"
      />
    </g>

    <g v-if="Array.isArray(annotations?.bad_crosses)">
      <g
        v-for="(p, idx) in annotations.bad_crosses"
        :key="`bad-${idx}`"
        :transform="`translate(${p[0]}, ${p[1]})`"
      >
        <line x1="-10" y1="-10" x2="10" y2="10" stroke="#d32f2f" stroke-width="4" />
        <line x1="-10" y1="10" x2="10" y2="-10" stroke="#d32f2f" stroke-width="4" />
      </g>
    </g>

    <rect
      v-if="Array.isArray(annotations?.inscription_suggestion_box) && annotations.inscription_suggestion_box.length === 4"
      :x="annotations.inscription_suggestion_box[0]"
      :y="annotations.inscription_suggestion_box[1]"
      :width="annotations.inscription_suggestion_box[2]"
      :height="annotations.inscription_suggestion_box[3]"
      fill="#000"
      opacity="0.15"
      stroke="#111"
      stroke-width="2"
      stroke-dasharray="8 8"
    />

    <g v-if="Array.isArray(annotations?.warnings) && annotations.warnings.includes('line_parallel')">
      <rect x="20" y="20" width="320" height="56" rx="10" fill="#f9a825" opacity="0.9" />
      <text x="36" y="56" fill="#111" font-size="22">注意避免平行线</text>
    </g>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  annotations: {
    type: Object,
    default: () => ({})
  },
  width: {
    type: Number,
    default: 0
  },
  height: {
    type: Number,
    default: 0
  }
})

const arrowStyles = [
  { color: '#e53935', label: '起' },   // 红 — 起：布局之始
  { color: '#ff9800', label: '承' },   // 橙 — 承：自然紧凑
  { color: '#1976d2', label: '转' },   // 蓝 — 转：情节高潮
  { color: '#2e7d32', label: '合' },   // 绿 — 合：气聚合一
]

const arrowColors = computed(() => {
  const count = props.annotations?.arrows?.length || 0
  return arrowStyles.slice(0, count).map(s => s.color)
})

function getArrowColor(idx) {
  return arrowStyles[idx % arrowStyles.length].color
}

function arrowColorIndex(idx) {
  return idx % arrowStyles.length
}

function arrowLabel(idx) {
  // Prefer backend-provided labels, fall back to default
  const labels = props.annotations?.arrow_labels
  if (Array.isArray(labels) && labels[idx]) {
    return labels[idx]
  }
  return arrowStyles[idx % arrowStyles.length].label
}

/**
 * Calculate label position at the START of the arrow line,
 * offset slightly away from the line direction to avoid overlap.
 */
function labelStartPos(a, idx) {
  const sx = a[0]
  const sy = a[1]
  const ex = a[2]
  const ey = a[3]

  // Calculate direction vector
  const dx = ex - sx
  const dy = ey - sy
  const len = Math.sqrt(dx * dx + dy * dy) || 1

  // Perpendicular unit vector (offset labels to the left of arrow direction)
  const perpX = -dy / len
  const perpY = dx / len

  // Offset from start point: slightly along the line + perpendicular
  const offsetAlong = 30 // pixels along arrow
  const offsetPerp = 25  // pixels perpendicular to arrow

  // Alternate perpendicular direction for each arrow to avoid overlap
  const perpSign = idx % 2 === 0 ? 1 : -1

  const x = sx + (dx / len) * offsetAlong + perpX * offsetPerp * perpSign
  const y = sy + (dy / len) * offsetAlong + perpY * offsetPerp * perpSign

  return { x: Math.round(x), y: Math.round(y) }
}
</script>

<style scoped>
.overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
