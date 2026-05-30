---
name: tubi-component-refactoring
overview: 按照 Vercel Composition Patterns 重构 Tubi 相关组件，按优先级顺序执行：1. TubiUploadDialog phase 拆分 2. TubiAnalysis 对话框提取 3. TubiRanking 复用 TubiEditDialog 4. TubiDetail props 聚合
todos:
  - id: refactor-upload-dialog
    content: 重构 TubiUploadDialog.vue，拆分 phase 组件
    status: completed
  - id: extract-dialogs
    content: 从 TubiAnalysis.vue 提取 4 个对话框组件
    status: completed
    dependencies:
      - refactor-upload-dialog
  - id: reuse-edit-dialog
    content: TubiRanking.vue 复用 TubiEditDialog 组件
    status: completed
    dependencies:
      - extract-dialogs
  - id: aggregate-detail-props
    content: TubiDetail.vue 聚合 analysis 相关 props
    status: completed
    dependencies:
      - reuse-edit-dialog
  - id: extract-comparison-bar
    content: TubiComparison.vue 提取 ComparisonBar 组件
    status: completed
    dependencies:
      - aggregate-detail-props
  - id: extract-gallery-item
    content: TubiGallery.vue 提取 TubiGalleryItem 组件
    status: completed
    dependencies:
      - extract-comparison-bar
---

## 产品概述

按照 Vercel Composition Patterns 原则，对 Tubi 相关组件进行渐进式重构，提升代码可维护性和可扩展性。

## 核心功能

- 按优先级顺序重构 6 个高/中优先级问题
- 每个重构步骤包含自我验证机制
- 安全性第一，无人值守执行
- 保持功能完全一致的前提下优化架构

## Tech Stack

- **前端框架**: Vue 3 (Composition API + `<script setup>`)
- **UI 组件库**: Element Plus
- **重构原则**: Vercel Composition Patterns
- **验证方式**: 手动功能测试 + Git 对比验证

## 重构优先级（按顺序执行）

1. **TubiUploadDialog.vue** - 阶段式条件渲染重构
2. **TubiAnalysis.vue** - 提取 4 个内联对话框
3. **TubiRanking.vue** - 复用 TubiEditDialog
4. **TubiDetail.vue** - Props 聚合优化
5. **TubiComparison.vue** - 提取对比条组件
6. **TubiGallery.vue** - 提取画廊单项组件

## 架构设计

每个重构步骤遵循：

- 先备份/提交当前状态
- 提取/重构组件
- 自我验证功能
- Git 提交，记录变更