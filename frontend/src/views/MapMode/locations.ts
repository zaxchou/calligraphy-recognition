/**
 * 翰墨行旅 — 通用城市坐标 & 地点构建
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
const PROVINCE_RE = /^(江苏|浙江|山东|安徽|河南|河北|湖北|湖南|广东|广西|福建|江西|四川|云南|贵州|陕西|甘肃|辽宁|吉林|黑龙江|山西|海南|台湾|北京市?|上海市?|天津市?|重庆市?)/

// ── 模糊解析城市名 → { name, lat, lng } ──
// 返回值同名城市返回相同 name（选最短的匹配 key）
export function lookupCity(rawLocation: string): { name: string; lat: number; lng: number } | null {
  if (!rawLocation) return null
  const coords = CITY_COORDS as Record<string, [number, number]>
  const cleaned = rawLocation.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim()
  if (!cleaned) return null

  // 精确匹配
  if (coords[cleaned]) return { name: cleaned, lat: coords[cleaned][0], lng: coords[cleaned][1] }

  // 拆分子串匹配（分隔符：、，至 和省份前缀）
  const parts = cleaned.split(/[、，,至到]/).map(p => p.trim()).filter(Boolean)
  for (const part of parts) {
    if (coords[part]) return { name: part, lat: coords[part][0], lng: coords[part][1] }
    const short = part.replace(PROVINCE_RE, '')
    if (short !== part && coords[short]) return { name: short, lat: coords[short][0], lng: coords[short][1] }
  }

  // 反向匹配（包含关系）
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

// ── 从坐标生成唯一 key（用作分组和标记点 id）──
function coordKey(lat: number, lng: number): string { return `${lat.toFixed(2)},${lng.toFixed(2)}` }

export interface ChronologyEntry {
  year?: string | number; event?: string; location?: string; description?: string
}

// ── 从 art_chronology 构建地点列表 ──
export function buildLocationsFromChronology(
  chronology: ChronologyEntry[],
  paintings: any[],
): MapLocation[] {
  if (!Array.isArray(chronology) || chronology.length === 0) return []

  // 用坐标 key 分组（同坐标 = 同城市）
  const groups = new Map<string, { entries: ChronologyEntry[]; name: string; lat: number; lng: number }>()
  for (const entry of chronology) {
    const raw = entry.location || ''
    if (!raw) continue
    const match = lookupCity(raw)
    if (!match) continue
    const key = coordKey(match.lat, match.lng)
    if (!groups.has(key)) {
      groups.set(key, { entries: [], name: match.name, lat: match.lat, lng: match.lng })
    }
    groups.get(key)!.entries.push(entry)
  }

  const locations: MapLocation[] = []
  for (const [, group] of groups) {
    const years = group.entries.map(e => parseInt(String(e.year || ''))).filter(y => !isNaN(y))
    const descParts = group.entries
      .filter(e => e.event || e.description)
      .map(e => {
        const y = e.year ? `${e.year}年` : ''
        return [y, e.event, e.description].filter(Boolean).join(' ')
      })
    const description = descParts.join('；') || group.name

    // 画作匹配（缩小到 ±15年 窗口）
    const matchedPaintings = paintings.filter(p => {
      const py = parseInt(String(p.year))
      if (isNaN(py)) return false
      return years.length === 0 || years.some(y => Math.abs(py - y) <= 15)
    })

    locations.push({
      id: coordKey(group.lat, group.lng),
      name: group.name,
      lat: group.lat,
      lng: group.lng,
      description,
      paintingCount: matchedPaintings.length,
      paintings: matchedPaintings,
      markerRadius: 0,
    })
  }

  // 按最早画作年份排序
  locations.sort((a, b) => {
    const aYears = a.paintings.map(p => parseInt(String(p.year))).filter(n => !isNaN(n))
    const bYears = b.paintings.map(p => parseInt(String(p.year))).filter(n => !isNaN(n))
    const aMin = aYears.length > 0 ? Math.min(...aYears) : 9999
    const bMin = bYears.length > 0 ? Math.min(...bYears) : 9999
    return aMin - bMin
  })

  return locations
}

// ── 从 art_chronology 自动划分时期（语义标签）──
export function buildPeriodsFromChronology(
  chronology: ChronologyEntry[],
  birthYear?: number | null,
  deathYear?: number | null,
): PeriodConfig[] {
  if (!Array.isArray(chronology) || chronology.length === 0) return []

  const years = chronology.map(e => parseInt(String(e.year || ''))).filter(y => !isNaN(y)).sort((a, b) => a - b)
  if (years.length < 2) return []

  const minYear = birthYear || years[0]
  const maxYear = deathYear || years[years.length - 1]
  const totalSpan = maxYear - minYear
  if (totalSpan < 2) return []

  // 目标 3-5 个时期，每个至少覆盖 5 年
  const targetPeriods = Math.min(5, Math.max(3, Math.floor(years.length / 8)))
  const periodSpan = Math.max(5, Math.ceil(totalSpan / targetPeriods))

  const periods: PeriodConfig[] = []
  for (let i = 0; i < targetPeriods; i++) {
    const start = minYear + i * periodSpan
    const end = i === targetPeriods - 1 ? maxYear : start + periodSpan - 1
    if (start > maxYear) break

    // 从该时期的 chronology 条目中提取最有代表性的 event 作为标签
    const periodEntries = chronology.filter(e => {
      const y = parseInt(String(e.year || '')); if (isNaN(y)) return false
      return y >= start && y <= end
    })
    const events = periodEntries.map(e => e.event || '').filter(Boolean)
    const label = generatePeriodLabel(events, start, end, i, targetPeriods)

    periods.push({ id: `p${i}`, label, yearRange: [start, end], color: PERIOD_COLORS[i % PERIOD_COLORS.length], order: i })
  }

  return periods
}

// ── 生成语义时期标签 ──
const LIFE_PHASE_TERMS = ['出生', '早年', '学', '师', '中举', '进士', '仕', '宫廷', '官', '知县', '游', '卖画', '寓', '隐', '归', '老', '卒', '殁', '定居', '讲学']

function generatePeriodLabel(events: string[], start: number, end: number, index: number, total: number): string {
  // 取出现频次最高的事件关键词
  const hits: Record<string, number> = {}
  for (const ev of events) {
    for (const term of LIFE_PHASE_TERMS) {
      if (ev.includes(term)) hits[term] = (hits[term] || 0) + 1
    }
  }
  const topTerms = Object.entries(hits).sort((a, b) => b[1] - a[1]).slice(0, 2).map(e => e[0])
  if (topTerms.length > 0) return topTerms.join('·')

  // 回退：用生命周期位置
  if (total >= 3) {
    if (index === 0) return '早年'
    if (index === total - 1) return '晚年'
    return `盛年${index > 1 ? '后期' : ''}`
  }
  return `${start}-${end}`
}
