<template>
  <div class="map-mode-page">
    <!-- Loading -->
    <div v-if="loading" class="map-loading">
      <p class="loading-text">{{ $t('mapmode.t1') }}</p>
      <el-skeleton :rows="6" animated />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="map-error">
      <el-result icon="error" :title="$t('mapmode.a1')" :sub-title="error">
        <template #extra>
          <el-button type="primary" @click="retry">{{ $t('mapmode.t2') }}</el-button>
        </template>
      </el-result>
    </div>

    <!-- Main Content -->
    <template v-else>
      <!-- Top Bar: artist name + breadcrumb -->
      <div class="map-topbar">
        <router-link :to="`/artist/${encodeURIComponent(artistName)}`" class="topbar-back">
          &larr;&nbsp;{{ artistName }}
        </router-link>
        <span class="topbar-title">{{ pageTitle }}</span>
      </div>

      <div class="map-main" :class="{ 'panel-open': activePanel }">
        <!-- ECharts Map -->
        <div class="map-wrapper">
          <!-- 天气粒子层（仅有情绪数据时显示） -->
          <WeatherCanvas
            v-if="emotionTimeline.hasEmotionData"
            :emotion="currentWeatherEmotion"
            :enabled="true"
          />
          <WeatherCard
            v-if="emotionTimeline.hasEmotionData"
            :emotion="currentWeatherEmotion"
            :context-label="currentWeatherContext"
            :painting-count="currentWeatherCount"
            :temp="currentWeatherTemp"
          />
          <div ref="chartContainer" class="chart-container"></div>

          <!-- Smart Hint: hides after first interaction -->
          <div v-if="!activePanel" class="map-hint">
            点击城市标记查看{{ artistName }}在该地的经历与画作
          </div>

          <!-- City Quick List (top-left overlay) -->
          <div class="city-quick-list">
            <div class="city-quick-title">{{ $t('mapmode.t3') }}</div>
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
                  :title="$t('mapmode.a2')"
                  @click="stopTour"
                >&#9632;</button>
                <button class="panel-close" @click="closePeriodPanel">&times;</button>
              </div>
            </div>

            <!-- City Detail Header -->
            <div v-else class="panel-header">
              <button v-if="selectedPeriod" class="panel-back" @click="backToPeriod">{{ $t('mapmode.t4') }}</button>
              <h2 class="panel-location">{{ selectedLocation?.name }}</h2>
              <div class="panel-header-actions">
                <button
                  v-if="isTourActive"
                  class="panel-close tour-stop-btn"
                  :title="$t('mapmode.a2')"
                  @click="stopTour"
                >&#9632;</button>
                <button class="panel-close" @click="closePanel">&times;</button>
              </div>
            </div>

            <!-- Panel Body -->
            <PeriodPanel
              v-if="activePanel === 'period'"
              :artist-name="artistName"
              :period-label="currentPeriodLabel"
              :cities="periodCities"
              @select-city="selectCityFromPeriod"
            />
            <CityPanel
              v-else
              :location="selectedLocation!"
              :periods="periods"
              @go-to-painting="goToPainting"
            />
          </div>
        </transition>
      </div>

      <!-- Period Bar (merged legend + filter + tour) -->
      <div class="period-bar">
        <button
          class="period-btn reset-btn"
          :class="{ active: selectedPeriod === null && tourState === 'idle' }"
          @click="onFilterAll"
        >
          <span class="period-btn-label">{{ $t('mapmode.t5') }}</span>
          <span class="period-btn-year">{{ totalYearRange }}</span>
        </button>
        <button
          v-for="period in periods"
          :key="period.id"
          class="period-btn"
          :class="{ active: selectedPeriod === period.id, 'period-btn-tour': tourHighlightedPeriodId === period.id }"
          :data-pid="period.id"
          :title="periodTooltips[period.id]"
          @click="selectPeriod(period.id)"
        >
          <span class="period-btn-dot" :style="{ background: period.color }"></span>
          <span class="period-btn-label">{{ period.label }}</span>
          <span v-if="emotionTimeline.hasEmotionData" class="period-btn-emoji">{{ periodEmoji(period.id) }}</span>
          <span class="period-btn-year">{{ formatYearRange(period.yearRange) }}</span>
        </button>
        <button
          class="period-btn tour-btn"
          :class="{ playing: tourState === 'playing', paused: tourState === 'paused' }"
          @click="toggleTour"
        >
          <span v-if="tourState === 'playing'">{{ $t('mapmode.t6') }}<em class="tour-progress">{{ tourIndex }}/{{ tourEntries.length }}</em></span>
          <span v-else-if="tourState === 'paused'">{{ $t('mapmode.t7') }}<em class="tour-progress">{{ tourIndex }}/{{ tourEntries.length }}</em></span>
          <span v-else>{{ $t('mapmode.t8') }}</span>
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import echarts from '../utils/echarts'
import { useMapData } from './MapMode/useMapData'
import type { MapLocation as LocationWithPaintings, PeriodConfig } from './MapMode/locations'
import { lookupCity, coordKey } from './MapMode/locations'
import type { Painting } from './MapMode/useMapData'
import PeriodPanel from './MapMode/PeriodPanel.vue'
import CityPanel from './MapMode/CityPanel.vue'
import WeatherCanvas from './MapMode/WeatherCanvas.vue'
import WeatherCard from './MapMode/WeatherCard.vue'
import chinaGeoJSON from '@/assets/china-geojson.json'

const router = useRouter()
const route = useRoute()
const chartContainer = ref<HTMLElement | null>(null)
const selectedLocation = ref<LocationWithPaintings | null>(null)
const activePanel = ref<'period' | 'city' | null>(null)
const hasInteracted = ref(false)

const {
  loading,
  error,
  artistName,
  artistBirthYear,
  artistDeathYear,
  chronology,
  locationsWithPaintings,
  periods,
  filteredLocations,
  fetchData,
  selectedPeriod,
  selectPeriod: _selectPeriod,
  emotionTimeline,
} = useMapData()

const pageTitle = computed(() =>
  emotionTimeline.value.hasEmotionData ? '行旅气象地图' : '翰墨行旅'
)

const EMOTION_EMOJI: Record<string, string> = {
  sunny: '☀️',
  clear: '🌤️',
  cloudy: '⛅',
  overcast: '☁️',
  rain: '🌧️',
  storm: '⛈️',
  snow: '❄️',
}

function periodEmoji(periodId: string): string {
  const ep = emotionTimeline.value.periods.find((p) => p.id === periodId)
  if (!ep || ep.paintingCount === 0) return '🌤️'
  return EMOTION_EMOJI[ep.emotion] || '🌤️'
}

const EMOTION_PATH_COLOR: Record<string, string> = {
  sunny: '#c45a3c',
  clear: '#b8a070',
  cloudy: '#a09080',
  overcast: '#6a6070',
  rain: '#5a5078',
  storm: '#4a3040',
  snow: '#8a9ab0',
}

function emotionPathColor(periodId: string): string | null {
  if (!emotionTimeline.value.hasEmotionData) return null
  const ep = emotionTimeline.value.periods.find((p) => p.id === periodId)
  if (!ep || ep.paintingCount === 0) return null
  return EMOTION_PATH_COLOR[ep.emotion] || null
}

// 当前展示的天气状态：
// - 选中某城市 → 该城市所属时期的情绪
// - 选中某时期 → 该时期的情绪
// - Tour 模式 → 跟随当前 entry
// - 全程无选择 → 默认中性平和（不取最大时期，否则开头就是"雨"缺少对比基线）
const currentEmotionPeriod = computed(() => {
  if (!emotionTimeline.value.hasEmotionData) return null
  const eps = emotionTimeline.value.periods.filter((p) => p.paintingCount > 0)
  if (eps.length === 0) return null

  // 优先：选中的时期
  if (selectedPeriod.value) {
    const ep = eps.find((p) => p.id === selectedPeriod.value)
    if (ep) return ep
  }
  // 选中的城市 → 取城市的第一个 period 的情绪
  if (selectedLocation.value && selectedLocation.value.periods?.length) {
    const ep = eps.find((p) => p.id === selectedLocation.value!.periods![0])
    if (ep) return ep
  }
  // Tour 模式：跟随当前 entry
  if (tourState.value !== 'idle' && tourEntries.value[tourIndex.value]) {
    const entry = tourEntries.value[tourIndex.value]
    const ep = eps.find((p) => p.id === entry.periodId)
    if (ep) return ep
  }
  // 全程无选择 → null（前端降级到 clear）
  return null
})

const currentWeatherEmotion = computed<'sunny' | 'clear' | 'cloudy' | 'overcast' | 'rain' | 'storm' | 'snow'>(() => {
  return currentEmotionPeriod.value?.emotion || 'clear'
})

const currentWeatherContext = computed(() => {
  const ep = currentEmotionPeriod.value
  if (!ep) return '全程'
  if (selectedLocation.value) return selectedLocation.value.name
  if (selectedPeriod.value) return ep.label
  if (tourState.value !== 'idle' && tourEntries.value[tourIndex.value]) {
    return tourEntries.value[tourIndex.value].name
  }
  return ep.label
})

const currentWeatherCount = computed(() => currentEmotionPeriod.value?.paintingCount || 0)
const currentWeatherTemp = computed(() => currentEmotionPeriod.value?.temp || 0)

const totalYearRange = computed(() => {
  const start = artistBirthYear.value || ''
  const end = artistDeathYear.value || ''
  return start && end ? `${start}-${end}` : (start || end || '')
})

let chart: echarts.ECharts | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null
let tourTimer: ReturnType<typeof setTimeout> | null = null
const tourState = ref<'idle' | 'playing' | 'paused'>('idle')
const tourIndex = ref(0)
const tourVisitedLocIds = ref<Set<string> | null>(null)
const tourHighlightedPeriodId = ref<string | null>(null)
const tourStep = ref(0)
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
  // 收集所有 (year, location) 对，按年份排序
  const allEvents: { year: number; locId: string; name: string; lat: number; lng: number }[] = []
  for (const loc of locationsWithPaintings.value) {
    for (const line of (loc.chronologyLines || [])) {
      const m = line.match(/^(\d+)年/)
      if (!m) continue
      const y = parseInt(m[1])
      allEvents.push({ year: y, locId: loc.id, name: loc.name, lat: loc.lat, lng: loc.lng })
    }
  }
  allEvents.sort((a, b) => a.year - b.year)

  // 按地点分组连续事件：同城市连续事件合并为一个节点
  const entries: TimelineEntry[] = []
  for (const ev of allEvents) {
    const last = entries[entries.length - 1]
    if (last && last.locId === ev.locId) {
      // 同一地点连续 → 更新 endYear
      last.endYear = ev.year
    } else {
      // 新地点（或重返旧地）→ 新节点
      const period = periods.value.find(p => ev.year >= p.yearRange[0] && ev.year <= p.yearRange[1])
      entries.push({
        locId: ev.locId,
        name: ev.name,
        lat: ev.lat,
        lng: ev.lng,
        startYear: ev.year,
        endYear: ev.year,
        periodId: period?.id || 'p0',
        periodLabel: period?.label || '',
        periodColor: period?.color || '#8b7d6b',
      })
    }
  }
  return entries
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
  const result: { locId: string; order: number; color: string; name: string; paintingCount: number }[] = []
  for (const entry of cachedTimeline.value) {
    if (result.find((c) => c.locId === entry.locId)) continue
    const loc = locationsWithPaintings.value.find((l) => l.id === entry.locId)
    result.push({
      locId: entry.locId,
      order: result.length + 1,
      color: entry.periodColor,
      name: entry.name,
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
  const cfg = periods.value.find((p) => p.id === selectedPeriod.value)
  if (!cfg) return []

  return locationsWithPaintings.value
    .filter(loc => {
      // AI data: 直接用 location.periods 判断
      if (loc.periods && loc.periods.length > 0) {
        return loc.periods.includes(selectedPeriod.value!)
      }
      // 回退：按年谱条目年份确定
      const chronYears = (chronology.value || []).filter(e => {
        const y = parseInt(String(e.year || '')); if (isNaN(y)) return false
        const match = lookupCity(e.location || '')
        return match && coordKey(match.lat, match.lng) === loc.id && y >= cfg.yearRange[0] && y <= cfg.yearRange[1]
      })
      if (chronYears.length > 0) return true
      // 再回退：检查画作年份
      return loc.paintings.some(p => {
        const py = Number(p.year); if (isNaN(py)) return false
        return py >= cfg.yearRange[0] && py <= cfg.yearRange[1]
      })
    })
    .map(loc => {
      const brief = loc.description?.split('\n')[0]?.slice(0, 50) || ''
      const chronYears = (chronology.value || []).filter(e => {
        const match = lookupCity(e.location || '')
        return match && coordKey(match.lat, match.lng) === loc.id
      }).map(e => parseInt(String(e.year || ''))).filter(y => !isNaN(y) && y >= cfg.yearRange[0] && y <= cfg.yearRange[1]).sort()
      return {
        locId: loc.id,
        name: loc.name,
        year: chronYears[0] || cfg.yearRange[0],
        briefDesc: brief || loc.description?.slice(0, 50) || '',
        color: cfg.color,
      }
    })
})

const currentPeriodLabel = computed(() => {
  if (!selectedPeriod.value) return ''
  return periods.value.find((p) => p.id === selectedPeriod.value)?.label || ''
})

const currentPeriodYearRange = computed(() => {
  if (!selectedPeriod.value) return ''
  const cfg = periods.value.find((p) => p.id === selectedPeriod.value)
  if (!cfg) return ''
  const [s, e] = cfg.yearRange
  return s === e ? `${s}年` : `${s} — ${e}年`
})

const periodTooltips = computed(() => {
  const map: Record<string, string> = {}
  const locs = locationsWithPaintings.value
  if (!locs.length) return map
  for (const period of periods.value) {
    const cities = locs.filter((l) => {
      // AI data: 直接用 location.periods
      if (l.periods && l.periods.length > 0) return l.periods.includes(period.id)
      // 回退：chronology 年份判断
      const chronMatch = (chronology.value || []).some(e => {
        const y = parseInt(String(e.year || '')); if (isNaN(y)) return false
        const m = lookupCity(e.location || '')
        return m && coordKey(m.lat, m.lng) === l.id && y >= period.yearRange[0] && y <= period.yearRange[1]
      })
      if (chronMatch) return true
      // 再回退：画作年份
      return l.paintings.some(p => {
        const py = Number(p.year); if (isNaN(py)) return false
        return py >= period.yearRange[0] && py <= period.yearRange[1]
      })
    })
    const names = cities.map((c) => c.name).join('、')
    const total = cities.reduce((sum, c) => sum + c.paintingCount, 0)
    map[period.id] = names ? `${names} · 共 ${total} 幅` : '暂无记录'
  }
  return map
})

// ── Helpers ──

function getPeriodLabel(periodId: string): string {
  return periods.value.find((p) => p.id === periodId)?.label || periodId
}

function getPeriodColor(periodId: string): string {
  return periods.value.find((p) => p.id === periodId)?.color || '#8b7d6b'
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
  const route = router.resolve(`/tiba/${imageId}`)
  window.open(route.href, '_blank')
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

  // 高亮当前 stage
  tourHighlightedPeriodId.value = entry.periodId
  scrollToTourPeriod()

  const prevEntry = tourIndex.value > 0 ? tourEntries.value[tourIndex.value - 1] : null

  tourVisitedLocIds.value!.add(entry.locId)

  // Replace mode (notMerge=true): redraw all segments at correct opacity each step.
  // Safe because lines series has animationDuration:0 during tour — no visible flash.
  updateChartData(undefined, false)

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
  // 自适应速度：entry 多时快一点，少时慢一点
  const total = tourEntries.value.length
  const delay = total > 20 ? 2200 : total > 10 ? 3200 : 4200
  tourTimer = setTimeout(() => advanceTour(), delay)
}

function scrollToTourPeriod() {
  nextTick(() => {
    const activeBtn = document.querySelector('.period-btn.period-btn-tour')
    if (activeBtn) activeBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  })
}

function animateTravel(from: [number, number], to: [number, number]) {
  const arc = computeArc(from[0], from[1], to[0], to[1], 60)
  let startTime: number | null = null
  const duration = 1400

  function frame(now: number) {
    if (!startTime) startTime = now
    const raw = Math.min((now - startTime) / duration, 1)
    // 更平滑的 ease-out：cubic
    const t = 1 - (1 - raw) ** 3
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
  tourStep.value = 0
  tourVisitedLocIds.value = null
  tourHighlightedPeriodId.value = null
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

// 自动从 locations 提取省份，东经 >118.3 标签在左，否则在右
const visitedProvinces = computed(() => {
  const set = new Set<string>()
  for (const loc of locationsWithPaintings.value) {
    const prov = chinaGeoJSON.features.find((f: any) => {
      const cp = f.properties?.center || f.properties?.cp
      return cp && Math.abs(cp[0] - loc.lng) < 2.0 && Math.abs(cp[1] - loc.lat) < 1.5
    })
    if (prov) set.add(prov.properties.name)
  }
  return [...set]
})

function getLabelPosition(locId: string): { position: 'left' | 'right'; offset?: [number, number] } {
  const loc = locationsWithPaintings.value.find(l => l.id === locId)
  if (!loc) return { position: 'right' }
  return loc.lng > 118.3 ? { position: 'left' } : { position: 'right' }
}

function makeScatterData(locations: LocationWithPaintings[]) {
  const result = locations.map((loc) => {
    const meta = cachedMarkerMeta.value.get(loc.id)
    const order = meta?.order || 0
    const color = meta?.color || '#c9a96e'
    const num = CHINESE_NUMS[order - 1] || `${order}`
    const labelCfg = getLabelPosition(loc.id)
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
  // Sort by travel order so markers fade in sequentially (① → ② → ③ ...)
  result.sort((a, b) => {
    const orderA = cachedMarkerMeta.value.get(a.locId)?.order ?? 99
    const orderB = cachedMarkerMeta.value.get(b.locId)?.order ?? 99
    return orderA - orderB
  })
  return result
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
    const lineColor = emotionPathColor(a.periodId) || a.periodColor

    const arc = computeArc(a.lng, a.lat, b.lng, b.lat, 48)
    segments.push({
      coords: arc,
      lineStyle: { color: lineColor, width: 3, opacity },
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

  // ── 动态计算地图缩放和中心点 ──
  // 时期筛选时用筛选后的地点，全览时用全部地点
  const boundsLocs = periodFilter && locations.length > 0 ? locations : allLocations
  let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180
  for (const loc of boundsLocs) {
    if (loc.lng < 70 || loc.lng > 140 || loc.lat < 15 || loc.lat > 55) continue // 跳过海外点
    if (loc.lat < minLat) minLat = loc.lat
    if (loc.lat > maxLat) maxLat = loc.lat
    if (loc.lng < minLng) minLng = loc.lng
    if (loc.lng > maxLng) maxLng = loc.lng
  }
  // 兜底：至少有一个有效坐标
  const hasBounds = minLat < 90
  if (!hasBounds) { minLat = 20; maxLat = 45; minLng = 100; maxLng = 125 }

  // 加 padding 防止边缘城市被裁切
  const pad = 2
  minLat -= pad; maxLat += pad; minLng -= pad; maxLng += pad

  const latSpread = maxLat - minLat
  const lngSpread = maxLng - minLng
  const maxSpread = Math.max(latSpread, lngSpread)
  // zoom 反比：范围越小 zoom 越大，范围越大 zoom 越小
  const autoZoom = Math.max(1.8, Math.min(6, 10 - maxSpread * 0.45))
  const autoCenter: [number, number] = [(minLng + maxLng) / 2, (minLat + maxLat) / 2]

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
    animationDuration: tourEntryCount > 0 ? 0 : 800,
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
            const locYears = (loc?.paintings || []).map(p => Number(p.year)).filter(y => !isNaN(y)).sort()
            const yrStr = locYears.length > 0 ? `${locYears[0]}-${locYears[locYears.length - 1]}` : '未知'
            return `<strong>${meta?.name || params.name}</strong><br/>年份：${yrStr}<br/>画作：${count} 幅`
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
      zoom: autoZoom,
      center: autoCenter,
      scaleLimit: { min: 1.5, max: 8 },
      itemStyle: {
        areaColor: '#f6f3ed',
        borderColor: '#d8d1c4',
        borderWidth: 0.8,
      },
      emphasis: { disabled: true },
      label: { show: false },
      regions: visitedProvinces.value.map((name) => ({
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
    animationDelay: (idx: number) => idx * 180,
  })

  option.series.push({
    type: 'effectScatter',
    coordinateSystem: 'geo',
    data: [],
    symbol: 'diamond',
    symbolSize: 18,
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
  // replace mode (notMerge=true): full redraw — used for period switches and tour steps.
  // Tour steps also use replace because merge mode doesn't reliably update nested
  // lineStyle.opacity on existing data items, causing inconsistent fade levels.
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
      // 浅拷贝确保 Vue 响应式追踪嵌套 paintings 数组
      selectedLocation.value = { ...loc, paintings: [...loc.paintings] }
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

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && activePanel.value) {
    e.preventDefault()
    if (activePanel.value === 'period') closePeriodPanel()
    else closePanel()
  }
  if (e.key === ' ' && e.target === document.body) {
    e.preventDefault()
    toggleTour()
  }
}

onMounted(async () => {
  const name = (route.params.name as string) || '李鱓'
  await fetchData(name)
  await nextTick()
  initChart()
  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', handleKeydown)
})

// 侧边栏切换艺术家时重新加载
watch(() => route.params.name, async (newName) => {
  if (newName && typeof newName === 'string') {
    await fetchData(newName)
    await nextTick()
    updateChartData()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
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

/* ── Top Bar (breadcrumb) ── */
.map-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #e8e4d8;
  flex-shrink: 0;
  z-index: 10;
}
.topbar-back {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.92rem;
  color: #5e5d59;
  text-decoration: none;
  transition: color 0.2s;
  letter-spacing: 0.04em;
}
.topbar-back:hover {
  color: #c9a96e;
}
.topbar-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.82rem;
  color: #b8a990;
  letter-spacing: 0.08em;
}

.map-loading,
.map-error {
  padding: 48px 24px;
  max-width: 640px;
  margin: 0 auto;
}
.loading-text {
  font-family: 'Noto Serif SC', serif;
  font-size: 0.95rem;
  color: #b8a990;
  text-align: center;
  margin: 0 0 24px;
  letter-spacing: 0.06em;
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
  z-index: 1;
  animation: map-fade-in 0.8s ease-out;
}
@keyframes map-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
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
  position: fixed;
  bottom: 0; left: 0; right: 0; z-index: 10;
  display: flex;
  justify-content: center; align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: #f8f5f0;
  border-top: 1px solid #e8e4d8;
  flex-wrap: wrap;
  overflow-y: visible;
}
.period-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 5px 14px;
  border: 1px solid #d8d0c0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
  min-width: 70px;
  flex-shrink: 0;
}
.period-btn:hover { border-color: #c9a96e; }
.period-btn.active,
.period-btn-tour {
  border-color: #c45a3c !important;
  box-shadow: 0 0 0 2px rgba(196,90,60,0.25), 0 2px 8px rgba(0,0,0,0.1);
  animation: tour-pulse 2s ease-in-out infinite;
  background: #fef6f2;
}
@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(196,90,60,0.25), 0 2px 8px rgba(0,0,0,0.1); }
  50% { box-shadow: 0 0 0 4px rgba(196,90,60,0.15), 0 4px 14px rgba(0,0,0,0.15); }
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
.period-btn-emoji {
  font-size: 0.85rem;
  line-height: 1;
  margin-left: 2px;
}
.period-btn-year {
  font-size: 0.68rem;
  color: #b8a990;
}
.period-btn.active .period-btn-year,
.period-btn.period-btn-tour .period-btn-year { color: #8b7d6b; }

.period-btn.active .period-btn-label,
.period-btn.period-btn-tour .period-btn-label { color: #2c2416; }

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
.tour-progress {
  font-style: normal;
  font-size: 0.68rem;
  color: inherit;
  opacity: 0.65;
  margin-left: 2px;
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
  .period-bar { gap: 6px; padding: 6px 12px; flex-wrap: wrap; }
  .period-btn { padding: 5px 10px; min-width: 50px; border-radius: 8px; }
  .period-btn-label { font-size: 0.7rem; }
  .period-btn-year { font-size: 0.62rem; }
}
</style>
