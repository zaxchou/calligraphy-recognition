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

          <!-- Smart Hint: hides after first interaction -->
          <div v-if="!activePanel && !hasInteracted" class="map-hint">
            点击城市标记查看李鱓在该地的经历与画作
          </div>

          <!-- City Quick List (top-left overlay) -->
          <div class="city-quick-list">
            <div class="city-quick-title">行 旅</div>
            <div
              v-for="city in cityQuickList"
              :key="city.locId"
              class="city-quick-item"
              :class="{ active: selectedLocation?.id === city.locId }"
              @click="selectCityFromList(city.locId)"
            >
              <span class="city-quick-num" :style="{ color: city.color }">
                {{ CHINESE_NUMS[city.order - 1] }}
              </span>
              <span class="city-quick-name">{{ city.name }}</span>
              <span class="city-quick-province">{{ city.province }}</span>
              <span class="city-quick-count">{{ city.paintingCount }}幅</span>
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
              <div class="panel-header-actions">
                <button
                  v-if="isTourActive"
                  class="panel-close tour-stop-btn"
                  title="停止播放"
                  @click="stopTour"
                >&#9632;</button>
                <button class="panel-close" @click="closePeriodPanel">&times;</button>
              </div>
            </div>

            <!-- City Detail Header -->
            <div v-else class="panel-header">
              <button v-if="selectedPeriod" class="panel-back" @click="backToPeriod">&larr; 返回</button>
              <h2 class="panel-location">{{ selectedLocation?.name }}</h2>
              <div class="panel-header-actions">
                <button
                  v-if="isTourActive"
                  class="panel-close tour-stop-btn"
                  title="停止播放"
                  @click="stopTour"
                >&#9632;</button>
                <button class="panel-close" @click="closePanel">&times;</button>
              </div>
            </div>

            <!-- Panel Body -->
            <PeriodPanel
              v-if="activePanel === 'period'"
              :period-label="currentPeriodLabel"
              :cities="periodCities"
              @select-city="selectCityFromPeriod"
            />
            <CityPanel
              v-else
              :location="selectedLocation!"
              @go-to-painting="goToPainting"
            />
          </div>
        </transition>
      </div>

      <!-- Period Bar (merged legend + filter + tour) -->
      <div class="period-bar">
        <button
          class="period-btn reset-btn"
          :class="{ active: selectedPeriod === null }"
          @click="onFilterAll"
        >
          <span class="period-btn-label">全 程</span>
          <span class="period-btn-year">1686-1756</span>
        </button>
        <button
          v-for="period in PERIOD_CONFIG"
          :key="period.id"
          class="period-btn"
          :class="{ active: selectedPeriod === period.id }"
          @click="selectPeriod(period.id)"
        >
          <span class="period-btn-dot" :style="{ background: period.color }"></span>
          <span class="period-btn-label">{{ period.label }}</span>
          <span class="period-btn-year">{{ formatYearRange(period.yearRange) }}</span>
        </button>
        <button
          class="period-btn tour-btn"
          :class="{ playing: tourState === 'playing', paused: tourState === 'paused' }"
          @click="toggleTour"
        >
          <span v-if="tourState === 'playing'">&#9646;&#9646; 暂停</span>
          <span v-else-if="tourState === 'paused'">&#9654; 继续</span>
          <span v-else>&#9654; 播放行旅</span>
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
import PeriodPanel from './MapMode/PeriodPanel.vue'
import CityPanel from './MapMode/CityPanel.vue'
import chinaGeoJSON from '@/assets/china-geojson.json'

const router = useRouter()
const chartContainer = ref<HTMLElement | null>(null)
const selectedLocation = ref<LocationWithPaintings | null>(null)
const activePanel = ref<'period' | 'city' | null>(null)
const hasInteracted = ref(false)

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
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let tourTimer: ReturnType<typeof setTimeout> | null = null
const tourState = ref<'idle' | 'playing' | 'paused'>('idle')
const tourIndex = ref(0)
const tourVisitedLocIds = ref<Set<string> | null>(null)
const isTourActive = computed(() => tourState.value !== 'idle')

// ── Memoized timeline ──

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

const cachedTimeline = computed<TimelineEntry[]>(() => {
  // Detailed travel sequence based on historical anchor points,
  // forming a realistic continuous path without impossible parallel lines.
  const seq: [string, number, number, string][] = [
    // ▸ 早年求学与仕进（1686–1713）
    ['xinghua', 1686, 1713, 'early'],
    ['nanjing', 1711, 1711, 'exam-court'],
    ['chengde', 1713, 1713, 'exam-court'],
    ['beijing', 1713, 1718, 'exam-court'],
    // ▸ 江湖卖画（1718–1730）
    ['yangzhou', 1718, 1727, 'wandering'],
    ['huzhou', 1727, 1727, 'wandering'],
    ['yangzhou', 1727, 1730, 'wandering'],
    // ▸ 再度入都（1730–1736）
    ['beijing', 1730, 1732, 'wandering'],
    ['yangzhou', 1732, 1736, 'wandering'],
    ['linyi', 1736, 1736, 'wandering'],
    // ▸ 山东仕途（1736–1744）
    ['beijing', 1736, 1737, 'shandong'],
    ['linzi', 1737, 1738, 'shandong'],
    ['tengxian', 1738, 1740, 'shandong'],
    ['jinan', 1740, 1744, 'late'],
    ['xinghua', 1744, 1745, 'late'],
    // ▸ 扬州终老（1745–1756）
    ['yangzhou', 1745, 1756, 'late'],
    ['nantong', 1756, 1756, 'late'],
  ]
  return seq.map(([locId, startYear, endYear, periodId]) => {
    const loc = LI_SHAN_LOCATIONS.find((l) => l.id === locId)!
    const cfg = PERIOD_CONFIG.find((p) => p.id === periodId)!
    return {
      locId, name: loc.name, lat: loc.lat, lng: loc.lng,
      startYear, endYear, periodId,
      periodLabel: cfg.label, periodColor: cfg.color,
    }
  })
})

interface MarkerMeta {
  order: number
  color: string
  name: string
}

const cachedMarkerMeta = computed<Map<string, MarkerMeta>>(() => {
  const seen = new Map<string, MarkerMeta>()
  let order = 0
  for (const entry of cachedTimeline.value) {
    if (!seen.has(entry.locId)) {
      order++
      seen.set(entry.locId, { order, color: entry.periodColor, name: entry.name })
    }
  }
  return seen
})

// Tour entries: follow the timeline step-by-step so each step
// reveals exactly one segment. Same city may appear multiple times
// (return visits) but each step advances the path by one segment.
const tourEntries = computed(() => cachedTimeline.value)

// ── City quick list (top-left overlay) ──

const cityQuickList = computed(() => {
  const result: { locId: string; order: number; color: string; name: string; province: string; paintingCount: number }[] = []
  for (const entry of cachedTimeline.value) {
    if (result.find((c) => c.locId === entry.locId)) continue
    const loc = locationsWithPaintings.value.find((l) => l.id === entry.locId)
    result.push({
      locId: entry.locId,
      order: result.length + 1,
      color: entry.periodColor,
      name: entry.name,
      province: loc?.province || '',
      paintingCount: loc?.paintingCount || 0,
    })
  }
  return result
})

function selectCityFromList(locId: string) {
  markInteraction()
  if (tourState.value !== 'idle') stopTour()
  const loc = locationsWithPaintings.value.find((l) => l.id === locId)
  if (!loc) return
  selectedLocation.value = loc
  activePanel.value = 'city'
  updateChartEffectScatter([loc.lng, loc.lat])
}

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
  const seen = new Set<string>()
  return cachedTimeline.value
    .filter((e) => e.periodId === selectedPeriod.value)
    .filter((e) => {
      if (seen.has(e.locId)) return false
      seen.add(e.locId)
      return true
    })
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

// ── Helpers ──

function getPeriodLabel(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.label || periodId
}

function getPeriodColor(periodId: string): string {
  return PERIOD_CONFIG.find((p) => p.id === periodId)?.color || '#8b7d6b'
}

function formatYearRange(range: [number, number]): string {
  const [s, e] = range
  return s === e ? `${s}` : `${s}-${e}`
}

function markInteraction() {
  hasInteracted.value = true
}

// ── Period / City selection ──

function selectPeriod(periodId: string | null) {
  _selectPeriod(periodId)
  markInteraction()
  // If tour is playing and user manually clicks a period, stop tour
  if (tourState.value !== 'idle') stopTour()
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

function onFilterAll() {
  selectPeriod(null)
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
    backToPeriod()
  } else {
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

// ── Tour mode ──

function toggleTour() {
  if (tourState.value === 'playing') {
    pauseTour()
  } else if (tourState.value === 'paused') {
    resumeTour()
  } else {
    startTour()
  }
}

function startTour() {
  tourState.value = 'playing'
  tourIndex.value = 0
  tourVisitedLocIds.value = new Set()
  markInteraction()
  // Reset filter to "全 程"
  if (selectedPeriod.value) _selectPeriod(null)
  advanceTour()
}

function advanceTour() {
  if (tourState.value !== 'playing') return
  const entry = tourEntries.value[tourIndex.value]
  if (!entry) {
    stopTour()
    return
  }

  const prevEntry = tourIndex.value > 0 ? tourEntries.value[tourIndex.value - 1] : null

  tourVisitedLocIds.value!.add(entry.locId)

  // Merge mode: existing segments stay, only new segment draws from start.
  // animationDurationUpdate:0 prevents old segments from morphing.
  updateChartData(undefined, true)

  const loc = locationsWithPaintings.value.find((l) => l.id === entry.locId)
  if (loc) {
    selectedLocation.value = loc
    activePanel.value = 'city'

    // Animate traveler dot along arc from previous city → current city
    if (prevEntry && prevEntry.locId !== entry.locId) {
      const prevLoc = locationsWithPaintings.value.find((l) => l.id === prevEntry.locId)
      if (prevLoc) {
        animateTravel([prevLoc.lng, prevLoc.lat], [loc.lng, loc.lat])
      } else {
        updateChartEffectScatter([loc.lng, loc.lat])
      }
    } else {
      updateChartEffectScatter([loc.lng, loc.lat])
    }
  }
  tourIndex.value++
  tourTimer = setTimeout(advanceTour, 2800)
}

function animateTravel(from: [number, number], to: [number, number]) {
  const arc = computeArc(from[0], from[1], to[0], to[1], 40)
  let startTime: number | null = null
  const duration = 900

  function frame(now: number) {
    if (!startTime) startTime = now
    const raw = Math.min((now - startTime) / duration, 1)
    const t = raw < 0.5 ? 4 * raw ** 3 : 1 - (-2 * raw + 2) ** 3 / 2 // easeInOutCubic
    const idx = Math.min(Math.floor(t * (arc.length - 1)), arc.length - 1)
    updateChartEffectScatter(arc[idx])
    if (raw < 1) {
      requestAnimationFrame(frame)
    }
  }
  requestAnimationFrame(frame)
}

function pauseTour() {
  tourState.value = 'paused'
  if (tourTimer) {
    clearTimeout(tourTimer)
    tourTimer = null
  }
}

function resumeTour() {
  tourState.value = 'playing'
  advanceTour()
}

function stopTour() {
  tourState.value = 'idle'
  tourIndex.value = 0
  tourVisitedLocIds.value = null
  if (tourTimer) {
    clearTimeout(tourTimer)
    tourTimer = null
  }
  selectedLocation.value = null
  activePanel.value = null
  updateChartEffectScatter(null)
  updateChartData()
}

// ── ECharts ──

const CHINESE_NUMS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩', '⑪']
const VISITED_PROVINCES = ['北京市', '河北省', '江苏省', '浙江省', '山东省']

// Per-city label position: assign based on longitude to avoid overlaps
// Eastern cities (>118.3°E) get 'left', western get 'right'
const LABEL_POSITIONS: Record<string, { position: 'left' | 'right'; offset?: [number, number] }> = {
  xinghua:  { position: 'left' },
  nanjing:  { position: 'left' },
  chengde:  { position: 'right' },
  yangzhou: { position: 'left',  offset: [0, -8] },
  huzhou:   { position: 'left' },
  linyi:    { position: 'right' },
  linzi:    { position: 'right' },
  tengxian: { position: 'left' },
  beijing:  { position: 'right' },
  jinan:    { position: 'left' },
  nantong:  { position: 'left' },
}

function makeScatterData(locations: LocationWithPaintings[]) {
  return locations.map((loc) => {
    const meta = cachedMarkerMeta.value.get(loc.id)
    const order = meta?.order || 0
    const color = meta?.color || '#c9a96e'
    const num = CHINESE_NUMS[order - 1] || `${order}`
    const labelCfg = LABEL_POSITIONS[loc.id] || { position: 'right' as const }
    const dx = labelCfg.position === 'left' ? -6 : 6
    const extraOffset = labelCfg.offset || [0, 0]
    return {
      name: `${num} ${loc.name}`,
      value: [loc.lng, loc.lat, loc.paintingCount],
      locId: loc.id,
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      label: {
        color,
        position: labelCfg.position,
        offset: [dx + extraOffset[0], extraOffset[1]],
        distance: 2,
      },
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
  // Subtle bulge proportional to distance, always to the right of travel direction
  const bulge = Math.min(dist * 0.18, 0.5)
  // Right perpendicular: (dy, -dx) — gives consistent clockwise arcs
  const len = dist || 1
  const px = dy / len
  const py = -dx / len
  const cx = mx + px * bulge
  const cy = my + py * bulge

  const pts: [number, number][] = []
  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints
    const x = (1 - t) ** 2 * lng1 + 2 * (1 - t) * t * cx + t * t * lng2
    const y = (1 - t) ** 2 * lat1 + 2 * (1 - t) * t * cy + t * t * lat2
    pts.push([x, y])
  }
  return pts
}

/** Segment i (timeline[i]→timeline[i+1]) is revealed at tour step i+1. */
function segmentOpacity(segmentIndex: number, tourEntryCount: number): number {
  const stepsAgo = tourEntryCount - 2 - segmentIndex
  if (stepsAgo <= 0) return 0.7
  if (stepsAgo === 1) return 0.28
  if (stepsAgo === 2) return 0.1
  return 0.04 // 残影
}

function buildSegments(
  visibleLocIds: Set<string> | null,
  tourEntryCount: number,
): SegmentData[] {
  const timeline = cachedTimeline.value
  const segments: SegmentData[] = []

  for (let i = 0; i < timeline.length - 1; i++) {
    const a = timeline[i]
    const b = timeline[i + 1]
    if (a.lat === b.lat && a.lng === b.lng) continue
    if (visibleLocIds && (!visibleLocIds.has(a.locId) || !visibleLocIds.has(b.locId))) continue

    // Tour: only reveal segment i once entry i+1 has been visited.
    // This prevents multiple segments between the same two cities
    // from all lighting up at once (e.g. 北京→扬州 appearing twice).
    if (tourEntryCount > 0 && i + 1 >= tourEntryCount) continue

    const opacity = tourEntryCount > 0 ? segmentOpacity(i, tourEntryCount) : 0.7

    const arc = computeArc(a.lng, a.lat, b.lng, b.lat, 48)
    segments.push({
      coords: arc,
      lineStyle: { color: a.periodColor, width: 3, opacity },
      periodId: a.periodId,
      fromName: a.name,
      toName: b.name,
      fromYear: a.startYear,
      toYear: b.startYear,
    })
  }
  return segments
}

function buildOption(locations: LocationWithPaintings[], allLocations: LocationWithPaintings[], periodFilter: string | null, tourEntryCount = 0) {
  const visibleLocIds = periodFilter
    ? new Set(locations.map((l) => l.id))
    : null
  const scatterData = makeScatterData(
    periodFilter ? allLocations : locations,
  )

  if (periodFilter) {
    for (const d of scatterData) {
      if (!visibleLocIds!.has(d.locId)) {
        d.itemStyle.opacity = 0.22
        d.label.opacity = 0.22
      }
    }
  }

  const segments = buildSegments(visibleLocIds, tourEntryCount)

  const option: any = {
    backgroundColor: '#f8f5f0',
    animation: true,
    animationDuration: 800,
    animationDurationUpdate: 0,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.seriesType === 'scatter' || params.seriesType === 'effectScatter') {
          const count = params.value?.[2] ?? 0
          const locId = params.data?.locId
          if (locId) {
            const meta = cachedMarkerMeta.value.get(locId)
            const loc = allLocations.find((l) => l.id === locId)
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
      center: [118, 36],
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

  option.series.push({
    type: 'lines',
    coordinateSystem: 'geo',
    polyline: true,
    animationDuration: tourEntryCount > 0 ? 0 : 800,
    data: segments.map((seg) => ({
      coords: seg.coords,
      lineStyle: seg.lineStyle,
      fromName: seg.fromName,
      toName: seg.toName,
      fromYear: seg.fromYear,
      toYear: seg.toYear,
    })),
    lineStyle: { width: 3 },
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

  option.series.push({
    type: 'scatter',
    coordinateSystem: 'geo',
    data: scatterData,
    encode: { tooltip: [2] },
    symbolSize: (val: number[]) => Math.max(7, Math.min(22, Math.sqrt(val[2]) * 2.2)),
    label: {
      show: true,
      formatter: '{b}',
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

function updateChartData(locations?: LocationWithPaintings[], smooth = false) {
  if (!chart) return
  const locs = locations || filteredLocations.value
  const tourEntryCount = tourState.value !== 'idle' ? tourIndex.value + 1 : 0
  const option = buildOption(locs, locationsWithPaintings.value, selectedPeriod.value, tourEntryCount)
  // replace mode (notMerge=true): lines clear and redraw from start — used for period switches
  // merge mode (notMerge=false): new segments animate in, existing stay — used for tour steps
  chart.setOption(option, !smooth)
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
      markInteraction()
      if (tourState.value !== 'idle') stopTour()
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

function handleResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    chart?.resize()
  }, 150)
}

onMounted(async () => {
  await fetchData()
  await nextTick()
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeTimer) clearTimeout(resizeTimer)
  if (tourTimer) clearTimeout(tourTimer)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.map-mode-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: #f8f5f0;
  position: relative;
  overflow: hidden;
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

/* ── Smart Hint ── */
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
  animation: hint-pulse 3s ease-in-out infinite;
}
@keyframes hint-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* ── City Quick List ── */
.city-quick-list {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 5;
  background: rgba(250, 249, 245, 0.92);
  backdrop-filter: blur(6px);
  border: 1px solid #e8e4d8;
  border-radius: 10px;
  padding: 8px 0;
  min-width: 140px;
  max-width: 180px;
  max-height: calc(100% - 24px);
  overflow-y: auto;
  box-shadow: 0 2px 12px rgba(44, 36, 22, 0.06);
}
.city-quick-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.7rem;
  color: #b8a990;
  letter-spacing: 0.12em;
  padding: 4px 14px 8px;
  user-select: none;
}
.city-quick-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px 5px 8px;
  cursor: pointer;
  transition: background 0.15s;
  border-radius: 4px;
  margin: 0 4px;
  white-space: nowrap;
}
.city-quick-item:hover {
  background: rgba(201, 169, 110, 0.1);
}
.city-quick-item.active {
  background: rgba(201, 169, 110, 0.15);
}
.city-quick-num {
  font-size: 0.72rem;
  flex-shrink: 0;
  width: 16px;
  text-align: center;
}
.city-quick-name {
  font-size: 0.82rem;
  font-weight: 500;
  color: #2c2416;
  flex: 1;
  white-space: nowrap;
}
.city-quick-province {
  font-size: 0.65rem;
  color: #b8a990;
  flex-shrink: 0;
}
.city-quick-count {
  display: none;
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
  overflow: hidden;
  z-index: 10;
}

.panel-header {
  display: flex;
  align-items: center;
  padding: 24px 24px 0;
  gap: 8px;
}

.panel-location {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.5rem;
  font-weight: 500;
  color: #2c2416;
  margin: 0;
  letter-spacing: 0.06em;
}

.panel-year-range {
  font-size: 0.78rem;
  color: #8b7d6b;
  flex: 1;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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

.tour-stop-btn {
  font-size: 0.8rem;
  color: #c96442;
  border: 1px solid #e8d0c0;
  border-radius: 6px;
  width: 28px;
  height: 28px;
}
.tour-stop-btn:hover { background: rgba(201, 100, 66, 0.08); }

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
  white-space: nowrap;
}
.panel-back:hover { border-color: #c9a96e; color: #c9a96e; }

/* Slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-slide-enter-from { transform: translateX(100%); opacity: 0; }
.panel-slide-leave-to { transform: translateX(100%); opacity: 0; }

/* ── Period Bar (merged legend + filter + tour) ── */
.period-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 14px 24px;
  background: #f8f5f0;
  border-top: 1px solid #e8e4d8;
  flex-wrap: wrap;
}
.period-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 18px;
  border: 1px solid #d8d0c0;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
  min-width: 80px;
}
.period-btn:hover { border-color: #c9a96e; }
.period-btn.active {
  background: #f6f0e2;
  border-color: #c9a96e;
}
.period-btn-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-bottom: 2px;
}
.period-btn-label {
  font-size: 0.82rem;
  color: #5e5d59;
  font-weight: 500;
}
.period-btn.active .period-btn-label { color: #2c2416; }
.period-btn-year {
  font-size: 0.68rem;
  color: #b8a990;
}
.period-btn.active .period-btn-year { color: #8b7d6b; }

.reset-btn .period-btn-label {
  font-weight: 600;
  letter-spacing: 0.08em;
}

/* Tour button */
.tour-btn {
  border-color: #c9a96e;
  background: #faf6ee;
  min-width: auto;
  padding: 8px 20px;
}
.tour-btn:hover { background: #f6f0e2; }
.tour-btn.playing {
  background: #c96442;
  border-color: #c96442;
}
.tour-btn.playing .period-btn-label,
.tour-btn.playing span { color: #fff; }
.tour-btn.paused {
  background: #faf6ee;
  border-color: #c9a96e;
}

/* Responsive */
@media (max-width: 1024px) {
  .info-panel { width: 340px; min-width: 340px; }
  .period-btn { padding: 6px 12px; min-width: 60px; }
  .period-btn-label { font-size: 0.76rem; }
}
@media (max-width: 768px) {
  .map-main { flex-direction: column; }
  .map-wrapper { min-height: 340px; }
  .city-quick-list {
    top: 8px;
    left: 8px;
    padding: 4px 0;
    border-radius: 8px;
  }
  .city-quick-item { padding: 4px 8px; }
  .city-quick-name { font-size: 0.76rem; }
  .info-panel {
    width: 100%;
    min-width: 0;
    max-height: 50vh;
    border-left: none;
    border-top: 1px solid #e8e4d8;
    box-shadow: 0 -2px 16px rgba(44, 36, 22, 0.06);
  }
  .period-bar { gap: 6px; padding: 10px 12px; }
  .period-btn { padding: 6px 10px; min-width: 50px; border-radius: 8px; }
  .period-btn-label { font-size: 0.7rem; }
  .period-btn-year { font-size: 0.62rem; }
}
</style>
