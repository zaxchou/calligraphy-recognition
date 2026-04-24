/**
 * TubiAnalysis 常量与配置数据
 * 从 TubiAnalysis.vue 中抽离的纯配置/常量定义
 */

// 画家信息配置（出生年份用于年龄↔年份互算）
export const ARTISTS = {
  '李鱓': { birth: 1686, death: 1756, defaultYear: 1725 },
  '郑燮': { birth: 1693, death: 1766, defaultYear: 1730 },
  '金农': { birth: 1687, death: 1763, defaultYear: 1720 },
  '黄慎': { birth: 1687, death: 1770, defaultYear: 1720 },
  '边寿民': { birth: 1684, death: 1752, defaultYear: 1720 },
  '刘海勇': { birth: 1976, death: null, defaultYear: 2020 },
}

// 词云颜色（中国传统画色彩）
export const WORD_CLOUD_COLORS = [
  '#B23C3C', // 胭脂
  '#2C5A6E', // 花青
  '#E8B43C', // 藤黄
  '#8A5A3A', // 赭石
  '#2F5A3A'  // 墨绿
]

// 词云字体大小范围
export const WORD_CLOUD_FONT = {
  MIN: 18,
  MAX: 40
}

// 对比条显示常量
export const BAR_CONSTANTS = {
  MIN_VISIBLE_PERCENT: 2,   // 最小可见百分比（小于此值则显示为该值）
  MIN_WIDTH_GENERAL: 30,    // 一般对比条最小宽度百分比
  MIN_WIDTH_NARROW: 15      // 窄对比条最小宽度百分比（题跋比等）
}
