---
name: tubi-analysis-split
overview: 将 3600+ 行的 TubiAnalysis.vue 拆分为多个独立组件，逐步验证确保无 bug
todos:
  - id: phase-1-ranking-card
    content: 阶段1：提取 TubiRankingCard.vue（首页排行榜模块）
    status: completed
  - id: phase-2-verify-1
    content: 验证阶段1：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-1-ranking-card
  - id: phase-3-gallery
    content: 阶段2：提取 TubiGallery.vue（作品库模块）
    status: completed
    dependencies:
      - phase-2-verify-1
  - id: phase-4-verify-2
    content: 验证阶段2：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-3-gallery
  - id: phase-5-comparison
    content: 阶段3：提取 TubiComparison.vue（名家对比模块）
    status: completed
    dependencies:
      - phase-4-verify-2
  - id: phase-6-verify-3
    content: 验证阶段3：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-5-comparison
  - id: phase-7-upload-dialog
    content: 阶段4：提取 TubiUploadDialog.vue（上传弹窗）
    status: completed
    dependencies:
      - phase-6-verify-3
  - id: phase-8-verify-4
    content: 验证阶段4：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-7-upload-dialog
  - id: phase-9-edit-dialog
    content: 阶段5：提取 TubiEditDialog.vue（编辑弹窗）
    status: completed
    dependencies:
      - phase-8-verify-4
  - id: phase-10-verify-5
    content: 验证阶段5：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-9-edit-dialog
  - id: phase-11-analysis-panel
    content: 阶段6：提取 TubiAnalysisPanel.vue（分析面板）
    status: completed
    dependencies:
      - phase-10-verify-5
  - id: phase-12-verify-6
    content: 验证阶段6：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-11-analysis-panel
  - id: phase-13-home-detail
    content: 阶段7：拆分 TubiHome.vue 和 TubiDetail.vue
    status: completed
    dependencies:
      - phase-12-verify-6
  - id: phase-14-verify-7
    content: 验证阶段7：检查功能正常，git commit
    status: completed
    dependencies:
      - phase-13-home-detail
  - id: phase-15-composable
    content: 阶段8：提取 useTubiAnalysis.js composable
    status: completed
    dependencies:
      - phase-14-verify-7
  - id: phase-16-verify-8
    content: 验证阶段8：最终验证，git commit
    status: completed
    dependencies:
      - phase-15-composable
---

## 产品概述

拆分 TubiAnalysis.vue（3600+ 行）这个臃肿的单文件组件，逐步拆分为多个职责单一的组件，确保每一步都经过验证，无 bug 后再继续。

## 核心功能

1. **渐进式拆分验证** - 每次只拆分一个模块，验证后再继续
2. **无人值守自动化** - 自我循环完成整个大任务
3. **保持功能完整** - 确保拆分过程中功能不丢失
4. **路由兼容** - 保持现有路由结构不变

## 技术栈选择

- 前端框架：Vue 3 + TypeScript
- UI 组件库：Element Plus
- 项目已有架构：单文件组件 → 模块化组件

## 实现方案

### 拆分策略

采用**增量式、自底向上**的拆分策略，每次只拆分一个小模块，确保：

1. 每次改动最小化
2. 拆分后立即验证
3. 验证通过再继续下一步

### 拆分顺序

按照依赖关系从简单到复杂排序：

| 阶段 | 组件名称 | 功能描述 | 预估行数 | 风险等级 |
| --- | --- | --- | --- | --- |
| 1 | `TubiRankingCard.vue` | 首页排行榜模块 | ~200行 | 低 |
| 2 | `TubiGallery.vue` | 作品库（画廊）模块 | ~600行 | 中 |
| 3 | `TubiComparison.vue` | 名家对比模块 | ~300行 | 低 |
| 4 | `TubiUploadDialog.vue` | 上传弹窗（含模式选择） | ~400行 | 中 |
| 5 | `TubiEditDialog.vue` | 编辑弹窗 | ~300行 | 低 |
| 6 | `TubiAnalysisPanel.vue` | 分析结果面板 | ~400行 | 中 |
| 7 | `TubiHome.vue` | 首页（无选中图片） | ~300行 | 中 |
| 8 | `TubiDetail.vue` | 详情页（有选中图片） | ~800行 | 高 |
| 9 | `useTubiAnalysis.js` | 核心业务逻辑 composable | ~500行 | 高 |


### 关键设计决策

1. **保持路由不变** - `/tubi` 和 `/tubi/:id` 仍然指向同一个入口组件
2. **入口组件保持** - TubiAnalysis.vue 作为入口，只负责路由分发和状态整合
3. **Props/Events 通信** - 父子组件通过 props 和 events 通信
4. **样式共享** - 复用现有 claude-design.css 样式系统

### 数据流程

```
TubiAnalysis.vue (入口)
  ├── 路由判断 → TubiHome.vue 或 TubiDetail.vue
  ├── useTubiAnalysis.js (业务逻辑)
  └── 各子组件 (通过 props/events 通信)
```

## 目录结构

```
frontend/src/
├── views/
│   ├── TubiAnalysis.vue          # [MODIFY] 入口组件，路由分发
│   ├── TubiHome.vue              # [NEW] 首页组件
│   ├── TubiDetail.vue            # [NEW] 详情页组件
│   └── TubiRanking.vue           # [保持不变] 已独立
├── components/
│   ├── tubi/
│   │   ├── TubiRankingCard.vue   # [NEW] 排行榜卡片
│   │   ├── TubiGallery.vue       # [NEW] 作品库
│   │   ├── TubiComparison.vue    # [NEW] 名家对比
│   │   ├── TubiUploadDialog.vue  # [NEW] 上传弹窗
│   │   ├── TubiEditDialog.vue    # [NEW] 编辑弹窗
│   │   └── TubiAnalysisPanel.vue # [NEW] 分析面板
│   └── ArtistStatsCard.vue       # [保持不变] 已独立
└── composables/
    └── useTubiAnalysis.js        # [NEW] 核心业务逻辑
```