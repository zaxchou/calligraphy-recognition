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
  chronologyLines: string[]
  periods: string[]
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

export const PERIOD_COLORS = ['#a08060', '#c96442', '#5b7a8c', '#8b6d4b', '#6b8b5a', '#8b5a8c', '#4a7a8c', '#c9a06c']
const PROVINCE_RE = /^(江苏|浙江|山东|安徽|河南|河北|湖北|湖南|广东|广西|福建|江西|四川|云南|贵州|陕西|甘肃|辽宁|吉林|黑龙江|山西|海南|台湾|北京市?|上海市?|天津市?|重庆市?)/

// ── 模糊解析城市名 → { name, lat, lng } ──
// 1) 精确匹配 2) 拆分子串 3) 去省名前缀 4) 反向匹配（最后手段）
export function lookupCity(rawLocation: string): { name: string; lat: number; lng: number } | null {
  if (!rawLocation) return null
  const coords = CITY_COORDS as Record<string, [number, number]>
  const cleaned = rawLocation.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim()
  if (!cleaned) return null

  // 1) 精确匹配
  if (coords[cleaned]) return { name: cleaned, lat: coords[cleaned][0], lng: coords[cleaned][1] }

  // 2) 按分隔符拆分，对每个部分尝试匹配
  const parts = cleaned.split(/[、，,至到]/).map(p => p.trim()).filter(Boolean)
  for (const part of parts) {
    // 2a) 直接匹配
    if (coords[part]) return { name: part, lat: coords[part][0], lng: coords[part][1] }
    // 2b) 去掉省名前缀
    let short = part
    for (const prefix of ['江苏', '浙江', '山东', '安徽', '河南', '河北', '湖北', '湖南', '广东', '广西', '福建', '江西', '四川', '云南', '贵州', '陕西', '甘肃', '辽宁', '吉林', '黑龙江', '山西', '海南', '台湾', '北京市', '上海市', '天津市', '重庆市', '北京', '上海', '天津', '重庆']) {
      if (short.startsWith(prefix)) {
        short = short.slice(prefix.length)
        if (coords[short]) return { name: short, lat: coords[short][0], lng: coords[short][1] }
        break
      }
    }
  }

  // 3) 反向匹配 — 只在以上都失败时使用
  for (const [key, val] of Object.entries(coords)) {
    if (cleaned.includes(key) || key.includes(cleaned)) {
      return { name: key, lat: val[0], lng: val[1] }
    }
    for (const part of parts) {
      if (part.includes(key) || key.includes(part)) {
        return { name: key, lat: val[0], lng: val[1] }
      }
    }
  }

  return null
}

// ── 从坐标生成唯一 key（用作分组和标记点 id）──
export function coordKey(lat: number, lng: number): string { return `${lat.toFixed(2)},${lng.toFixed(2)}` }

// ── 从括号注释中提取可能的现代地名 ──
// "宣府（今河北张家口）" → ["张家口"]
// "范县（今属河南）" → []
function extractParentheticalCities(raw: string): string[] {
  const m = raw.match(/[（(]今[^）)]*?([一-鿿]{2,6}(?:市|县|区|镇)?)[）)]/)
  if (m && m[1]) {
    const coords = CITY_COORDS as Record<string, [number, number]>
    const hint = m[1]
    // 直接匹配
    if (coords[hint]) return [hint]
    // 尝试去掉后缀
    const noSuffix = hint.replace(/[市县区镇]$/, '')
    if (noSuffix !== hint && coords[noSuffix]) return [noSuffix]
    // 反向匹配
    for (const key of Object.keys(coords)) {
      if (hint.includes(key) || key.includes(hint)) return [key]
    }
  }
  return []
}

// ── 查找位置中的所有匹配城市（用于复合地点如"绍兴、宁波"）──
export function lookupAllCities(rawLocation: string): { name: string; lat: number; lng: number }[] {
  if (!rawLocation) return []
  const coords = CITY_COORDS as Record<string, [number, number]>
  const results: { name: string; lat: number; lng: number }[] = []
  const seen = new Set<string>()

  function add(result: { name: string; lat: number; lng: number } | null) {
    if (result && !seen.has(result.name)) {
      seen.add(result.name)
      results.push(result)
    }
  }

  // 先尝试从括号中提取现代地名
  const hints = extractParentheticalCities(rawLocation)
  for (const hint of hints) {
    if (coords[hint]) add({ name: hint, lat: coords[hint][0], lng: coords[hint][1] })
  }

  // 清洗括号后匹配
  const cleaned = rawLocation.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '').trim()
  if (!cleaned) return results

  // 1) 精确匹配
  if (coords[cleaned]) { add({ name: cleaned, lat: coords[cleaned][0], lng: coords[cleaned][1] }); return results }

  // 2) 按分隔符拆分，对每个部分尝试匹配（ALL parts, not just first）
  const parts = cleaned.split(/[、，,至到]/).map(p => p.trim()).filter(Boolean)
  for (const part of parts) {
    // 2a) 直接匹配
    if (coords[part]) { add({ name: part, lat: coords[part][0], lng: coords[part][1] }); continue }
    // 2b) 去掉省名前缀
    let short = part
    for (const prefix of ['江苏', '浙江', '山东', '安徽', '河南', '河北', '湖北', '湖南', '广东', '广西', '福建', '江西', '四川', '云南', '贵州', '陕西', '甘肃', '辽宁', '吉林', '黑龙江', '山西', '海南', '台湾', '北京市', '上海市', '天津市', '重庆市', '北京', '上海', '天津', '重庆']) {
      if (short.startsWith(prefix)) {
        short = short.slice(prefix.length)
        if (coords[short]) { add({ name: short, lat: coords[short][0], lng: coords[short][1] }) }
        break
      }
    }
    // 2c) 反向匹配
    if (!seen.has(part)) {
      for (const [key, val] of Object.entries(coords)) {
        if (part.includes(key) || key.includes(part)) {
          add({ name: key, lat: val[0], lng: val[1] })
          break
        }
      }
    }
  }

  // 3) 全局反向匹配（兜底：整个 cleaned 字符串）
  if (results.length === 0) {
    for (const [key, val] of Object.entries(coords)) {
      if (cleaned.includes(key) || key.includes(cleaned)) {
        add({ name: key, lat: val[0], lng: val[1] })
        break
      }
    }
    // 对每个 part 也做一次
    if (results.length === 0) {
      for (const part of parts) {
        for (const [key, val] of Object.entries(coords)) {
          if (part.includes(key) || key.includes(part)) {
            add({ name: key, lat: val[0], lng: val[1] })
            break
          }
        }
        if (results.length > 0) break
      }
    }
  }

  return results
}

export interface ChronologyEntry {
  year?: string | number; event?: string; location?: string; description?: string
}

// ── 格式化描述文本（排版优化）──
function formatDescription(entries: ChronologyEntry[], cityName: string): { text: string; lines: string[] } {
  const lines = entries
    .filter(e => e.event || e.description)
    .map(e => {
      const y = e.year ? `${e.year}年` : ''
      const ev = e.event || ''
      const desc = e.description || ''
      const main = [y, ev].filter(Boolean).join(' ')
      return desc ? `${main}：${desc}` : main
    })
  // 去重（同年同事件只保留一次）
  const seen = new Set<string>()
  const unique = lines.filter(l => { const k = l.slice(0, 20); if (seen.has(k)) return false; seen.add(k); return true })
  return {
    text: unique.length > 0 ? unique.join('\n') : `${cityName}（暂无详细记录）`,
    lines: unique,
  }
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
    const matches = lookupAllCities(raw)
    for (const match of matches) {
      const key = coordKey(match.lat, match.lng)
      if (!groups.has(key)) {
        groups.set(key, { entries: [], name: match.name, lat: match.lat, lng: match.lng })
      }
      groups.get(key)!.entries.push(entry)
    }
  }

  const locations: MapLocation[] = []
  for (const [, group] of groups) {
    const years = group.entries.map(e => parseInt(String(e.year || ''))).filter(y => !isNaN(y))
    const { text: description, lines: chronologyLines } = formatDescription(group.entries, group.name)

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
      chronologyLines,
      periods: [],
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
  const usedLabels = new Set<string>()
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
    let label = generatePeriodLabel(periodEntries, start, end, i, targetPeriods)

    // 相邻时期标签去重：次优语义标签 → 生命阶段序列 → 追加年份兜底
    if (usedLabels.has(label)) {
      const alt = scorePeriodLabels(events).find(r => !usedLabels.has(r.label))
      if (alt) {
        label = alt.label
      } else {
        const stage = lifeStageLabel(i, targetPeriods, periodEntries, start, end)
        label = usedLabels.has(stage) ? `${stage}（${start}-${end}）` : stage
      }
    }
    usedLabels.add(label)

    periods.push({ id: `p${i}`, label, yearRange: [start, end], color: PERIOD_COLORS[i % PERIOD_COLORS.length], order: i })
  }

  return periods
}

// ── 生成语义时期标签 ──
// 词级匹配（单字类会把"学院/教师/问世"这类词误命中，是当代艺术家标签失真的根因）
const PERIOD_PATTERNS: [string, RegExp][] = [
  ['出生与早年', /(出生|诞生|出生于|幼年|童年|启蒙)/],
  ['求学', /(考入|考取|保送|入学|入读|就读|求学|留学|进修|攻读|毕业)/],
  ['执教治学', /(任教|执教|受聘|获聘|晋升教授|晋升副教授|教授|副教授|导师|教学|讲学|长江学者|学者|副主任|处长|秘书长|副院长|院长)/],
  ['科举仕途', /(中举|进士|科举|及第|状元|举人|秀才|仕途|官宦|会试|乡试)/],
  ['宫廷供奉', /(宫廷|内廷|供奉|南书房行走|待诏)/],
  ['为官', /(知县|县令|知州|为官|赴任|上任|擢)/],
  ['游历', /(游历|云游|壮游|漫游|旅居|游学|客居)/],
  ['卖画', /(卖画|鬻画|鬻书|卖字|润格)/],
  ['罢官归隐', /(罢官|归隐|隐居|退隐)/],
  ['著述展览', /(出版|专著|作品集|个展|发表|获奖|论文|教材)/],
  ['晚年', /(晚年|暮年|晚景|耄耋)/],
]

function scorePeriodLabels(events: string[]): { label: string; score: number }[] {
  // 按事件计数：一条事件命中某标签只计 1 分，避免"出版首部专著"同时命中
  // 出版+专著 被算成 2 分的重复计分
  return PERIOD_PATTERNS
    .map(([label, re]) => ({
      label,
      score: events.filter(ev => re.test(ev)).length,
    }))
    .filter(r => r.score > 0)
    .sort((a, b) => b.score - a.score)
}

function lifeStageLabel(index: number, total: number, periodEntries: ChronologyEntry[], start: number, end: number): string {
  const hasBirth = periodEntries.some(e => /(出生|诞生)/.test((e.event || '') + (e.description || '')))
  if (total >= 3) {
    if (index === 0) return hasBirth ? '出生与早年' : '早年'
    if (index === total - 1) return '晚年'
    const middleLabels = ['青壮年', '壮年', '盛年', '中年', '暮年']
    const labelIdx = index - 1 // 第一个中间时期 → 0
    if (labelIdx >= middleLabels.length) return `盛年（${start}-${end}）`
    return middleLabels[labelIdx]
  }
  return `${start}-${end}`
}

function generatePeriodLabel(periodEntries: ChronologyEntry[], start: number, end: number, index: number, total: number): string {
  const events = periodEntries.map(e => e.event || '').filter(Boolean)

  // 去世判定：词级匹配（裸字符类会把"问世/世纪"误判为去世），且只看当前时期的条目
  // ——中期提到师长去世不再把最后一个时期误标为"晚年"
  const hasDeath = periodEntries.some(e =>
    /(逝世|去世|病故|谢世|驾崩|卒于|病卒|暴卒|殁)/.test((e.event || '') + (e.description || '')))

  // 最后一个时期如果包含去世事件，标记为"晚年"
  if (index === total - 1 && hasDeath) return '晚年'

  const ranked = scorePeriodLabels(events)
  // 词级模式精确度高，单事件命中即可命名（古代画家一窗口常只有一两个关键事件）
  if (ranked.length) return ranked[0].label

  return lifeStageLabel(index, total, periodEntries, start, end)
}
