# 情绪光球 EmotionOrb — 交接文档 / Handoff

> 本文档自包含，不依赖任何外部会话记忆。新的 agent / 项目拿到本目录 + 此文档即可完整接手。

## 1. 这是什么
- 一个基于 **React + OGL（WebGL 着色器）** 的实时「玻璃光球」组件，用于把**情绪分数**可视化成有生命感的光球。
- **它不是视频**，是逐帧实时渲染的着色器。可直接用情绪模型的连续输出（如一个 -1~+1 的分数）每帧驱动，颜色/大小/能量都是连续插值，过渡顺滑。
- 基础组件 `Strands.jsx` 源自开源项目 `github.com/opc8838-hub/glass-light-orb`（MIT），本仓库在其之上加了「情绪映射层」。

## 2. 依赖
| 依赖 | 版本 | 说明 |
|------|------|------|
| `ogl` | ^1.0.11 | **唯一运行时依赖**（轻量 WebGL 封装）。`Strands.jsx` 依赖它 |
| `react` / `react-dom` | ^19 | 宿主环境 |
| 浏览器 | 需支持 WebGL | Canvas 填满父容器，**父容器必须显式给定宽高** |

> `Strands.jsx` 只依赖 `ogl`；`EmotionOrb.jsx` 与 `emotion-utils.js` 是纯 JS，可单独复用。

## 3. 文件结构（只搬这些即可）
```
src/
  Strands.jsx        底层玻璃光球着色器组件（原样复刻，勿改除非懂 GLSL）
  Strands.css        容器样式
  emotion-utils.js   情绪 → 视觉参数映射（颜色/大小/能量），纯函数，可独立复用
  EmotionOrb.jsx     对外封装：传入 value 即可，推荐给业务用的入口
  main.jsx           演示页（滑块 -1.000~+1.000）
standalone.html              免构建单文件版（CDN 加载 OGL），双击即开，用于快速预览
standalone-themes.html       同上，额外带深/浅背景切换，用于评估浅色主题表现
```
搬到目标项目时：复制 `src/` 整目录即可；`standalone*.html` 仅作预览/演示，可不要。

## 4. 用法
```jsx
import EmotionOrb from "./EmotionOrb";

export default function Demo() {
  return (
    <div style={{ width: 360, height: 360 }}>
      <EmotionOrb value={0.42} />   {/* value ∈ [-1, 1]，保留 3 位小数 */}
    </div>
  );
}
```
- `value`：情绪效价，范围 `[-1, 1]`。建议数据层保留 3 位小数（用于记录/喂模型/差分），视觉为连续插值，人眼无法分辨 0.001 级差异。
- 其余 `Strands` 的 props（`count/speed/refraction/...`）可通过 `...rest` 透传覆盖。

## 5. 情绪映射设计（重要，改之前先读）
采用心理学常用的 **效价-唤醒度（valence-arousal）** 二维模型：

| 维度 | 驱动变量 | 映射 |
|------|----------|------|
| **颜色（色相）** | 效价 `v` | -1 红(愤怒) → 0 蓝(平静) → +1 金(快乐) |
| **大小 / 速度 / 振幅 / 辉光** | 唤醒度 `\|v\|` | 0=平稳（最小最静）；**±1=愤怒与快乐两个极端同样最大最躁** |

⚠️ **设计约定**：大小表示的是「情绪强烈程度」，不是「开心程度」。所以**愤怒和快乐在球体大小上是对称的**——都是最大，0（平静）是最小。不要改回「快乐最大、愤怒最小」。

- 颜色在 RGB 空间插值（非色相旋转），避免愤怒→平静途中出现怪异的中间色（如绿色）。
- 当前为第一版，各系数（0.82~1.22 大小区间、辉光 1.9~3.1 等）可在 `EmotionOrb.jsx` / `emotion-utils.js` 微调。

⚠️ **尺寸与裁剪约束（已修，勿回退）**：玻璃球半径在 `Strands.jsx` / standalone 里 = `0.375 × glassSize`，**最大不超过 0.46（短边 uv 单位）**。原因：极端情绪（|v|=1，glassSize=1.22）时若半径 > 0.5 光球会超出父容器被剪裁（"最大化时展现不完整"的 bug）。坐标系已改为按 **短边 `min(uResolution.x,uResolution.y)`** 归一化，横屏/竖屏/窄容器都不再裁切。改 `glassSize` 区间或 `uRadius` 系数时，务必保证「最大半径 ≤ 0.46」，否则重新出现裁剪。

## 6. 主题（深色 / 浅色）
- **默认按深色背景调校**，深色下表现最佳。
- **浅色背景需专门适配**：原组件玻璃外壳 alpha 极低、菲涅尔边缘为白色，浅底上球体边界/质感会「散掉」，辉光被白稀释。
- 浅色适配做法（见 `standalone-themes.html`）：玻璃边缘改用**情绪色描边**、整体透明度提升、画布加 CSS `drop-shadow`。属第一版，辉光在浅底对比仍偏弱。
- **生产建议**：给 `EmotionOrb` 加 `theme="light" | "dark"` prop，把浅色调校固化进组件，而不是靠页面 CSS 补救。

## 7. 本地运行 / 预览
```bash
npm install
npm run dev        # Vite，默认 http://localhost:5173
```
免构建预览：直接用浏览器打开 `standalone.html` 或 `standalone-themes.html`（需联网从 CDN 加载 OGL）。

## 8. 已知限制 / 待办
- **光球尺寸上限已封顶**：为避免极端情绪下裁切，最大半径约 0.46（短边），因此尺寸变化幅度有限（约 1.5×）。若想更夸张的大小对比，应同步缩小最小半径而非放大最大半径。
- 浅色主题为第一版，辉光对比、球体质感仍可打磨。
- 当前唤醒度由 `|v|` 推导（单轴）。若业务需要，可加**独立第二轴**（如单独传入 arousal 值）做更精细控制。
- `Strands.jsx` 内 GLSL 着色器较复杂，调整需懂 WebGL；视觉效果调参优先改 `EmotionOrb.jsx` + `emotion-utils.js`。

## 9. 给接手 agent 的提示
- 改视觉风格优先动 `EmotionOrb.jsx` 和 `emotion-utils.js`，别碰 `Strands.jsx` 的 GLSL 除非必要。
- 若目标项目不用 React，可参考 `standalone.html` 把 `Strands` 逻辑用原生 JS 重写（已含完整着色器与挂载代码）。
- 数值范围约定：**-1.000 = 愤怒，0.000 = 平静，+1.000 = 快乐**，3 位小数。
