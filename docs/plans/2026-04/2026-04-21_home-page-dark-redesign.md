---
name: home-page-dark-redesign
overview: 首页全页暗色博物馆风格改版：hero滚动减速、header首页黑底白字、下半部分功能卡片/流程/引用区统一暗色设计。
design:
  architecture:
    framework: vue
  styleKeywords:
    - Dark Museum
    - Immersive
    - Glassmorphism
    - Elegant
    - Gold Accent
  fontSystem:
    fontFamily: Noto Serif SC
    heading:
      size: var(--text-display)
      weight: 500
    subheading:
      size: var(--text-h3)
      weight: 500
    body:
      size: var(--text-body)
      weight: 400
  colorSystem:
    primary:
      - "#c96442"
      - "#b8a47e"
    background:
      - "#141413"
      - rgba(255,255,255,0.03)
      - rgba(255,255,255,0.06)
    text:
      - "#ffffff"
      - rgba(255,255,255,0.78)
      - rgba(255,255,255,0.55)
    functional:
      - "#b8a47e"
      - "#c96442"
todos:
  - id: slow-hero
    content: 放慢 Hero 画廊双轨滚动速度（上排55s/下排70s）
    status: completed
  - id: dark-header
    content: App.vue header 添加首页专属黑底白字样式
    status: completed
  - id: dark-content
    content: Home.vue 下半部分改版为暗色博物馆风格
    status: completed
    dependencies:
      - slow-hero
  - id: verify-build
    content: npm run build 验证编译通过
    status: completed
    dependencies:
      - dark-header
      - dark-content
---

## Product Overview

对首页进行整体视觉升级，将 Hero 画廊、顶部导航及下方内容区域统一为暗色博物馆风格。

## Core Features

1. **放慢 Hero 画廊滚动**：将双轨无限滚动的动画时长显著增加，使画作移动更加缓慢优雅
2. **首页 Header 黑底白字**：仅在首页（`/`）将顶部导航栏切换为深色背景 + 白色文字，其他页面保持原有暖色风格不变
3. **内容区域暗色改版**：将 Hero 下方的"核心功能"、"使用流程"、"底部引用"三个区块全部改为暗色博物馆风格——深色背景、半透明暗色卡片、浅色文字、金色装饰线

## Tech Stack

- 前端框架：Vue 3 + Vite（现有）
- 样式：Scoped CSS + CSS 变量（现有设计系统）

## Implementation Approach

### Header 首页变黑方案

App.vue 的 `<header>` 添加动态 class：`{ 'home-header': $route.path === '/' }`。通过 scoped CSS 定义 `.home-header` 及其子元素覆盖样式，仅当路由为首页时生效，零影响其他页面。

### 暗色博物馆风格方案

将 Home.vue 的 `.home` 根容器背景从 `--parchment` 改为 `--deep-dark`，下方各区块适配：

- **功能卡片**：背景 `rgba(255,255,255,0.03)` + 边框 `rgba(255,255,255,0.06)`，hover 时微亮 + 金色边框
- **流程步骤卡片**：同样的暗色半透明卡片风格
- **文字系统**：标题纯白，描述文字半透明白色，section 装饰线改为金色渐变
- **quote-section**：已是暗底，微调 ornament 透明度与金色呼应

### 性能考量

纯 CSS 切换，无额外 JS 计算，无性能开销。动画仅修改 `animation-duration`，保持 GPU 加速的 `transform` 属性。

## Implementation Notes

- App.vue 的 `.main-header` 已有 `backdrop-filter: blur(18px)`，首页黑底版本保留此效果以维持毛玻璃质感
- 需确保 `.home-header` 下的 `.nav-item.active::after` 下划线颜色在暗底上清晰可见（使用 `--gold` 或保持 `--cinnabar`）
- `.feature-card:hover` 和 `.step-item:hover` 在暗色模式下不宜使用白色阴影，改用边框色变化 + 背景微亮
- 保持所有现有的响应式断点逻辑不变

## Directory Structure

```
frontend/src/App.vue              # [MODIFY] header 添加 home-header 动态 class + 覆盖样式
frontend/src/views/Home.vue       # [MODIFY] hero 速度 + 下半部分暗色博物馆风格改版
```

## Design Style

采用**暗色博物馆风格（Dark Museum）**，延续 Hero 区域的画廊氛围，将整个首页统一为沉浸式暗色调体验。

### 整体氛围

- 背景：深邃墨黑（#141413），营造博物馆展厅的庄重感
- 卡片：半透明暗色玻璃质感，如展品陈列柜
- 文字：纯白主标题 + 暖银灰副标题，保证暗底可读性
- 装饰：金色（#b8a47e）线条与点缀，呼应高端艺术空间

### Header（仅首页）

- 背景：纯黑 rgba(20,20,19,0.95) + backdrop-filter blur
- Logo：白色主文字 + 半透明白色副标题
- 导航：半透明白色文字，hover/active 变为纯白 + 金色下划线
- 底部边框：极淡的白色分割线

### 核心功能区块

- 背景：继承首页深色底
- 功能卡片：半透明暗底（rgba(255,255,255,0.03)）+ 极淡边框
- 卡片 hover：背景微亮至 rgba(255,255,255,0.06) + 金色边框浮现
- 图标圆圈：保持原有朱砂/金色/炭灰配色（在暗底上更鲜明）
- 箭头：半透明白色，hover 变金色

### 使用流程区块

- 步骤卡片：与功能卡片一致的暗色玻璃风格
- 步骤数字圆圈：保持朱砂红底白字（暗底上的视觉焦点）
- 连接箭头：朱砂色，透明度降低

### 引用区块

- 背景：保持深黑，与整体一致
- ornament：朱砂色，适当提高透明度（0.3 → 0.4）使其在暗底更明显
- 引用文字： parchment 暖白色
- 作者：金色

### 交互细节

- 卡片 hover：无阴影（暗底上白色阴影不自然），改用边框色变化 + 背景微亮 + 轻微上移
- 所有过渡动画保持现有 duration，确保手感一致