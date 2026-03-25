<template>
  <svg
    v-if="width > 0 && height > 0"
    class="overlay"
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="none"
  >
    <defs>
      <marker
        id="arrowhead-red"
        markerWidth="10"
        markerHeight="7"
        refX="10"
        refY="3.5"
        orient="auto"
      >
        <polygon points="0 0, 10 3.5, 0 7" fill="#e53935" />
      </marker>
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

    <g v-if="Array.isArray(annotations?.arrows)">
      <line
        v-for="(a, idx) in annotations.arrows"
        :key="`arrow-${idx}`"
        :x1="a[0]"
        :y1="a[1]"
        :x2="a[2]"
        :y2="a[3]"
        stroke="#e53935"
        stroke-width="4"
        stroke-linecap="round"
        marker-end="url(#arrowhead-red)"
      />
    </g>

    <g v-if="Array.isArray(annotations?.sketch_rects)">
      <rect
        v-for="(r, idx) in annotations.sketch_rects"
        :key="`skrect-${idx}`"
        :x="r[0]"
        :y="r[1]"
        :width="r[2]"
        :height="r[3]"
        fill="none"
        stroke="#FF6B35"
        stroke-width="4"
        stroke-linecap="round"
        stroke-dasharray="10 8"
        opacity="0.9"
      />
    </g>

    <g v-if="Array.isArray(annotations?.sketch_lines)">
      <line
        v-for="(a, idx) in annotations.sketch_lines"
        :key="`skline-${idx}`"
        :x1="a[0]"
        :y1="a[1]"
        :x2="a[2]"
        :y2="a[3]"
        stroke="#FF6B35"
        stroke-width="4"
        stroke-linecap="round"
        opacity="0.9"
      />
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
defineProps({
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
