<template>
  <div class="map-mode-page">
    <!-- Loading -->
    <div v-if="loading" class="map-loading">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="map-error">
      <el-result icon="error" title="数据加载失败" :sub-title="error">
        <template #extra>
          <el-button type="primary" @click="retry">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- Main Content -->
    <template v-else>
      <div class="map-main" :class="{ 'panel-open': activePanel }">
        <!-- ECharts Map -->
        <div class="map-wrapper">
          <div ref="chartContainer" class="chart-container"></div>

          <!-- Hint -->
          <div v-if="!activePanel" class="map-hint">
            点击城市标记查看李鱓在该地的经历与画作
          </div>

          <!-- Legend -->
          <div class="map-legend">
            <div
              v-for="p in PERIOD_CONFIG"
              :key="p.id"
              class="legend-item"
              :class="{ dimmed: selectedPeriod && selectedPeriod !== p.id }"
              @click="selectPeriod(p.id)"
            >
              <span class="legend-line" :style="{ background: p.color }"></span>
              <span class="legend-label">{{ p.yearRange[0] === p.yearRange[1] ? p.yearRange[0] : `${p.yearRange[0]}-${p.yearRange[1]}` }}</span>
            </div>
          </div>
        </div>

        <!-- Info Panel -->
        <transition name="panel-slide">
          <div v-if="activePanel" class="info-panel">
            <!-- Period Overview Header -->
            <div v-if="activePanel === 'period'" class="panel-header">
              <h2 class="panel-location">{{ currentPeriodLabel }}</h2>
              <span class="panel-year-range">{{ currentPeriodYearRange }}</span>
              <button class="panel-close" @click="closePeriodPanel">&times;</button>
            </div>

            <!-- City Detail Header -->
            <div v-else class="panel-header">
              <button v-if="selectedPeriod" class="panel-back" @click="backToPeriod">&larr; 返回</button>
              <h2 class="panel-location">{{ selectedLocation?.name }}</h2>
              <button class="panel-close" @click="closePanel">&times;</button>
            </div>

            <!-- Panel Body -->
            <div v-if="activePanel === 'period'" key="period" class="panel-body">
              <div class="panel-description period-desc">
                李鱓{{ currentPeriodLabel }}期间，足迹涉及 {{ periodCities.length }} 座城市：
              </div>

              <div class="period-timeline">
                <div
                  v-for="(city, idx) in periodCities"
                  :key="city.locId"
                  class="timeline-step"
                  :class="{ last: idx === periodCities.length - 1 }"
                  @click="selectCityFromPeriod(city.locId)"
                >
                  <div class="timeline-dot" :style="{ background: city.color }"></div>
                  <div v-if="idx < periodCities.length - 1" class="timeline-line"></div>
                  <div class="timeline-card">
                    <span class="timeline-year">{{ city.year }}年</span>
                    <span class="timeline-name">{{ city.name }}</span>
                    <span class="timeline-desc">{{ city.briefDesc }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- City Detail Body -->
            <div v-else key="city" class="panel-body">
              <div class="panel-periods">
                <el-tag
                  v-for="pid in selectedLocation!.periods"
                  :key="pid"
                  size="small"
                  :color="getPeriodColor(pid)"
                  effect="dark"
                  class="period-tag"
                >
                  {{ getPeriodLabel(pid) }}
                </el-tag>
              </div>

              <p class="panel-description">{{ selectedLocation!.description }}</p>

              <div class="panel-count">
                <span class="count-num">{{ selectedLocation!.paintingCount }}</span>
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
                      @click="goToPainting(p)"
                    >
                      <span class="painting-title">{{ p.title }}</span>
                      <span class="painting-year">{{ p.year || '年代不详' }}</span>
                    </div>
                  </template>
                  <div v-if="selectedLocation!.paintingCount === 0" class="no-paintings">
                    暂无该地点对应年份的存世作品记录
                  </div>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- Period Selector -->
      <div class="period-bar">
        <button
          class="period-btn reset-btn"
          :class="{ active: selectedPeriod === null }"
          @click="selectPeriod(null)"
        >
          全 程
        </button>
        <button
          v-for="period in PERIOD_CONFIG"
          :key="period.id"
          class="period-btn"
          :class="{ active: selectedPeriod === period.id }"
          @click="selectPeriod(period.id)"
        >
          {{ period.label }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useMapData } from './MapMode/useMapData'
import { PERIOD_CONFIG, LI_SHAN_LOCATIONS } from './MapMode/locations'
import type { LocationWithPaintings, Painting } from './MapMode/useMapData'
import chinaGeoJSON from '@/assets/china-geojson.json'

const router = useRouter()
const chartContainer = ref<HTMLElement | null>(null)
const selectedLocation = ref<LocationWithPaintings | null>(null)
const activePanel = ref<'period' | 'city' | null>(null)

const {
  loading,
  error,
  locationsWithPaintings,
  filteredLocations,
  fetchData,
  selectedPeriod,
  selectPeriod: _selectPeriod,
} = useMapData()

let chart: echarts.ECharts | null = null

// ── Period overview data ──

interface PeriodCityEntry {
  locId: string
  name: string
  year: number
  briefDesc: string
  color: string
}

const periodCities = computed<PeriodCityEntry[]>(() => {
  if (!selectedPeriod.value) return []
  const timeline = buildTimeline()
  return timeline
    .filter((e) => e.periodId === selectedPeriod.value)
    .map((e) => {
      const loc = LI_SHAN_LOCATIONS.find((l) => l.id === e.locId)
      const brief = loc?.description?.split('\n')[0]?.replace(/^[^。]+。/, '').slice(0, 40) || ''
      return {
        locId: e.locId,
        name: e.name,
        year: e.startYear,
        briefDesc: brief || loc?.description?.slice(0, 50) || '',
        color: e.periodColor,
      }
    })
})

const currentPeriodLabel = computed(() => {
  if (!selectedPeriod.value) return ''
  return PERIOD_CONFIG.find((p) => p.id === selectedPeriod.value)?.label || ''
})

const currentPeriodYearRange = computed(() => {
  if (!selectedPeriod.value) return ''
  const cfg = PERIOD_CONFIG.find((p) => p.id === selectedPeriod.value)
  if (!cfg) return ''
  const [s, e] = cfg.yearRange
  return s === e ? `${s}年` : `${s} — ${e}年`
})

const paintingPhases = computed(() => {
  if (!selectedLocation.value) return []
  const paintings = selectedLocation.value.paintings
  const phaseMap: Record<string, Painting[]> = {}
  for (const p of paintings) {
    const phase = p.period_phase || p.period || '未分期'
    if (!phaseMap[phase]) phaseMap[phase] = []
    phaseMap[phase].push(p)
  }
  return Object.entries(phaseMap).map(([label, list]) => ({ label, paintings: list }))
})

function getPeriodLabel(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.label || periodId
}

function getPeriodColor(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.color || '#8b7d6b'
}

function selectPeriod(periodId: string | null) {
  _selectPeriod(periodId)
  if (periodId) {
    activePanel.value = 'period'
    selectedLocation.value = null
    updateChartEffectScatter(null)
  } else {
    activePanel.value = null
    selectedLocation.value = null
    updateChartEffectScatter(null)
  }
}

function selectCityFromPeriod(locId: string) {
  const loc = locationsWithPaintings.value.find((l) => l.id === locId)
  if (!loc) return
  selectedLocation.value = loc
  activePanel.value = 'city'
  updateChartEffectScatter([loc.lng, loc.lat])
}

function closePeriodPanel() {
  _selectPeriod(null)
  activePanel.value = null
  selectedLocation.value = null
  updateChartEffectScatter(null)
}

function backToPeriod() {
  selectedLocation.value = null
  activePanel.value = 'period'
  updateChartEffectScatter(null)
}

function closePanel() {
  if (selectedPeriod.value) {
    // Coming from period overview → go back to it
    backToPeriod()
  } else {
    // Coming from map marker → close everything
    activePanel.value = null
    selectedLocation.value = null
    updateChartEffectScatter(null)
  }
}

function goToPainting(painting: Painting) {
  const imageId = painting.image_id || painting.id
  router.push(`/tubi/${imageId}`)
}

async function retry() {
  await fetchData()
  updateChartData()
}

// ── Timeline & trajectory ──

interface TimelineEntry {
  locId: string
  name: string
  lat: number
  lng: number
  startYear: number
  endYear: number
  periodId: string
  periodLabel: string
  periodColor: string
}

function buildTimeline(): TimelineEntry[] {
  const entries: TimelineEntry[] = []
  for (const loc of LI_SHAN_LOCATIONS) {
    for (let i = 0; i < loc.yearRanges.length; i++) {
      const pid = loc.periods[i]
      const cfg = PERIOD_CONFIG.find((p) => p.id === pid)
      entries.push({
        locId: loc.id,
        name: loc.name,
        lat: loc.lat,
        lng: loc.lng,
        startYear: loc.yearRanges[i][0],
        endYear: loc.yearRanges[i][1],
        periodId: pid,
        periodLabel: cfg?.label || pid,
        periodColor: cfg?.color || '#8b7d6b',
      })
    }
  }
  entries.sort((a, b) => a.startYear - b.startYear)
  return entries
}

// Build marker map: merged-location-id → { order, primaryColor }
function buildMarkerMeta() {
  const timeline = buildTimeline()
  const seen = new Map<string, { order: number; color: string; name: string }>()
  let order = 0
  for (const entry of timeline) {
    if (!seen.has(entry.locId)) {
      order++
      seen.set(entry.locId, { order, color: entry.periodColor, name: entry.name })
    }
  }
  return seen
}

const CHINESE_NUMS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩']

const VISITED_PROVINCES = ['北京市', '河北省', '江苏省', '浙江省', '山东省']

function makeScatterData(locations: LocationWithPaintings[], markerMeta: Map<string, any>) {
  return locations.map((loc) => {
    const meta = markerMeta.get(loc.id)
    const order = meta?.order || 0
    const color = meta?.color || '#c9a96e'
    const num = CHINESE_NUMS[order - 1] || `${order}`
    return {
      name: `${num} ${loc.name}`,
      value: [loc.lng, loc.lat, loc.paintingCount],
      locId: loc.id,
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      label: { color },
    }
  })
}

interface SegmentData {
  coords: [number, number][]
  lineStyle: { color: string; width: number; opacity: number }
  periodId: string
  fromName: string
  toName: string
  fromYear: number
  toYear: number
}

/** Quadratic bezier arc — bulges east when going north, west when going south, avoiding crossing */
function computeArc(
  lng1: number, lat1: number,
  lng2: number, lat2: number,
  numPoints: number,
): [number, number][] {
  const mx = (lng1 + lng2) / 2
  const my = (lat1 + lat2) / 2
  const dx = lng2 - lng1
  const dy = lat2 - lat1
  const dist = Math.sqrt(dx * dx + dy * dy)
  // Bulge proportional to east-west span (great-circle style) + base
  const bulge = Math.max(Math.abs(dx) * 0.5 + 0.3, 0.4)
  // North-going routes bulge east, south-going bulge west
  const dir = dy >= 0 ? 1 : -1
  const cx = mx + dir * bulge
  const cy = my + bulge * 0.6

  const pts: [number, number][] = []
  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints
    const x = (1 - t) ** 2 * lng1 + 2 * (1 - t) * t * cx + t * t * lng2
    const y = (1 - t) ** 2 * lat1 + 2 * (1 - t) * t * cy + t * t * lat2
    pts.push([x, y])
  }
  return pts
}

function buildSegments(visibleLocIds: Set<string> | null): SegmentData[] {
  const timeline = buildTimeline()
  const segments: SegmentData[] = []

  for (let i = 0; i < timeline.length - 1; i++) {
    const a = timeline[i]
    const b = timeline[i + 1]
    if (a.lat === b.lat && a.lng === b.lng) continue
    if (visibleLocIds && (!visibleLocIds.has(a.locId) || !visibleLocIds.has(b.locId))) continue

    const arc = computeArc(a.lng, a.lat, b.lng, b.lat, 48)

    segments.push({
      coords: arc,
      lineStyle: {
        color: a.periodColor,
        width: 3,
        opacity: 0.7,
      },
      periodId: a.periodId,
      fromName: a.name,
      toName: b.name,
      fromYear: a.startYear,
      toYear: b.startYear,
    })
  }

  return segments
}

function buildOption(locations: LocationWithPaintings[], allLocations: LocationWithPaintings[], periodFilter: string | null) {
  const markerMeta = buildMarkerMeta()

  // Always show all markers, but dim non-matching ones when a period is selected
  const visibleLocIds = periodFilter
    ? new Set(locations.flatMap((l) => [l.id, ...l.sourceIds]))
    : null
  const scatterData = makeScatterData(
    periodFilter ? allLocations : locations,
    markerMeta,
  )
  // Apply per-marker dimming when a period is filtered
  if (periodFilter) {
    for (const d of scatterData) {
      if (!visibleLocIds!.has(d.locId)) {
        d.itemStyle.opacity = 0.22
        d.label.opacity = 0.22
      }
    }
  }

  const segments = buildSegments(visibleLocIds)

  const option: any = {
    backgroundColor: '#f8f5f0',
    animation: true,
    animationDuration: 800,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
          const count = params.value?.[2] ?? 0
          const locId = params.data?.locId
          if (locId) {
            const meta = markerMeta.get(locId)
            const loc = allLocations.find((l) => l.sourceIds?.includes(locId) || l.id === locId)
            const periods = loc?.periods || []
            const labels = periods.map((p: string) => getPeriodLabel(p)).join('、')
            const yrs = loc?.yearRanges
              .map((r: [number, number]) => `${r[0]}-${r[1]}`).join('、') || ''
            return `<strong>${meta?.name || params.name}</strong><br/>时期：${labels}<br/>年份：${yrs}<br/>画作：${count} 幅`
          }
          return `<strong>${params.name}</strong><br/>画作数量：${count} 幅`
        }
        if (params.seriesType === 'lines') {
          const from = params.data?.fromName || ''
          const to = params.data?.toName || ''
          const fy = params.data?.fromYear || ''
          const ty = params.data?.toYear || ''
          return `${fy}年 ${from} → ${ty}年 ${to}`
        }
        return ''
      },
    },
    geo: {
      map: 'china',
      roam: true,
      zoom: 5,
      center: [118, 35],
      scaleLimit: { min: 1.5, max: 8 },
      itemStyle: {
        areaColor: '#f6f3ed',
        borderColor: '#d8d1c4',
        borderWidth: 0.8,
      },
      emphasis: { disabled: true },
      label: { show: false },
      regions: VISITED_PROVINCES.map((name) => ({
        name,
        itemStyle: { areaColor: '#f0ead8' },
      })),
    },
    series: [] as any[],
  }

  // One lines series with per-segment arc paths
  option.series.push({
    type: 'lines',
    coordinateSystem: 'geo',
    polyline: true,
    data: segments.map((seg) => ({
      coords: seg.coords,
      lineStyle: seg.lineStyle,
      fromName: seg.fromName,
      toName: seg.toName,
    })),
    lineStyle: { width: 3, opacity: 0.55 },
    effect: {
      show: true,
      period: 6,
      trailLength: 0.25,
      symbol: 'triangle',
      symbolSize: 6,
      color: '#c96442',
    },
    zlevel: 1,
  })

  // Scatter markers
  option.series.push({
    type: 'scatter',
    coordinateSystem: 'geo',
    data: scatterData,
    encode: { tooltip: [2] },
    symbolSize: (val: number[]) => Math.max(7, Math.min(22, Math.sqrt(val[2]) * 2.2)),
    label: {
      show: true,
      formatter: '{b}',
      position: 'right' as const,
      fontSize: 13,
      fontFamily: "'Noto Serif SC', serif",
      fontWeight: 600,
      textShadowColor: 'rgba(248, 245, 240, 0.9)',
      textShadowBlur: 4,
    },
    emphasis: {
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 3,
        shadowBlur: 16,
      },
      scale: 1.4,
    },
    zlevel: 2,
    animationDelay: (_idx: number) => 200,
  })

  // Effect scatter (selected point ripple)
  option.series.push({
    type: 'effectScatter',
    coordinateSystem: 'geo',
    data: [],
    symbolSize: 20,
    showEffectOn: 'render' as const,
    rippleEffect: {
      brushType: 'stroke' as const,
      scale: 4,
      period: 3,
      color: '#c96442',
    },
    itemStyle: { color: '#c96442' },
    zlevel: 3,
  })

  return option
}

function updateChartEffectScatter(lngLat: [number, number] | null) {
  if (!chart) return
  const effectData = lngLat ? [{ value: lngLat }] : []
  chart.setOption({ series: [{}, {}, { data: effectData }] } as any)
}

function updateChartData(locations?: LocationWithPaintings[]) {
  if (!chart) return
  const locs = locations || filteredLocations.value
  const option = buildOption(locs, locationsWithPaintings.value, selectedPeriod.value)
  chart.setOption(option, true)
}

function initChart() {
  if (!chartContainer.value) return

  echarts.registerMap('china', chinaGeoJSON as any)
  chart = echarts.init(chartContainer.value)

  chart.on('click', 'series', (params: any) => {
    if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
      const locId = params.data?.locId
      if (!locId) return
      const loc = locationsWithPaintings.value.find((l) => l.id === locId)
      if (!loc) return
      selectedLocation.value = loc
      activePanel.value = 'city'
      updateChartEffectScatter([loc.lng, loc.lat])
    }
  })

  updateChartData()
}

// ── Lifecycle ──

watch(selectedPeriod, () => {
  updateChartData(filteredLocations.value)
})

onMounted(async () => {
  await fetchData()
  await nextTick()
  initChart()
  window.addEventListener('resize', handleResize)
})

function handleResize() {
  chart?.resize()
}

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.map-mode-page {
  min-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: #f8f5f0;
  position: relative;
}

.map-loading,
.map-error {
  padding: 48px 24px;
  max-width: 640px;
  margin: 0 auto;
}

.map-main {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.map-wrapper {
  flex: 1;
  position: relative;
  min-height: 500px;
}

.chart-container {
  position: absolute;
  inset: 0;
}

/* ── Hint ── */
.map-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-family: 'Noto Serif SC', serif;
  font-size: 0.92rem;
  color: #b8a990;
  pointer-events: none;
  z-index: 3;
  text-align: center;
  letter-spacing: 0.04em;
  transition: opacity 0.4s;
}

/* ── Legend ── */
.map-legend {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(250, 249, 245, 0.85);
  border: 1px solid #e8e4d8;
  border-radius: 8px;
  padding: 10px 14px;
  z-index: 5;
  backdrop-filter: blur(4px);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
  user-select: none;
}
.legend-item.dimmed {
  opacity: 0.3;
}
.legend-line {
  width: 18px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}
.legend-label {
  font-size: 0.78rem;
  color: #5e5d59;
  white-space: nowrap;
}

/* ── Info Panel ── */
.info-panel {
  width: 400px;
  min-width: 400px;
  background: #faf9f5;
  border-left: 1px solid #e8e4d8;
  box-shadow: -2px 0 16px rgba(44, 36, 22, 0.06);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  z-index: 10;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 24px 0;
}

.panel-location {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.5rem;
  font-weight: 500;
  color: #2c2416;
  margin: 0;
  letter-spacing: 0.06em;
}

.panel-close {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  font-size: 1.4rem;
  color: #8b7d6b;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}
.panel-close:hover { color: #c96442; }

.panel-year-range {
  font-size: 0.78rem;
  color: #8b7d6b;
  margin-left: 8px;
  flex: 1;
}

.panel-back {
  border: 1px solid #d8d0c0;
  background: #fff;
  color: #5e5d59;
  font-size: 0.78rem;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 14px;
  transition: all 0.2s;
  font-family: inherit;
  margin-right: 8px;
  white-space: nowrap;
}
.panel-back:hover { border-color: #c9a96e; color: #c9a96e; }

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
.period-desc {
  padding-bottom: 12px;
  border-bottom: 1px solid #e8e4d8;
}

/* ── Period Timeline ── */
.period-timeline {
  padding: 16px 24px 24px;
  overflow-y: auto;
  flex: 1;
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
  overflow-y: auto;
}
.paintings-title {
  font-size: 0.82rem;
  font-weight: 500;
  color: #8b7d6b;
  margin: 0 0 12px;
  letter-spacing: 0.04em;
}
.paintings-list {
  max-height: 360px;
  overflow-y: auto;
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
  justify-content: space-between;
  align-items: center;
  padding: 6px 4px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}
.painting-item:hover { background: rgba(201, 169, 110, 0.08); }
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
  margin-left: 12px;
  flex-shrink: 0;
}
.no-paintings {
  color: #8b7d6b;
  font-size: 0.84rem;
  text-align: center;
  padding: 24px 0;
}

/* Slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-slide-enter-from { transform: translateX(100%); opacity: 0; }
.panel-slide-leave-to { transform: translateX(100%); opacity: 0; }

/* Panel content crossfade */
.panel-fade-enter-active,
.panel-fade-leave-active {
  transition: opacity 0.2s ease;
}
.panel-fade-enter-from,
.panel-fade-leave-to { opacity: 0; }

/* Period Bar */
.period-bar {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 16px 24px;
  background: #f8f5f0;
  border-top: 1px solid #e8e4d8;
  flex-wrap: wrap;
}
.period-btn {
  padding: 6px 16px;
  border: 1px solid #d8d0c0;
  border-radius: 20px;
  background: #fff;
  color: #5e5d59;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.period-btn:hover { border-color: #c9a96e; color: #c9a96e; }
.period-btn.active {
  background: #c9a96e;
  border-color: #c9a96e;
  color: #fff;
}
.reset-btn { font-weight: 500; }

/* Responsive */
@media (max-width: 1024px) {
  .info-panel { width: 340px; min-width: 340px; }
}
@media (max-width: 768px) {
  .map-main { flex-direction: column; }
  .map-wrapper { min-height: 340px; }
  .info-panel {
    width: 100%;
    min-width: 0;
    max-height: 50vh;
    border-left: none;
    border-top: 1px solid #e8e4d8;
    box-shadow: 0 -2px 16px rgba(44, 36, 22, 0.06);
  }
  .map-legend {
    top: 8px;
    left: 8px;
    padding: 6px 10px;
    gap: 3px;
  }
  .legend-label { font-size: 0.7rem; }
}
</style>
