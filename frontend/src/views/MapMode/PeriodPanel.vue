<template>
  <div class="period-timeline">
    <div class="panel-description period-desc">
      {{ artistName }}{{ periodLabel }}期间，足迹涉及 {{ cities.length }} 座城市：
    </div>
    <div
      v-for="(city, idx) in cities"
      :key="city.locId"
      class="timeline-step"
      :class="{ last: idx === cities.length - 1 }"
      @click="$emit('selectCity', city.locId)"
    >
      <div class="timeline-dot" :style="{ background: city.color }"></div>
      <div v-if="idx < cities.length - 1" class="timeline-line"></div>
      <div class="timeline-card">
        <span class="timeline-year">{{ city.year }}年</span>
        <span class="timeline-name">{{ city.name }}</span>
        <span class="timeline-desc">{{ city.briefDesc }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  artistName: string
  periodLabel: string
  cities: {
    locId: string
    name: string
    year: number
    briefDesc: string
    color: string
  }[]
}>()

defineEmits<{
  selectCity: [locId: string]
}>()
</script>

<style scoped>
.period-timeline {
  padding: 16px 24px 24px;
  overflow-y: auto;
  flex: 1;
}
.period-desc {
  padding-bottom: 12px;
  font-size: 0.88rem;
  line-height: 1.75;
  color: #5e5d59;
}
.timeline-step {
  position: relative;
  display: flex;
  padding-left: 32px;
  padding-bottom: 4px;
  cursor: pointer;
}
.timeline-step:not(.last) { padding-bottom: 20px; }
.timeline-dot {
  position: absolute;
  left: 0;
  top: 6px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px currentColor;
  z-index: 1;
  flex-shrink: 0;
}
.timeline-line {
  position: absolute;
  left: 5px;
  top: 20px;
  bottom: 4px;
  width: 2px;
  background: #e8e4d8;
}
.timeline-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 14px;
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 8px;
  transition: all 0.2s;
  flex: 1;
}
.timeline-step:hover .timeline-card {
  border-color: #c9a96e;
  box-shadow: 0 2px 8px rgba(201, 169, 110, 0.12);
}
.timeline-year {
  font-size: 0.75rem;
  color: #c9a96e;
  font-weight: 500;
}
.timeline-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: #2c2416;
}
.timeline-desc {
  font-size: 0.76rem;
  color: #8b7d6b;
  line-height: 1.5;
  margin-top: 2px;
}
</style>
