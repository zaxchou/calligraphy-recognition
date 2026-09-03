// 情绪 → 视觉参数映射工具
// 输入情绪效价 v ∈ [-1, 1]：-1 = 愤怒，0 = 平静，+1 = 快乐
// 数值保留 3 位小数精度（用于数据记录 / 模型输出）；视觉为连续映射。

export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

// 情绪文字标签（粗分档，仅用于展示；底层数据仍是连续值）
export function emotionLabel(v) {
  if (v <= -0.8) return "暴怒";
  if (v <= -0.5) return "愤怒";
  if (v <= -0.2) return "烦躁";
  if (v < 0.2) return "平静";
  if (v < 0.5) return "愉悦";
  if (v < 0.8) return "开心";
  return "快乐";
}

// 在 RGB 空间插值，避免色相旋转经过怪异的中间色（如愤怒→平静途中出现绿）
function lerpRgb(a, b, t) {
  return [
    Math.round(lerp(a[0], b[0], t)),
    Math.round(lerp(a[1], b[1], t)),
    Math.round(lerp(a[2], b[2], t)),
  ];
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0; const l = (max + min) / 2;
  const d = max - min;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return [h, s, l];
}

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  const to = (v) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return "#" + to(r) + to(g) + to(b);
}

const ANGER = [255, 59, 48];    // 红：愤怒
const NEUTRAL = [56, 132, 246]; // 冷蓝：平静
const HAPPY = [255, 209, 64];   // 暖金：快乐

// 由情绪值生成光带调色板（3 色，保持层次感）
export function emotionColors(v) {
  const val = clamp(v, -1, 1);
  const base = val < 0
    ? lerpRgb(ANGER, NEUTRAL, val + 1)
    : lerpRgb(NEUTRAL, HAPPY, val);
  const [h, s, l] = rgbToHsl(base[0], base[1], base[2]);
  return [
    hslToHex(h, Math.min(1, s * 1.1), Math.min(1, l * 1.15)),
    hslToHex(h, s, l),
    hslToHex((h + 18) % 360, s, Math.max(0, l * 0.82)),
  ];
}

// 玻璃球基础尺寸：随唤醒度 |v| 增大 —— 0=平稳最小，±1=愤怒与快乐两个极端同样最大
export function emotionGlassSize(v) {
  return lerp(0.82, 1.22, Math.abs(clamp(v, -1, 1)));
}

// 能量（激动 / 唤醒程度）随 |v| 增大，用来驱动速度、振幅、辉光
export function emotionEnergy(v) {
  return Math.abs(clamp(v, -1, 1));
}
