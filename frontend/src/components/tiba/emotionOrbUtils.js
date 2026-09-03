// 情绪 → 视觉参数映射（移植自 emotion-orb-handoff/src/emotion-utils.js）
// 输入情绪效价 v ∈ [-1, 1]：-1 = 愤怒，0 = 平静，+1 = 快乐
// 设计约定（勿回退）：大小表示「情绪强烈程度」而非「开心程度」，
// 愤怒与快乐在大小上对称（±1 同为最大），0 最小最静。

export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

export function lerp(a, b, t) {
  return a + (b - a) * t
}

function lerpRgb(a, b, t) {
  return [
    Math.round(lerp(a[0], b[0], t)),
    Math.round(lerp(a[1], b[1], t)),
    Math.round(lerp(a[2], b[2], t)),
  ]
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h = 0, s = 0
  const l = (max + min) / 2
  const d = max - min
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h *= 60
  }
  return [h, s, l]
}

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let r = 0, g = 0, b = 0
  if (h < 60) { r = c; g = x } else if (h < 120) { r = x; g = c } else if (h < 180) { g = c; b = x } else if (h < 240) { g = x; b = c } else if (h < 300) { r = x; b = c } else { r = c; b = x }
  const to = (v) => Math.round((v + m) * 255).toString(16).padStart(2, '0')
  return '#' + to(r) + to(g) + to(b)
}

const ANGER = [255, 59, 48]     // 红：愤怒
const NEUTRAL = [56, 132, 246]  // 冷蓝：平静
const HAPPY = [255, 209, 64]    // 暖金：快乐

// 由情绪值生成光带调色板（3 色，RGB 空间插值，避免色相旋转经过怪异中间色）
export function emotionColors(v) {
  const val = clamp(v, -1, 1)
  const base = val < 0 ? lerpRgb(ANGER, NEUTRAL, val + 1) : lerpRgb(NEUTRAL, HAPPY, val)
  const [h, s, l] = rgbToHsl(base[0], base[1], base[2])
  return [
    hslToHex(h, Math.min(1, s * 1.1), Math.min(1, l * 1.15)),
    hslToHex(h, s, l),
    hslToHex((h + 18) % 360, s, Math.max(0, l * 0.82)),
  ]
}

// 玻璃球尺寸 v2：0 值系数 0.58（球径约 43% 容器），±1 系数 1.20（约 92%），
// 反差约 2.2×；半径上限 0.375×1.20×1.025(脉动) ≈ 0.46（短边单位），不会溢出容器被裁切
export function emotionGlassSize(v) {
  return lerp(0.58, 1.2, Math.abs(clamp(v, -1, 1)))
}

// 能量（激动/唤醒程度）随 |v| 增大，驱动速度、振幅、辉光
export function emotionEnergy(v) {
  return Math.abs(clamp(v, -1, 1))
}
