/**
 * TubiAnalysis 工具函数
 * 从 TubiAnalysis.vue 中抽离的纯逻辑/无副作用函数
 */
import { ARTISTS, BAR_CONSTANTS } from './constants'

// ==================== 年龄/年份计算 ====================

/**
 * 根据画家和年份计算年龄
 * @param {number|string} year 年份
 * @param {string} artistName 画家名称（默认'李鱓'）
 * @returns {number|null}
 */
export function calculateAge(year, artistName = '李鱓') {
  if (!year || isNaN(parseInt(year))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return parseInt(year) - artist.birth
}

/**
 * 根据画家和年龄计算年份
 * @param {number|string} age 年龄
 * @param {string} artistName 画家名称（默认'李鱓'）
 * @returns {number|null}
 */
export function calculateYear(age, artistName = '李鱓') {
  if (!age || isNaN(parseInt(age))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return artist.birth + parseInt(age)
}

/**
 * 获取画作显示年龄（优先计算值，其次从原始字段提取）
 * @param {Object} image 画作对象
 * @returns {number|null}
 */
export function getDisplayAge(image) {
  if (!image) return null
  const computed = calculateAge(image.year, image.artist)
  if (computed !== null && computed !== undefined && !isNaN(computed)) {
    if (computed >= -50 && computed <= 150) return computed
  }
  const raw = image.age ?? image.period
  if (raw === null || raw === undefined) return null
  const m = String(raw).match(/\d+/)
  if (!m) return null
  const parsed = parseInt(m[0])
  if (isNaN(parsed)) return null
  return parsed
}

// ==================== 格式化函数 ====================

/** 百分比格式化（带最小可见值保护） */
export function fmtPct(value) {
  const v = Number(value)
  if (!Number.isFinite(v) || v <= 0) return '0%'
  const clamped = Math.min(100, Math.max(v, 0))
  const out = clamped > 0 && clamped < BAR_CONSTANTS.MIN_VISIBLE_PERCENT
    ? BAR_CONSTANTS.MIN_VISIBLE_PERCENT
    : clamped
  return out.toFixed(1).replace(/\.0$/, '') + '%'
}

/** 计算百分比宽度字符串（用于 CSS style 绑定） */
export function percentWidth(value) {
  const v = Number(value)
  if (!Number.isFinite(v) || v <= 0) return '0%'
  const clamped = Math.min(100, Math.max(v, 0))
  const minVisible = BAR_CONSTANTS.MIN_VISIBLE_PERCENT
  const out = clamped > 0 && clamped < minVisible ? minVisible : clamped
  return out.toFixed(1).replace(/\.0$/, '') + '%'
}

/** 判断标签是否应显示在条内 */
export function shouldLabelInside(value) {
  const v = Number(value)
  if (!Number.isFinite(v)) return false
  return v >= 18
}

/** 计算条外标签的位置样式 */
export function outsideLabelStyle(value, side) {
  const width = percentWidth(value)
  const gap = 10
  if (side === 'left') {
    return { right: `calc(${width} + ${gap}px)` }
  }
  return { left: `calc(${width} + ${gap}px)` }
}

// ==================== 对比条宽度计算 ====================

/** 通用对比条宽度计算内部实现 */
function calcBarWidth(leftValue, rightValue, side, minWidth = BAR_CONSTANTS.MIN_WIDTH_GENERAL) {
  const left = parseFloat(leftValue) || 0
  const right = parseFloat(rightValue) || 0
  const max = Math.max(left, right, 1)

  if (side === 'left') {
    const percentage = (left / max) * 100
    return Math.max(percentage, minWidth) + '%'
  } else {
    const percentage = (right / max) * 100
    return Math.max(percentage, minWidth) + '%'
  }
}

/** 数量对比条宽度（minWidth=30） */
export function calculateBarWidth(leftValue, rightValue, side) {
  return calcBarWidth(leftValue, rightValue, side, BAR_CONSTANTS.MIN_WIDTH_GENERAL)
}

/** 百分比对比条宽度（minWidth=30） */
export function calculatePercentBarWidth(leftValue, rightValue, side) {
  return calcBarWidth(leftValue, rightValue, side, BAR_CONSTANTS.MIN_WIDTH_GENERAL)
}

/** 窄对比条宽度（minWidth=15，用于题画比等） */
export function calculateBarWidthPercent(leftValue, rightValue, side) {
  return calcBarWidth(leftValue, rightValue, side, BAR_CONSTANTS.MIN_WIDTH_NARROW)
}

/** 窄百分比对比条宽度（minWidth=15，用于题画比等） */
export function calculatePercentBarWidthPercent(leftValue, rightValue, side) {
  return calcBarWidth(leftValue, rightValue, side, BAR_CONSTANTS.MIN_WIDTH_NARROW)
}

// ==================== 日期格式化 ====================

/** 格式化日期字符串 */
export function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

// ==================== 图片处理 ====================

/** 处理图片加载错误 */
export function handleImageError(e) {
  e.target.src = ''
  e.target.style.display = 'none'
  const placeholder = e.target.nextElementSibling
  if (placeholder) {
    placeholder.style.display = 'flex'
  }
}
