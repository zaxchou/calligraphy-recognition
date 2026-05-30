---
name: homepage-notion-redesign
overview: 参考 Notion 重新设计 Home.vue 首页：上半部分暗色 Hero+数据墙+功能卡，下半部分亮色 Claude 风格实时数据区
design:
  architecture:
    framework: vue
  styleKeywords:
    - Notion-style
    - Dark-mode Hero
    - Claude warm minimalism
    - Hard-cut transition
    - Chinese ink aesthetic
    - Parchment texture
    - Cinnabar accent
    - Glassmorphism navbar
  fontSystem:
    fontFamily: Noto Serif SC
    heading:
      size: 52px
      weight: 500
    subheading:
      size: 20px
      weight: 500
    body:
      size: 16px
      weight: 400
  colorSystem:
    primary:
      - "#c96442"
      - "#d97757"
      - "#a8503a"
    background:
      - "#0a0a0a"
      - "#141413"
      - "#f5f4ed"
      - "#faf9f5"
    text:
      - "#ffffff"
      - rgba(255,255,255,0.7)
      - "#141413"
      - "#4d4c48"
    functional:
      - "#b8a47e"
      - "#d4c5a0"
      - "#5a8a4a"
      - "#b53333"
todos:
  - id: rewrite-home-template
    content: 重写 Home.vue 模板：暗色 Hero+Stats+Feature + 硬切 + 亮色 Gallery+Insights+Process+Quote
    status: completed
  - id: rewrite-home-script
    content: 重写 Home.vue 脚本：并行 API 请求、数据处理、导航逻辑
    status: completed
  - id: rewrite-home-style
    content: 重写 Home.vue 样式：暗色区 Notion 风格 scoped CSS + 亮色区复用 claude-design.css
    status: completed
    dependencies:
      - rewrite-home-template
  - id: polish-responsive
    content: 完善响应式适配与动画细节，确保移动端体验
    status: completed
    dependencies:
      - rewrite-home-style
---

## 产品概述

重新设计系统首页（`/` 路由，Home.vue），参考 Notion.com 的现代 SaaS 官网风格。页面分为上下两大区块：上半部分采用暗色调（Notion 风格），下半部分恢复 Claude 宣纸色设计风格。所有数据从现有后端 API 实时获取，确保作品数量增长时首页数据自动更新。

## 用户原始需求

- 参考 https://www.notion.com/ 重新设计主页
- 上半部分暗色调，下半部分保持 Claude 风格
- 内容和布局重新规划
- 数据实时获取，避免手动维护

## 核心功能

### 上半部分 — 暗色 Notion 风格

1. **Hero 首屏**

- 保留现有画廊/视频滚动背景（上下双轨视差滚动效果）
- 文字布局从"左下角"改为"居中"（Notion 风格大标题居中）
- 大标题："中国画与书法" / "AI 综合分析系统"
- 副标题："题跋识别 · 字体溯源 · 构图分析 · 知识检索"
- 双 CTA 按钮：主按钮"开始分析" + 次按钮"浏览作品库"
- 信任背书：实时数据标签"已收录 {n} 幅画作 · {m} 位艺术家"

2. **数据信任墙（Stats Wall）**

- 暗色背景延续，5 个大数字横向平铺
- 收录画作总数 / 艺术家数量 / 册页套数 / 标签类别 / 分析完成数
- 金色/白色大数字 + 小字标签说明

3. **核心功能网格（Feature Grid）**

- 6 大功能入口：写意知识库、题跋空间分析、书法字体识别、潘天寿构图体系、起承转合分析、题跋大数据分析
- Notion 极简风格：小图标 + 标题 + 一句话描述 + → 箭头
- 扁平卡片设计，hover 时背景微亮 + 箭头右移
- 3 列响应式网格

### 过渡 — 硬切（无渐变）

从暗色区直接切换到亮色区，参考 Notion 的硬切过渡方式，依靠区块本身的巨大 padding 形成视觉呼吸。

### 下半部分 — Claude 宣纸色风格

4. **最新作品画廊（Recent Gallery）**

- 宣纸色背景 `#f5f4ed`，区块标题"最新收录"
- 从 API 实时获取最近 6 幅作品
- 3 列网格展示缩略图卡片
- 每张卡片：缩略图 + 标题 + 作者 + 题跋占比标签
- Claude 风格：白色底、暖色边框、圆角阴影、hover 抬升
- 点击跳转 `/tubi/{id}` 详情页

5. **数据洞察区（Data Insights）**

- 左右双栏布局
- 左栏：主题分布 TOP 5（横向条形图/列表，从 content-analysis/stats 获取）
- 右栏：题跋占比排行榜 TOP 5（从 tubi/results 数据计算）
- 使用 el-card 包装，Claude 风格卡片

6. **使用流程（Process）**

- 三步流程：上传图像 → AI 分析 → 查看结果
- 宣纸色卡片 + 朱砂编号圆点
- 箭头连接

7. **书法引用（Quote）**

- 保留现有书法引用区块
- 作为亮色区收尾或底部暗色收尾

## Tech Stack Selection

- **前端框架**：Vue 3（`<script setup>` Composition API）
- **UI 组件库**：Element Plus（el-card、el-button、el-icon）
- **图标**：Element Plus Icons Vue
- **样式**：CSS 变量（复用现有 `claude-design.css`）+ Scoped CSS
- **数据获取**：原生 Fetch API（并行 Promise.all）

## Implementation Approach

### 整体策略

完全重写 `Home.vue`，在上半部分构建暗色 Notion 风格界面，下半部分复用现有 Claude 设计系统的宣纸色变量。通过前端并行请求 4 个现有后端 API 获取实时数据，**不需要新建后端 API**。

### 关键决策

1. **不复用 TubiGallery 等组件**：现有组件是为 `/tubi` 页面设计的，依赖 Element Plus 的 el-card 且硬编码了 Claude 风格覆盖，不适合暗色区。Home 页直接内联实现更简洁。

2. **不新建后端 API**：现有 4 个 API 已覆盖所有数据需求：

- `GET /api/v1/tubi/stats/extended` → 总数、册页数、标签统计
- `GET /api/v1/content-analysis/artists` → 作者列表（length = 艺术家数）
- `GET /api/v1/tubi/results?limit=6` → 最新 6 幅作品（含缩略图、题跋占比）
- `GET /api/v1/content-analysis/stats?artist=xxx` → 主题分布

3. **暗色到亮色硬切过渡**：参考 Notion，不使用渐变，直接切换背景色，依靠区块间的巨大 padding 形成呼吸感。

4. **导航栏无需改动**：App.vue 已有 `home-header` 类，在首页路由时自动将导航栏切换为暗色玻璃态样式。

### 数据获取策略

前端并行发起 3 个请求：

```javascript
Promise.all([
  fetch('/api/v1/tubi/stats/extended'),
  fetch('/api/v1/content-analysis/artists'),
  fetch('/api/v1/tubi/results?limit=6&skip=0')
])
```

主题洞察数据在获取到 artists 后，用第一个作者名称发起第 4 个请求：

```javascript
fetch(`/api/v1/content-analysis/stats?artist=${artists[0]}`)
```

### 性能考虑

- 首页挂载时一次性获取所有数据，无轮询
- 图片使用懒加载（`loading="lazy"`）
- 画廊背景继续使用 CSS 动画（GPU 加速，无性能问题）

## Implementation Notes

- **暗色区样式**：在 `Home.vue` 的 `<style scoped>` 中完全自定义，使用硬编码的 rgba 白色/金色值，不依赖 claude-design.css（因为设计系统变量主要是为 Claude 亮色区服务的）
- **亮色区样式**：复用 claude-design.css 变量（`--parchment`、`--cinnabar`、`--ivory`、`--border-warm` 等），确保与系统其他页面风格一致
- **响应式**：Hero 区在移动端缩小标题字号；数据墙在 tablet 下改为 2 列，手机端改为 2×3 或 1 列；功能网格在 tablet 下 2 列，手机端 1 列
- **错误处理**：API 请求失败时优雅降级，显示占位数据或隐藏对应区块
- **点击跳转**：功能卡片和最新作品均使用 Vue Router 编程式导航

## Architecture Design

```
Home.vue（单文件组件）
├── Template
│   ├── 暗色区 wrapper (.dark-section)
│   │   ├── Hero 区域（背景 + 居中内容）
│   │   ├── Stats Wall（5 个大数字）
│   │   └── Feature Grid（6 个功能卡片）
│   ├── 亮色区 wrapper (.light-section)
│   │   ├── Recent Gallery（最新作品 3 列网格）
│   │   ├── Data Insights（左右双栏）
│   │   ├── Process Steps（三步流程）
│   │   └── Quote Section（书法引用）
│   └── 加载状态（全屏骨架屏）
├── Script
│   ├── API 请求函数（3 个并行 + 1 个依赖）
│   ├── 响应式数据（stats、artists、recentPaintings、themeData）
│   ├── 计算属性（topThemes、topTubiRatios）
│   └── 导航方法（goToTubi、goToAnalysis 等）
└── Style（scoped）
    ├── 暗色区样式（自定义 rgba）
    ├── 亮色区样式（复用 CSS 变量）
    ├── 动画（fadeInUp、数字计数）
    └── 响应式媒体查询
```

## Directory Structure

```
frontend/src/
├── views/
│   └── Home.vue                    # [MODIFY] 完全重写，Notion 暗色上半 + Claude 亮色下半
├── styles/
│   └── claude-design.css           # [MODIFY] 补充 --home-dark-surface 等首页暗色区变量（可选）
└── App.vue                         # [现有] home-header 类已支持，无需改动

backend/app/api/
├── tubi.py                         # [现有] /stats/extended、/results 已提供所需数据
└── content_analysis.py             # [现有] /artists、/stats 已提供所需数据
```

## Key Code Structures

```typescript
// Home.vue 数据接口
interface DashboardStats {
  total: number;
  albums: { count: number; item_count: number };
  tags: { count: number; top_tags: { name: string; count: number }[] };
}

interface RecentPainting {
  id: string;
  title: string;
  artist: string;
  thumbnail_url: string;
  inscription_percent: number;
}

// API 基础路径
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8002/api/v1';
```

## 设计架构

采用**上下分层的双风格设计**：上半部分为 Notion 暗色 SaaS 风格，下半部分为 Claude 宣纸人文风格，中间通过硬切过渡。

### 上半部分 — Notion 暗色风格

**Hero 区域：**

- 全宽深黑背景（#0a0a0a），保留画廊/视频滚动作为动态背景
- 内容绝对定位居中（非左下角）
- 大标题：Noto Serif SC，52px，白色，letter-spacing 0.08em，淡入动画
- 副标题：PingFang SC，16px，rgba(255,255,255,0.7)，letter-spacing 0.3em
- CTA 主按钮：朱砂色背景 #c96442，白色文字，圆角 8px
- CTA 次按钮：透明背景，白色边框 1px，白色文字
- 信任背书：小标签样式，金色文字 "已收录 128 幅画作 · 3 位艺术家"

**Stats Wall：**

- 延续暗色背景
- 5 个等宽列，大数字（48px，白色/金色）+ 小标签（14px，rgba(255,255,255,0.5)）
- 底部金色细线分隔（参考 Notion 的 social proof 区）

**Feature Grid：**

- 3 列 grid，gap 24px
- 卡片：无边框或 1px rgba(255,255,255,0.06) 边框，背景 rgba(255,255,255,0.03)
- hover：背景变为 rgba(255,255,255,0.06)，边框变为金色，箭头右移 3px
- 每个卡片：顶部小图标（24px）+ 标题（20px 衬线体）+ 描述（14px 灰色）+ 右侧箭头 →

### 过渡

暗色区最后一个区块与亮色区第一个区块之间无渐变、无阴影过渡，直接 background-color 切换，依靠各自区块 80px 的 padding 形成呼吸感。

### 下半部分 — Claude 宣纸色风格

**Recent Gallery：**

- 背景：--parchment #f5f4ed
- 区块标题：衬线体，--near-black，左侧朱砂竖线装饰
- 3 列网格，gap 24px
- 卡片：--ivory 背景，--border-warm 边框，--radius-lg 圆角，--shadow-whisper 阴影
- hover：--shadow-elevated，边框变为 --cinnabar-light
- 缩略图：aspect-ratio 4/3，object-fit cover，圆角
- 信息区：标题（衬线体 16px）+ 作者（ sans 14px 灰色）+ 题跋占比标签（朱砂色小标签）

**Data Insights：**

- 左右双栏，各用一个 el-card
- 卡片 header：--ivory 背景，衬线体标题
- 主题分布：简化横向条形图（用 div + width % 模拟），金色/朱砂/绿色区分
- 题跋排行：列表形式，前 3 名带金色/银色/铜色奖牌，右侧显示百分比

**Process Steps：**

- 横向排列三步，箭头连接
- 每步：--ivory 背景卡片，顶部朱砂圆形编号，标题衬线体，描述 sans 灰色

**Quote Section：**

- 背景可以是 --parchment 或 --deep-dark（二选一，建议暗色收尾更有力量感）
- 大号引号装饰 + 书法楷体引用文字 + 金色作者名