import { ref, computed, type Ref } from 'vue'
import { tubiApi } from '@/api'
import { artistsApi } from '@/api/artists'
import {
  buildLocationsFromChronology,
  buildPeriodsFromChronology,
  type MapLocation,
  type PeriodConfig,
  type ChronologyEntry,
} from './locations'

export interface Painting {
  id: number | string
  image_id?: string
  title: string
  year: number
  period?: string
  period_phase?: string
  artist: string
  thumbnail_url?: string
}

const MIN_RADIUS = 0.08
const MAX_RADIUS = 0.25
const PERIOD_COLORS = ['#a08060', '#c96442', '#5b7a8c', '#8b6d4b', '#6b8b5a', '#8b5a8c', '#4a7a8c', '#c9a06c']

function computeRadius(count: number, maxCount: number): number {
  if (maxCount === 0) return MIN_RADIUS
  const ratio = count / maxCount
  return MIN_RADIUS + ratio * (MAX_RADIUS - MIN_RADIUS)
}

function parseJsonField(raw: any): any[] {
  if (!raw) return []
  if (Array.isArray(raw)) return raw
  try { return JSON.parse(raw) } catch { return [] }
}

// ── 从 AI travel_notes JSON 映射为 MapLocation[] ──
function mapTravelNotesToLocations(
  travelNotes: any,
  paintings: Painting[],
): MapLocation[] {
  const periods: any[] = travelNotes.periods || []
  const locations: any[] = travelNotes.locations || []

  // 构建 painting image_id → Painting 的快速查找
  const paintingMap = new Map<string, Painting>()
  for (const p of paintings) {
    const key = p.image_id || String(p.id)
    paintingMap.set(key, p)
  }

  return locations.map((loc: any) => {
    const paintingIds: string[] = loc.painting_ids || []
    const matchedPaintings = paintingIds
      .map((pid: string) => paintingMap.get(pid))
      .filter(Boolean) as Painting[]

    // 构建 chronologyLines 从 events
    const events: any[] = loc.events || []
    const chronologyLines = events.map((e: any) => {
      const y = e.year ? `${e.year}年` : ''
      const ev = e.event || ''
      const desc = e.description || ''
      const main = [y, ev].filter(Boolean).join(' ')
      return desc ? `${main}：${desc}` : main
    })

    // description = summary（AI生成的城市概述）
    const description = loc.summary || `${loc.name}（暂无详细记录）`

    return {
      id: `${(loc.lat || 0).toFixed(2)},${(loc.lng || 0).toFixed(2)}`,
      name: loc.name || '未知',
      lat: loc.lat || 0,
      lng: loc.lng || 0,
      description,
      chronologyLines: chronologyLines.length > 0 ? chronologyLines : [description],
      paintingCount: matchedPaintings.length,
      paintings: matchedPaintings,
      markerRadius: 0,
    } as MapLocation
  })
}

// ── 从 AI travel_notes JSON 映射为 PeriodConfig[] ──
function mapTravelNotesToPeriods(travelNotes: any): PeriodConfig[] {
  const periods: any[] = travelNotes.periods || []
  return periods.map((p: any, i: number) => ({
    id: p.id || `p${i}`,
    label: p.label || `时期${i + 1}`,
    yearRange: (p.year_range || [0, 0]) as [number, number],
    color: PERIOD_COLORS[i % PERIOD_COLORS.length],
    order: p.order ?? i,
  }))
}

export function useMapData() {
  const loading: Ref<boolean> = ref(true)
  const error: Ref<string | null> = ref(null)
  const artistName: Ref<string> = ref('')
  const artistBirthYear: Ref<number | null> = ref(null)
  const artistDeathYear: Ref<number | null> = ref(null)
  const chronology: Ref<ChronologyEntry[]> = ref([])
  const allPaintings: Ref<Painting[]> = ref([])
  const locationsWithPaintings: Ref<MapLocation[]> = ref([])
  const periods: Ref<PeriodConfig[]> = ref([])
  const selectedPeriod: Ref<string | null> = ref(null)

  const maxCount = computed(() =>
    Math.max(...locationsWithPaintings.value.map((l) => l.paintingCount), 1)
  )

  const filteredLocations = computed(() => {
    if (!selectedPeriod.value) return locationsWithPaintings.value
    // 按时期筛选：画作年份落入时期范围
    return locationsWithPaintings.value.filter(loc => {
      const hasPaintingInPeriod = loc.paintings.some(p => {
        const py = parseInt(String(p.year))
        if (isNaN(py)) return false
        const period = periods.value.find(pp => pp.id === selectedPeriod.value)
        if (!period) return true
        return py >= period.yearRange[0] && py <= period.yearRange[1]
      })
      return hasPaintingInPeriod
    }).map(loc => ({
      ...loc,
      paintings: loc.paintings.filter(p => {
        const py = parseInt(String(p.year))
        if (isNaN(py)) return false
        const period = periods.value.find(pp => pp.id === selectedPeriod.value)
        if (!period) return true
        return py >= period.yearRange[0] && py <= period.yearRange[1]
      }),
    }))
  })

  async function fetchData(name: string) {
    loading.value = true
    error.value = null
    artistName.value = name

    try {
      // 并行获取艺术家元数据 + 作品
      const [artistRes, paintingsRes] = await Promise.all([
        artistsApi.getByName(name).catch(() => null),
        tubiApi.getAllResults(0, 2000, name, null, 'year', 'asc').catch(() => null),
      ])

      // 解析年谱
      const rawChron = artistRes?.artist?.art_chronology || artistRes?.art_chronology
      const chron = parseJsonField(rawChron) as ChronologyEntry[]
      chronology.value = chron
      artistBirthYear.value = artistRes?.artist?.birth_year || null
      artistDeathYear.value = artistRes?.artist?.death_year || null

      // 解析作品
      const paintings: Painting[] = ((paintingsRes as any)?.results || (paintingsRes as any)?.data || []).map((item: any) => ({
        id: item.id || item.image_id,
        image_id: item.image_id || item.id,
        title: item.title || '无题',
        year: item.year,
        period: item.period,
        period_phase: item.period_phase,
        artist: item.artist,
        thumbnail_url: item.thumbnail_url || item.url || undefined,
      }))
      allPaintings.value = paintings

      // 构建地点和时期（优先使用 AI travel_notes）
      const travelNotesRaw = artistRes?.artist?.travel_notes || artistRes?.travel_notes
      let travelNotes: any = null
      if (travelNotesRaw) {
        try {
          travelNotes = typeof travelNotesRaw === 'string' ? JSON.parse(travelNotesRaw) : travelNotesRaw
        } catch { /* ignore parse error */ }
      }

      if (travelNotes && travelNotes.locations && travelNotes.locations.length > 0) {
        // 使用 AI 生成的数据
        periods.value = mapTravelNotesToPeriods(travelNotes)
        const locs = mapTravelNotesToLocations(travelNotes, paintings)
        const max = Math.max(...locs.map(l => l.paintingCount), 1)
        for (const loc of locs) {
          loc.markerRadius = computeRadius(loc.paintingCount, max)
        }
        locationsWithPaintings.value = locs
      } else {
        // 回退：自动派生
        const locs = buildLocationsFromChronology(chron, paintings)
        const max = Math.max(...locs.map(l => l.paintingCount), 1)
        for (const loc of locs) {
          loc.markerRadius = computeRadius(loc.paintingCount, max)
        }
        locationsWithPaintings.value = locs
        periods.value = buildPeriodsFromChronology(chron, artistBirthYear.value, artistDeathYear.value)
      }
    } catch (e: any) {
      error.value = e?.message || '数据加载失败'
      console.error('MapMode fetch error:', e)
    } finally {
      loading.value = false
    }
  }

  function selectPeriod(periodId: string | null) {
    selectedPeriod.value = selectedPeriod.value === periodId ? null : periodId
  }

  function getPaintingsForLocation(locId: string): Painting[] {
    const loc = locationsWithPaintings.value.find((l) => l.id === locId)
    return loc ? loc.paintings : []
  }

  return {
    loading,
    error,
    artistName,
    artistBirthYear,
    artistDeathYear,
    chronology,
    allPaintings,
    locationsWithPaintings,
    periods,
    filteredLocations,
    selectedPeriod,
    maxCount,
    selectPeriod,
    getPaintingsForLocation,
    fetchData,
  }
}
