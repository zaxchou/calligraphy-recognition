import { ref, computed, type Ref } from 'vue'
import { tubiApi } from '@/api'
import {
  getMergedLocations,
  type MergedLocation,
} from './locations'

export interface Painting {
  id: number | string
  image_id?: string
  title: string
  year: number
  period?: string
  period_phase?: string
  artist: string
}

export interface LocationWithPaintings extends MergedLocation {
  paintingCount: number
  paintings: Painting[]
  markerRadius: number
}

const MIN_RADIUS = 0.08
const MAX_RADIUS = 0.25

function computeRadius(count: number, maxCount: number): number {
  if (maxCount === 0) return MIN_RADIUS
  const ratio = count / maxCount
  return MIN_RADIUS + ratio * (MAX_RADIUS - MIN_RADIUS)
}

export function useMapData() {
  const loading: Ref<boolean> = ref(true)
  const error: Ref<string | null> = ref(null)
  const allPaintings: Ref<Painting[]> = ref([])
  const locationsWithPaintings: Ref<LocationWithPaintings[]> = ref([])
  const selectedPeriod: Ref<string | null> = ref(null)

  const maxCount = computed(() =>
    Math.max(...locationsWithPaintings.value.map((l) => l.paintingCount), 1)
  )

  const filteredLocations = computed(() => {
    if (!selectedPeriod.value) return locationsWithPaintings.value
    return locationsWithPaintings.value.filter((l) =>
      l.periods.includes(selectedPeriod.value!)
    )
  })

  /** Check if a year falls within any of the given year ranges */
  function yearInRanges(year: number, ranges: [number, number][]): boolean {
    return ranges.some(([start, end]) => year >= start && year <= end)
  }

  async function fetchData() {
    loading.value = true
    error.value = null

    try {
      const res = await tubiApi.getAllResults(0, 500, '李鱓', 'year', 'asc')
      const paintings: Painting[] = (res?.data || []).map((item: any) => ({
        id: item.id,
        image_id: item.image_id,
        title: item.title || '无题',
        year: item.year,
        period: item.period,
        period_phase: item.period_phase,
        artist: item.artist,
      }))

      allPaintings.value = paintings

      // Group paintings by location
      const merged = getMergedLocations()
      const result: LocationWithPaintings[] = merged.map((loc) => {
        const matched = paintings.filter((p) => yearInRanges(p.year, loc.yearRanges))
        return {
          ...loc,
          paintingCount: matched.length,
          paintings: matched,
          markerRadius: 0, // computed after we know maxCount
        }
      })

      // Compute marker radii
      const max = Math.max(...result.map((l) => l.paintingCount), 1)
      for (const loc of result) {
        loc.markerRadius = computeRadius(loc.paintingCount, max)
      }

      locationsWithPaintings.value = result
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
    allPaintings,
    locationsWithPaintings,
    filteredLocations,
    selectedPeriod,
    maxCount,
    selectPeriod,
    getPaintingsForLocation,
    fetchData,
  }
}
