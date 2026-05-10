<template>
  <div class="panel-body">
    <div class="panel-periods">
      <el-tag
        v-for="pid in location.periods"
        :key="pid"
        size="small"
        :color="getPeriodColor(pid)"
        effect="dark"
        class="period-tag"
      >
        {{ getPeriodLabel(pid) }}
      </el-tag>
    </div>

    <p class="panel-description">{{ location.description }}</p>

    <div class="panel-count">
      <span class="count-num">{{ location.paintingCount }}</span>
      <span class="count-label">幅作品</span>
    </div>

    <div class="panel-paintings">
      <h3 class="paintings-title">画作列表</h3>
      <div class="paintings-list">
        <template v-for="phase in paintingPhases" :key="phase.label">
          <div class="phase-header">{{ phase.label }}</div>
          <div
            v-for="p in phase.paintings"
            :key="p.id"
            class="painting-item"
            @click="$emit('goToPainting', p)"
          >
            <img
              v-if="p.thumbnail_url"
              :src="p.thumbnail_url"
              class="painting-thumb"
              loading="lazy"
            />
            <div v-else class="painting-thumb-placeholder">
              <span>无图</span>
            </div>
            <span class="painting-title">{{ p.title }}</span>
            <span class="painting-year">{{ p.year || '年代不详' }}</span>
          </div>
        </template>
        <div v-if="location.paintingCount === 0" class="no-paintings">
          暂无该地点对应年份的存世作品记录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PERIOD_CONFIG } from './locations'
import type { LocationWithPaintings, Painting } from './useMapData'

const props = defineProps<{
  location: LocationWithPaintings
}>()

defineEmits<{
  goToPainting: [painting: Painting]
}>()

function getPeriodLabel(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.label || periodId
}

function getPeriodColor(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.color || '#8b7d6b'
}

const paintingPhases = computed(() => {
  const paintings = props.location.paintings
  const phaseMap: Record<string, Painting[]> = {}
  for (const p of paintings) {
    const phase = p.period_phase || p.period || '未分期'
    if (!phaseMap[phase]) phaseMap[phase] = []
    phaseMap[phase].push(p)
  }
  return Object.entries(phaseMap).map(([label, list]) => ({ label, paintings: list }))
})
</script>

<style scoped>
.panel-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow-y: auto;
}
.panel-periods {
  padding: 8px 24px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.period-tag { border: none !important; }

.panel-description {
  padding: 16px 24px 0;
  font-size: 0.88rem;
  line-height: 1.75;
  color: #5e5d59;
  margin: 0;
}

.panel-count {
  padding: 16px 24px;
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.count-num {
  font-family: 'Noto Serif SC', serif;
  font-size: 2rem;
  font-weight: 600;
  color: #c9a96e;
}
.count-label { font-size: 0.88rem; color: #8b7d6b; }

.panel-paintings {
  flex: 1;
  padding: 0 24px 24px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.paintings-title {
  font-size: 0.82rem;
  font-weight: 500;
  color: #8b7d6b;
  margin: 0 0 12px;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
.paintings-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.phase-header {
  font-size: 0.78rem;
  font-weight: 500;
  color: #c9a96e;
  padding: 10px 0 4px;
  border-bottom: 1px solid #e8e4d8;
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}
.painting-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 4px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
}
.painting-item:hover { background: rgba(201, 169, 110, 0.08); }
.painting-thumb {
  width: 44px;
  height: 44px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid #e8e4d8;
}
.painting-thumb-placeholder {
  width: 44px;
  height: 44px;
  border-radius: 4px;
  background: #f0ece4;
  border: 1px solid #e8e4d8;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.painting-thumb-placeholder span {
  font-size: 0.65rem;
  color: #c0b8a8;
}
.painting-title {
  font-size: 0.84rem;
  color: #2c2416;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.painting-year {
  font-size: 0.78rem;
  color: #8b7d6b;
  flex-shrink: 0;
}
.no-paintings {
  color: #8b7d6b;
  font-size: 0.84rem;
  text-align: center;
  padding: 24px 0;
}
</style>
