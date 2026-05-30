---
name: home-hero-gallery-v2
overview: 首页 Hero 画廊优化：扩充图片至11张、生成缩略图解决卡顿、标题改白字楷体、移除 badge，并评估可选动画增强方案。
todos:
  - id: gen-thumbs
    content: 用 Pillow 批量生成11张李鱓作品缩略图到 public/images/hero/
    status: completed
  - id: extend-images
    content: Home.vue 扩展 heroImages 至11张，引用缩略图路径
    status: completed
    dependencies:
      - gen-thumbs
  - id: style-title
    content: 删除 hero-badge，标题改白色 + Noto Serif SC 字体
    status: completed
  - id: add-animations
    content: 增加标题淡入动画和鼠标视差交互
    status: completed
    dependencies:
      - style-title
  - id: verify-build
    content: npm run build 验证编译通过
    status: completed
    dependencies:
      - extend-images
      - add-animations
---

## 产品概述

对首页 Hero 画廊进行迭代优化，提升视觉丰富度和性能表现。

## 核心功能

1. **扩展画作数量**：将 Hero 画廊从5张扩展至全部11张李鱓作品，消除视觉重复感
2. **标题样式优化**：hero-title 改为白色，`font-family: 'Noto Serif SC', 'KaiTi', serif`
3. **缩略图生成**：用 Pillow 批量生成 600px 宽、质量 85% 的缩略图，解决原图过大导致的卡顿
4. **删除 hero-badge**：移除"AI 书画研究"标签及其关联样式
5. **增强动画效果**：在现有双轨视差滚动基础上，增加鼠标交互视差和标题淡入动画

## Tech Stack

- 前端框架：Vue 3 + Vite（现有）
- 缩略图生成：Python Pillow（后端 venv 已安装 12.2.0）
- 字体：Noto Serif SC（index.html 已预加载 Google Fonts）

## 实现方案

### 缩略图策略

- 脚本：`scripts/generate_hero_thumbs.py`，扫描 `backend/data/imported/李鱓/` 全部 11 张作品
- 输出尺寸：宽 600px，等比缩放，JPEG quality=85，目标单张 < 80KB
- 输出目录：`frontend/public/images/hero/`（覆盖现有5张原图，新增至11张）

### 前端改造

- Home.vue：扩展 `heroImages` 数组至11张缩略图路径
- 删除 `.hero-badge` DOM 及 `.badge-seal` / `.badge-text` 全部 CSS
- `.hero-title`：`color: var(--pure-white)` + `font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif`
- 新增 `.hero-title` 和 `.hero-subtitle` 的淡入上移动画（mounted 后触发）

### 动画增强（在现有双轨滚动基础上叠加）

- **标题入场动画**：`opacity 0→1` + `translateY(20px→0)`，delay 200ms，duration 1s，ease-out
- **鼠标视差交互**：监听 `mousemove`，根据鼠标 Y 轴位置微调上下两排滚动速度（CSS `animation-duration` 动态调整），增加沉浸感
- **图片 hover 提亮**：`.gallery-frame img:hover` 时 `brightness(0.72→0.95)` + `scale(1.03)`，duration 0.6s

## 目录结构

```
frontend/public/images/hero/
├── lishan_01.jpg   # [MODIFY] 缩略图（原图→600px）
├── lishan_02.jpg   # [MODIFY]
├── lishan_03.jpg   # [MODIFY]
├── lishan_04.jpg   # [MODIFY]
├── lishan_05.jpg   # [MODIFY]
├── lishan_06.jpg   # [NEW] 新增6张缩略图
├── lishan_07.jpg   # [NEW]
├── lishan_08.jpg   # [NEW]
├── lishan_09.jpg   # [NEW]
├── lishan_10.jpg   # [NEW]
└── lishan_11.jpg   # [NEW]

frontend/src/views/Home.vue  # [MODIFY] 扩展数组、删badge、改标题样式、加动画

scripts/generate_hero_thumbs.py  # [NEW] 批量缩略图生成脚本
```

## Agent Extensions

无需外部扩展，全部使用现有技术栈实现。