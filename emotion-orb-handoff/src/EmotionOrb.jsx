import Strands from "./Strands";
import { clamp, emotionColors, emotionGlassSize, emotionEnergy } from "./emotion-utils";

// 把情绪效价 value ∈ [-1, 1] 映射成玻璃光球的视觉参数。
// - 颜色：效价(valence) —— 愤怒(红) → 平静(蓝) → 快乐(金)
// - 大小 / 速度 / 振幅 / 辉光：唤醒度(arousal) = |value|
//   0 = 平稳（最小最静），±1 = 愤怒与快乐两个极端同样最大最躁
export default function EmotionOrb({ value = 0, ...rest }) {
  const v = clamp(value, -1, 1);
  const e = emotionEnergy(v);  // 0..1 唤醒度：越极端越大越躁

  return (
    <Strands
      colors={emotionColors(v)}
      count={4}
      speed={0.4 + 0.6 * e}
      amplitude={0.7 + 0.7 * e}
      thickness={0.85}
      glow={1.9 + 1.2 * e}
      taper={3}
      spread={1}
      intensity={0.5 + 0.35 * e}
      saturation={1.5}
      scale={1.4}
      glass
      refraction={1.1}
      dispersion={1.25}
      glassSize={emotionGlassSize(v)}
      {...rest}
    />
  );
}
