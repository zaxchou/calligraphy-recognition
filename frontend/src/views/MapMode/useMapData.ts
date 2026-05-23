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

      // 构建地点和时期
      const locs = buildLocationsFromChronology(chron, paintings)
      const max = Math.max(...locs.map(l => l.paintingCount), 1)
      for (const loc of locs) {
        loc.markerRadius = computeRadius(loc.paintingCount, max)
      }
      locationsWithPaintings.value = locs

      periods.value = buildPeriodsFromChronology(chron, artistBirthYear.value, artistDeathYear.value)
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
