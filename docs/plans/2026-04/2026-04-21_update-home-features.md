---
name: update-home-features
overview: 在主页核心功能区域新增"题跋大数据分析"卡片，使功能板块从5个变为6个，布局保持3列2行整齐排列。
todos:
  - id: add-bigdata-card
    content: 在 Home.vue 中新增"题跋大数据分析"功能卡片及样式
    status: completed
---

## 产品概述

更新主页（Home.vue）下半部分"核心功能"模块介绍，新增"题跋大数据分析"板块。

## 核心功能

- 在现有的5个功能卡片基础上，新增第6个卡片"题跋大数据分析"
- 卡片路由指向 `/content-analysis`
- 选用合适的 Element Plus 图标
- 添加独特的图标底色样式
- 保持现有3列grid布局（6个卡片正好2行3列，无需调整布局）

## Tech Stack

- 前端框架：Vue 3 + Element Plus Icons
- 样式：CSS 变量 + Scoped CSS

## 实现方案

直接在 `frontend/src/views/Home.vue` 中修改三处：

1. **Script 导入区**：新增 `Histogram` 图标导入
2. **Template 卡片区**：在 `feature-cards` 末尾添加第6个卡片，包含：

- 路由跳转：`$router.push('/content-analysis')`
- 图标：`Histogram`
- 标题：题跋大数据分析
- 描述：批量分析题跋内容，统计主题、情感、时期等多维度数据
- 样式类：`icon-circle analytics`

3. **Style 样式区**：新增 `.icon-circle.analytics` 样式，使用蓝紫渐变底色以区分已有5种颜色

## 影响范围

仅修改 `frontend/src/views/Home.vue` 单文件，无其他依赖改动。