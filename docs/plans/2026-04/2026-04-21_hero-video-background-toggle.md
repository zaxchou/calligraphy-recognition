---
name: hero-video-background-toggle
overview: 首页 Hero 区域新增视频背景切换功能：将生成的博物馆视频作为可选背景，保留现有画廊效果，通过开关一键切换。
todos:
  - id: copy-video
    content: 复制视频到 frontend/public/videos/ 目录
    status: completed
  - id: add-video-bg
    content: Home.vue 添加视频背景、切换按钮和 showVideoBg 状态
    status: completed
    dependencies:
      - copy-video
  - id: add-toggle-styles
    content: 添加视频背景和切换按钮的 CSS 样式
    status: completed
    dependencies:
      - add-video-bg
  - id: verify-build
    content: npm run build 验证编译通过
    status: completed
    dependencies:
      - add-toggle-styles
---

## 产品概述

在首页 Hero 区域新增视频背景模式，与现有双轨画廊滚动效果并存，通过一个切换开关随时切换。

## 核心功能

1. 视频背景：使用 `hero_museum_li_shan.mp4` 作为 hero 全屏背景视频，自动播放、静音、循环
2. 保留画廊：现有双轨视差滚动画廊完全保留
3. 切换开关：在 hero 区域右上角放置一个切换按钮，图标+文字提示，可在视频背景和画廊背景之间切换
4. 遮罩层不变：hero-overlay 和 hero-vignette 始终保留，确保标题可读性

## Tech Stack

- 前端框架：Vue 3 + Vite（现有）
- 媒体资源：HTML5 `<video>` 标签

## 实现方案

### 视频资源处理

- 源文件：`backend/data/hero_museum_li_shan.mp4`
- 复制到：`frontend/public/videos/hero_museum_li_shan.mp4`（Vite dev server 可直接通过 `/videos/...` 引用）

### 前端改造（Home.vue）

**模板层**：

- 在 `hero-gallery` 同级添加 `hero-video` 容器，内嵌 `<video>`（autoplay muted loop playsinline）
- `hero-gallery` 和 `hero-video` 通过 `v-show="!showVideoBg"` / `v-show="showVideoBg"` 控制显隐
- 在 `hero-section` 右上角添加切换按钮 `.bg-toggle`，图标使用 Element Plus `VideoPlay` / `Picture` 或纯文字
- 按钮文案随状态变化："视频背景" / "画廊背景"

**脚本层**：

- 新增 `showVideoBg` ref，默认 `true`（先展示视频效果）
- 视频路径常量 `VIDEO_SRC = '/videos/hero_museum_li_shan.mp4'`

**样式层**：

- `.hero-video`：absolute inset:0，z-index 与 hero-gallery 同级
- `.hero-video video`：width/height 100%，object-fit: cover
- `.bg-toggle`：absolute 定位右上角，z-index 高于遮罩层，半透明暗底圆角按钮，hover 提亮

### 性能考量

- 视频通过 `v-show` 而非 `v-if` 控制，DOM 始终存在，切换时无加载延迟
- `muted` + `playsinline` 确保移动端自动播放兼容性
- 视频文件较大（预计数十 MB），仅首页加载一次，不影响其他页面