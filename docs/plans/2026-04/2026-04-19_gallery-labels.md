---
name: gallery-labels
overview: 作品库图片右下角添加标签显示（册页、条屏等），Claude配色
design:
  architecture:
    framework: vue
  styleKeywords:
    - Claude风格
    - 朱砂色
    - 金色
    - 柔和圆角
    - 半透明背景
  fontSystem:
    fontFamily: PingFang SC
    heading:
      size: 20px
      weight: 600
    subheading:
      size: 16px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#c96442"
      - "#b8a47e"
    background:
      - rgba(255, 255, 255, 0.92)
      - "#f5f4ed"
    text:
      - "#ffffff"
      - "#141413"
    functional:
      - "#c96442"
      - "#b8a47e"
todos:
  - id: add-album-tag
    content: 在 gallery-image-wrapper 添加册页标签显示逻辑
    status: completed
  - id: add-tags-parsing
    content: 解析并显示 tags 字段中的标签（如条屏）
    status: completed
    dependencies:
      - add-album-tag
  - id: add-tag-styles
    content: 添加 Claude 风格的标签 CSS 样式
    status: completed
    dependencies:
      - add-tags-parsing
  - id: test-and-verify
    content: 验证标签显示效果，确保无标签时不显示
    status: completed
    dependencies:
      - add-tag-styles
---

## 产品概述

在作品库图片右下角添加作品类型标签（如"册页"、"条屏"），有对应标签时显示，没有时隐藏。

## 核心功能

- 有 `album_name` 字段时显示"册页"标签
- 有 `tags` 字段时解析并显示对应标签（如"条屏"）
- 标签位于图片右下角，样式采用 Claude 配色
- 无标签时不显示，保持界面简洁

## 技术方案

基于现有的作品库 gallery 结构，在 `gallery-image-wrapper` 内右下角添加标签容器。

### 数据结构

- 使用 `item.album_name` 判断是否为册页
- 使用 `item.tags` 判断是否有其他类型标签（如条屏）
- 支持多标签叠加显示

### 关键修改点

- **frontend/src/views/TubiAnalysis.vue**：在图片容器中添加标签显示逻辑和样式
- 复用项目现有的 Claude 配色系统（`claude-design.css`）

## 设计风格

采用 Claude 设计语言中的柔和暖色调：

- **朱砂色标签**：主要标签（册页）使用 `--cinnabar` 朱砂色
- **金色标签**：次要标签使用 `--gold` 金色
- **透明玻璃效果**：半透明白色背景，大圆角，柔和阴影
- **排版**：使用 `--font-sans` 字体，`--text-caption` 字号，字重600

## 标签布局

- 位置：图片右下角，采用绝对定位 `bottom: 8px; right: 8px`
- 样式：大圆角 `--radius-lg`，柔和阴影 `--shadow-whisper`，内边距 `6px 12px`
- 多标签布局：多个标签从右向左堆叠，间距 `6px`