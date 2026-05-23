/**
 * 翰墨行旅 — 通用城市坐标 & 地点构建
 * 从 art_chronology JSON 动态生成地图数据，不再硬编码李鱓。
 */
import CITY_COORDS from './cities.json'

export interface MapLocation {
  id: string
  name: string
  lat: number
  lng: number
  description: string
  paintingCount: number
  paintings: any[]
  markerRadius: number
}

export interface PeriodConfig {
  id: string
  label: string
  yearRange: [number, number]
  color: string
  order: number
}

const PERIOD_COLORS = ['#a08060', '#c96442', '#5b7a8c', '#8b6d4b', '#6b8b5a', '#8b5a8c', '#4a7a8c', '#c9a06c']

// ── 模糊解析城市名 → [lat, lng] ──
export function lookupCity(rawLocation: string): { name: string; lat: number; lng: number } | null {
  if (!rawLocation) return null
  const cleaned = rawLocation
    .replace(/（[^）]*）/g, '')
    .replace(/\([^)]*\)/g, '')
    .trim()

  // 先精确匹配
  const coords = (CITY_COORDS as Record<string, [number, number]>)
  if (coords[cleaned]) {
    return { name: cleaned, lat: coords[cleaned][0], lng: coords[cleaned][1] }
  }

  // 模糊匹配：尝试每个候选（按分隔符拆分）
  const parts = cleaned.split(/[、，,至到]/).map(p => p.trim()).filter(Boolean)
  for (const part of parts) {
    if (coords[part]) {
      return { name: part, lat: coords[part][0], lng: coords[part][1] }
    }
    // 尝试去掉省名前缀
    const short = part.replace(/^(江苏|浙江|山东|安徽|河南|河北|湖北|湖南|广东|广西|福建|江西|四川|云南|贵州|陕西|甘肃|辽宁|吉林|黑龙江|山西|海南|台湾|北京市?|上海市?|天津市?|重庆市?)/, '')
    if (short !== part && coords[short]) {
      return { name: short, lat: coords[short][0], lng: coords[short][1] }
    }
  }

  // 反向匹配：key 包含地点名
  for (const [key, val] of Object.entries(coords)) {
    if (key.includes(cleaned) || cleaned.includes(key)) {
      return { name: key, lat: val[0], lng: val[1] }
    }
    for (const part of parts) {
      if (key.includes(part) || part.includes(key)) {
        return { name: key, lat: val[0], lng: val[1] }
      }
    }
  }

  return null
}

// ── 从 art_chronology 构建地点列表 ──
export interface ChronologyEntry {
  year?: string | number
  event?: string
  location?: string
  description?: string
}

export function buildLocationsFromChronology(
  chronology: ChronologyEntry[],
  paintings: any[],
): MapLocation[] {
  if (!Array.isArray(chronology) || chronology.length === 0) return []

  // 按 location 分组
  const groups = new Map<string, { entries: ChronologyEntry[]; coord: { name: string; lat: number; lng: number } }>()
  for (const entry of chronology) {
    const raw = entry.location || ''
    if (!raw) continue
    const coord = lookupCity(raw)
    if (!coord) continue
    // 用坐标名作为分组 key
    const key = coord.name
    if (!groups.has(key)) {
      groups.set(key, { entries: [], coord })
    }
    groups.get(key)!.entries.push(entry)
  }

  // 构建 MapLocation 列表
  const locations: MapLocation[] = []
  for (const [key, group] of groups) {
    const years = group.entries.map(e => parseInt(String(e.year || ''))).filter(y => !isNaN(y))
    const descParts = group.entries
      .filter(e => e.event || e.description)
      .map(e => {
        const y = e.year ? `${e.year}年` : ''
        const ev = e.event || ''
        const d = e.description || ''
        return [y, ev, d].filter(Boolean).join(' ')
      })
    const description = descParts.join('；') || key

    // 匹配画作
    const matchedPaintings = paintings.filter(p => {
      const py = parseInt(String(p.year))
      if (isNaN(py)) return false
      return years.length === 0 || years.some(y => Math.abs(py - y) <= 30)
    })

    locations.push({
      id: key.replace(/\s/g, '_'),
      name: key,
      lat: group.coord.lat,
      lng: group.coord.lng,
      description,
      paintingCount: matchedPaintings.length,
      paintings: matchedPaintings,
      markerRadius: 0,
    })
  }

  // 按最早年份排序
  locations.sort((a, b) => {
    const aMin = Math.min(...(a.paintings.map(p => parseInt(String(p.year))).filter(n => !isNaN(n)) || [9999]))
    const bMin = Math.min(...(b.paintings.map(p => parseInt(String(p.year))).filter(n => !isNaN(n)) || [9999]))
    return aMin - bMin
  })

  return locations
}

// ── 从 art_chronology 自动划分时期 ──
export function buildPeriodsFromChronology(
  chronology: ChronologyEntry[],
  birthYear?: number | null,
  deathYear?: number | null,
): PeriodConfig[] {
  if (!Array.isArray(chronology) || chronology.length === 0) return []

  const years = chronology
    .map(e => parseInt(String(e.year || '')))
    .filter(y => !isNaN(y))
    .sort((a, b) => a - b)

  if (years.length < 2) return []

  const minYear = birthYear || years[0]
  const maxYear = deathYear || years[years.length - 1]
  const totalSpan = maxYear - minYear

  // 目标 3-6 个时期
  const targetPeriods = Math.min(6, Math.max(3, Math.floor(years.length / 5)))
  const periodSpan = Math.max(5, Math.ceil(totalSpan / targetPeriods))

  const periods: PeriodConfig[] = []
  for (let i = 0; i < targetPeriods; i++) {
    const start = minYear + i * periodSpan
    const end = i === targetPeriods - 1 ? maxYear : start + periodSpan - 1
    if (start > maxYear) break
    periods.push({
      id: `p${i}`,
      label: `${start}-${end}`,
      yearRange: [start, end],
      color: PERIOD_COLORS[i % PERIOD_COLORS.length],
      order: i,
    })
  }

  return periods
}
