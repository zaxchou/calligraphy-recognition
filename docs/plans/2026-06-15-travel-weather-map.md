# 行旅气象地图 — 实现计划

> 将现有"翰墨行旅"地图升级为"行旅气象地图"，在时间-空间维度上叠加情绪气象维度。

---

## 1. 数据层分析

### 1.1 现有数据源

| 数据 | 来源 | 格式 |
|------|------|------|
| 行旅数据 | `artists.travel_notes` JSON | `{ periods: [...], locations: [...] }` |
| 年谱数据 | `artists.art_chronology` JSON | `[{ year, event, location, ... }]` |
| 作品列表 | `tubi_analyses` | 含 year, period_phase, content_analysis |
| 作品情绪 | `tubi_analyses.content_analysis.sentiment.polarity` | positive/negative/neutral |
| 作品综合情绪 | `tubi_analyses.content_analysis.combined_sentiment` | 含维度分、置信度 |
| 画家规则 | `artist_rules.life_stages` | 各阶段的情绪基线 |

### 1.2 情绪聚合策略

**从 `useMapData.fetchData()` 已经获取了全部画作列表。** 每幅画已有 `period` / `period_phase` 字段和 `content_analysis`（含 sentiment）。需要在 MapMode 数据加载阶段：

1. 对每个 location 下的 paintings 按 period 聚合情绪
2. 计算该地点的"情绪气象状态"（sunny / cloudy / overcast / storm / snow）
3. 生成情绪温度值（-5 ~ +5）

### 1.3 情绪 → 气象映射规则（纯数据驱动，零 AI 判断）

```
positive 占比 >= 60%  → ☀️ sunny  · 晴    · temp +2 ~ +4
positive 占比 40-60%  → ⛅ cloudy · 多云  · temp -1 ~ +1
negative 占比 40-60%  → ☁️ overcast · 阴  · temp -2 ~ -1
negative 占比 >= 60%  → ⛈️ storm  · 暴雨  · temp -4 ~ -3
neutral 占比 >= 60%   → ❄️ snow   · 雪    · temp -3 ~ -2
```

**情绪温度** = `(pos_count - neg_count) / total * 5`，映射到 -5 ~ +5。

**关键原则：** 这是纯 SQL 聚合 + 公式计算，不依赖 LLM。100% 确定性。

---

## 2. 后端改动

### 2.1 新增 API：`GET /api/v1/artists/{name}/emotion-timeline`

**用途：** 返回画家生平情绪时间线，按时期聚合。

**输入：** `name`（路径参数）

**输出：**
```json
{
  "artist_name": "李鱓",
  "periods": [
    {
      "id": "p0",
      "label": "少年求学",
      "year_range": [1686, 1710],
      "color": "#c45a3c",
      "emotion": "sunny",
      "temp": 2,
      "description": "江苏兴化，幼承庭训",
      "painting_count": 5,
      "positive_pct": 60,
      "negative_pct": 10,
      "neutral_pct": 30
    },
    ...
  ],
  "has_emotion_data": true
}
```

**实现逻辑：**

```python
@router.get("/{name}/emotion-timeline")
async def get_emotion_timeline(name: str, db: Session = Depends(get_db)):
    artist = db.query(Artist).filter(Artist.name == name).first()
    if not artist:
        raise HTTPException(404)
    
    # 1. 获取该画家的所有画作情绪数据
    paintings = db.query(TibaAnalysis).filter(
        TibaAnalysis.artist == name
    ).all()
    
    # 2. 解析每幅画的 sentiment
    # 3. 按 travel_notes 的 periods 聚合
    # 4. 如果没有情绪数据 → has_emotion_data: false
    # 5. 计算每个 period 的情绪分布和温度
    
    return { ... }
```

### 2.2 优化：在 `useMapData` 中复用已有 API

**方案 B（推荐，避免新增 API）：** 不新增后端接口，在前端 `useMapData.ts` 的 `fetchData()` 中直接利用已获取的画作列表计算情绪数据。因为 `fetchData()` 已经通过 `tibaApi.getAllResults()` 拉取了全部画作（含 `content_analysis` 字段），只需在前端做一次聚合计算。

**优势：**
- 零后端改动
- 零新增 API
- 数据已经在内存中（paintings 列表），聚合是 O(n) 操作
- 不存在"情绪数据缺失"时的 API 报错问题

---

## 3. 前端改动

### 3.1 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/src/views/MapMode.vue` | 重构 | 核心改动：天气 Canvas 层、天气卡片、底部时间线改版、路径颜色按情绪变化 |
| `frontend/src/views/MapMode/useMapData.ts` | 扩展 | 新增 emotionTimeline 数据结构、情绪聚合逻辑 |
| `frontend/src/router/index.js` | 微调 | 路由 meta.title "翰墨行旅" → "行旅气象地图" |

### 3.2 新增组件

| 组件 | 说明 |
|------|------|
| `WeatherCanvas.vue` | Canvas 天气粒子效果（雨/雪/阳光/闪电） |
| `WeatherCard.vue` | 右上角天气状态卡片（图标 + 温度 + 描述） |

### 3.3 useMapData 扩展

```typescript
// 新增类型
export interface EmotionPeriod {
  id: string
  label: string
  yearRange: [number, number]
  color: string
  emotion: 'sunny' | 'cloudy' | 'overcast' | 'storm' | 'snow'
  temp: number            // -5 ~ +5
  description: string
  paintingCount: number
  positivePct: number
  negativePct: number
  neutralPct: number
}

export interface EmotionTimeline {
  periods: EmotionPeriod[]
  hasEmotionData: boolean   // 是否有情绪数据
}

// 在 useMapData 中新增
function computeEmotionTimeline(
  periods: PeriodConfig[],
  paintings: Painting[],
  travelNotes: any
): EmotionTimeline { ... }
```

### 3.4 情绪数据计算（在 useMapData 中）

```typescript
function computeEmotionTimeline(periods, paintings, travelNotes): EmotionTimeline {
  // 1. 统计所有画作的情绪（解析 content_analysis.sentiment.polarity）
  let hasAnySentiment = false
  const periodSentiments: Record<string, { pos: number; neg: number; neu: number }> = {}
  
  for (const p of paintings) {
    const polarity = p.content_analysis?.sentiment?.polarity
    if (!polarity) continue
    hasAnySentiment = true
    
    // 按时期归类
    const py = parseInt(String(p.year))
    const period = periods.find(pp => py >= pp.yearRange[0] && py <= pp.yearRange[1])
    if (!period) continue
    
    if (!periodSentiments[period.id]) periodSentiments[period.id] = { pos: 0, neg: 0, neu: 0 }
    if (polarity === 'positive') periodSentiments[period.id].pos++
    else if (polarity === 'negative') periodSentiments[period.id].neg++
    else periodSentiments[period.id].neu++
  }
  
  // 2. 映射为气象状态
  const result = periods.map(p => {
    const s = periodSentiments[p.id] || { pos: 0, neg: 0, neu: 0 }
    const total = s.pos + s.neg + s.neu
    const posPct = total ? (s.pos / total * 100) : 0
    const negPct = total ? (s.neg / total * 100) : 0
    const temp = total ? ((s.pos - s.neg) / total * 5) : 0
    
    let emotion: string
    if (total === 0) emotion = 'sunny'          // 无数据默认晴
    else if (posPct >= 60) emotion = 'sunny'
    else if (posPct >= 40) emotion = 'cloudy'
    else if (negPct >= 60) emotion = 'storm'
    else if (negPct >= 40) emotion = 'overcast'
    else emotion = 'snow'
    
    return { ...p, emotion, temp, posPct, negPct, neutralPct: total ? (s.neu / total * 100) : 0, paintingCount: total, hasEmotionData: total > 0 }
  })
  
  return { periods: result, hasEmotionData: hasAnySentiment }
}
```

---

## 4. 向后兼容策略 ⚠️ 关键

### 4.1 情绪数据缺失时的行为

```
has_emotion_data === false 时：
  → 地图照常展示（现有行旅功能不受影响）
  → 天气 Canvas 层不渲染（无粒子效果）
  → 天气卡片不显示
  → 路径颜色使用现有 period.color（不变）
  → 页面标题显示"翰墨行旅"（而非"行旅气象地图"）
  → 底部时间线不显示 emoji 天气图标
```

### 4.2 部分画作有情绪、部分没有

```
某个 period 只有 3/10 幅画有情绪数据时：
  → 只用有数据的 3 幅计算（标注 "3/10 幅有数据"）
  → 不虚构数据，不推测
  → 如果 < 2 幅有数据，该 period 不显示气象状态
```

### 4.3 新增画家 / 新上传作品

```
新画家：travel_notes 存在 → 地图正常展示
  → 如果该画家的作品有 sentiment 数据 → 自动聚合，显示气象
  → 如果没有 → 降级为普通行旅地图
新作品上传：情感分析跑完后 → 下次打开地图时自动更新气象数据
```

### 4.4 页面标题动态切换

```
route.meta.title = emotionTimeline.hasEmotionData ? '行旅气象地图' : '翰墨行旅'
顶部 topbar-title 同步切换
```

---

## 5. MapMode.vue 改动细节

### 5.1 模板结构

```
<div class="map-mode-page">
  <!-- Top Bar -->
  <div class="map-topbar"> <!-- 标题动态切换 --> </div>

  <div class="map-main">
    <!-- 地图底图 -->
    <div class="map-bg"></div>

    <!-- Weather Canvas（仅 hasEmotionData 时渲染） -->
    <WeatherCanvas v-if="emotionTimeline.hasEmotionData" ... />

    <!-- ECharts Map -->
    <div ref="chartContainer"></div>

    <!-- Weather Card（仅 hasEmotionData 时渲染） -->
    <WeatherCard v-if="emotionTimeline.hasEmotionData" ... />

    <!-- City Quick List（不变） -->
    <div class="city-quick-list">...</div>

    <!-- Info Panel（不变） -->
    <transition name="panel-slide">...</transition>
  </div>

  <!-- Period Bar（底部时间线改版） -->
  <div class="period-bar">
    <!-- 每个 period 按钮增加天气 emoji -->
    <button v-for="period in periods" class="period-btn">
      <span v-if="emotionTimeline.hasEmotionData">{{ periodEmoji(period) }}</span>
      <span class="period-btn-dot" :style="{ background: period.color }"></span>
      <span class="period-btn-label">{{ period.label }}</span>
      <span class="period-btn-year">{{ formatYearRange(period.yearRange) }}</span>
    </button>
    <!-- Tour 按钮不变 -->
  </div>
</div>
```

### 5.2 路径颜色按情绪变化

当 `hasEmotionData === true` 时，ECharts lines series 的每段路径颜色根据目标 period 的情绪状态动态设置：

```typescript
function emotionToPathColor(emotion: string): string {
  const map = {
    sunny: '#c45a3c',    // 朱砂暖色
    cloudy: '#a09080',   // 灰棕
    overcast: '#6a6070', // 灰紫
    storm: '#4a3040',    // 暗紫
    snow: '#8a9ab0',     // 灰蓝
  }
  return map[emotion] || '#8b7d6b'
}
```

### 5.3 Tour 模式增强

播放行旅时，WeatherCard 实时显示当前到达城市的情绪状态（而非整个时期的状态）。Canvas 粒子效果也随当前城市切换。

---

## 6. 实现分步

### Step 1: 数据层 — `useMapData.ts` 扩展
- 新增 `EmotionPeriod`, `EmotionTimeline` 类型
- 实现 `computeEmotionTimeline()`
- 从 `fetchData()` 返回 `emotionTimeline`

### Step 2: 基础 UI — MapMode.vue 集成
- 导入 WeatherCanvas、WeatherCard 组件
- 添加 `emotionTimeline` 响应式数据
- 顶部栏标题动态切换
- 底部时间线增加天气 emoji

### Step 3: WeatherCanvas 组件
- 从 demo `emotion-weather-demo.html` 迁移 Canvas 粒子代码
- Vue 3 组件化（props: emotion, size）
- 粒子系统：rain / snow / sun / storm 四种模式

### Step 4: WeatherCard 组件
- 右上角浮动卡片
- 显示当前天气图标 + 状态名 + 温度 + 描述
- 随 tour 播放实时切换

### Step 5: 路径颜色 + Tour 增强
- 修改 `buildSegments()` / `buildOption()` 支持情绪颜色
- Tour 播放时同步切换 Canvas 粒子和 WeatherCard

### Step 6: 路由 + 测试
- router meta.title 更新
- 端到端测试：有情绪数据的画家（李鱓）、无情绪数据的画家

---

## 7. 潜在坑点

| 坑 | 风险 | 对策 |
|----|------|------|
| `content_analysis` JSON 解析失败 | 某些画的 sentiment 字段不存在或格式异常 | try-catch 包裹，失败跳过不崩溃 |
| 画作没有 `period_phase` 字段 | 无法归类到时期 | 用 `year` 手动匹配 `yearRange` |
| Canvas 性能 | 大量粒子 + ECharts 同时渲染卡顿 | 粒子数按情绪类型动态调整（sunny: 50, storm: 120） |
| Canvas 尺寸变化 | 窗口 resize 时 Canvas 不重绘 | resize 事件中 `canvas.width/height` 重置 + 粒子坐标重算 |
| `travel_notes` 数据格式不统一 | 不同画家的 travel_notes 可能是不同版本的 AI 输出 | 已有 `useMapData` 的回退逻辑（chronology 派生），保持不变 |
| 移动端 | Canvas 粒子在移动端性能差 | `@media (max-width: 768px)` 禁用 Canvas 层，仅保留天气卡片 |
| 时期数量多时时间线溢出 | 8+ 个时期按钮撑爆底部栏 | 已有 `overflow-x: auto`，保持不变 |

---

## 8. 预期效果

**有情绪数据的画家（如李鱓）：**
- 地图上路径颜色随情绪变化（晴=暖棕，暴雨=暗紫）
- Canvas 粒子效果渲染天气（雨/雪/阳光/闪电）
- 右上角天气卡片实时显示当前"气候"
- 底部时间线每个时期有天气 emoji
- 页面标题："行旅气象地图"
- Tour 播放时粒子、卡片、路径联动

**无情绪数据的画家：**
- 地图照常显示（现有功能不受影响）
- 无 Canvas 粒子、无天气卡片、无 emoji
- 页面标题："翰墨行旅"（保持原样）
- 一切和现在一样
