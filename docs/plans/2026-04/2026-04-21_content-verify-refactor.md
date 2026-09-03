---
name: content-verify-refactor
overview: 按优先级重构 ContentVerify.vue：拆出题跋校对组件、提取 SSE composable、合并重复函数、复用图片预览组件。每步完成后验证无 500 错误并 git 保存。
todos:
  - id: extract-useSSEStream
    content: 提取 useSSEStream.ts composable，消除重复 SSE 解析逻辑
    status: completed
  - id: merge-verify-functions
    content: 合并 confirmVerify/reverify 为 saveVerify，验证 build + 功能正常
    status: completed
    dependencies:
      - extract-useSSEStream
  - id: split-VerifyPanel
    content: 拆出题跋校对为 VerifyPanel.vue，ContentVerify 精简为容器
    status: completed
    dependencies:
      - merge-verify-functions
  - id: reuse-image-dialog
    content: 复用 TubiImageZoomDialog 替代内嵌图片预览逻辑
    status: completed
    dependencies:
      - split-VerifyPanel
  - id: extract-batch-ops
    content: 提取 useBatchOperations.ts，集中管理批量翻译/分析状态
    status: completed
    dependencies:
      - reuse-image-dialog
---

## Product Overview

重构 `ContentVerify.vue`（46KB，约 1000+ 行），将其从一个臃肿的单文件组件拆分为多个独立、可复用的模块，提升代码可维护性和可读性。

## Core Features

- P0：拆出题跋校对核心逻辑为独立 `VerifyPanel.vue` 组件，`ContentVerify.vue` 只保留 tabs 容器和共享头部统计
- P1：提取 `useSSEStream()` composable，消除 `startBatchAnalyze` / `startBatchTranslate` 中重复的 SSE 解析逻辑
- P1：合并 `confirmVerify()` 与 `reverify()` 重复函数
- P2：复用 `TubiImageZoomDialog.vue` 替代 `ContentVerify.vue` 内嵌的图片缩放/拖拽实现
- P2：提取 `useBatchOperations()` composable，将批量翻译/分析的状态与逻辑集中管理

## Tech Stack

- Frontend: Vue 3 + Vite + ElementPlus + `<script setup>` + Composition API
- Backend: FastAPI (验证 500 错误用)

## Implementation Approach

### 安全重构策略

采用**渐进式重构**，每一步完成后都执行：

1. `npm run build` 确保编译通过
2. 启动后端 + 前端，访问 `/content-verify` 页面验证无 500/404
3. `git commit` 保存状态

### 拆分策略

- **VerifyPanel.vue**：接收 `records`、`currentRecord`、`filter` 等 props，通过 `emit` 向上层通信（保存、跳转、翻译等），保持与父组件的松耦合
- **useSSEStream.ts**：通用 SSE 流式响应解析器，接收 `fetch` Response 和回调函数，返回 cancel 方法
- **useBatchOperations.ts**：管理 `showAnalyzeProgress` / `showTranslateProgress` / `analyzeProgress` / `translateProgress` 等批量操作状态

### 关键决策

- `VerifyPanel` 不直接管理 `records` 列表，由父组件 `ContentVerify` 统一获取和过滤，避免数据不一致
- `useSSEStream` 不绑定具体业务，只处理通用的 `getReader` → `decode` → `split('\n')` → `parse` 流程
- 复用 `TubiImageZoomDialog` 时，将其 props 扩展为支持自定义 title（默认"原图查看"），保持向后兼容
- 合并 `confirmVerify`/`reverify` 为 `saveVerify(isReverify = false)`，通过参数区分行为和文案

## Architecture Design

```
ContentVerify.vue (tabs 容器)
├── page-header (统计 + 按钮)
├── el-tabs
│   ├── VerifyPanel.vue (props: records, filteredRecords, currentIndex, imageUrl, fullImageUrl...)
│   │   ├── filter-section
│   │   ├── progress-section
│   │   ├── verify-card (图片 + 文本编辑 + 操作按钮)
│   │   └── dialogs (弹窗)
│   ├── AlbumManager.vue
│   ├── TagManager.vue
│   ├── StripManager.vue
│   └── DimensionInput.vue
└── dialogs (批量翻译/分析选项弹窗 → 由 useBatchOperations 管理)
```

## Directory Structure

```
frontend/src/
├── views/
│   ├── ContentVerify.vue          # [MODIFY] 精简为 tabs 容器 + 头部 + 批量操作
│   └── VerifyPanel.vue            # [NEW] 题跋校对核心面板组件
├── composables/
│   ├── useSSEStream.ts            # [NEW] 通用 SSE 流式响应解析
│   └── useBatchOperations.ts      # [NEW] 批量翻译/分析状态管理
└── components/tubi/
    └── TubiImageZoomDialog.vue    # [MODIFY] 扩展 title props，保持向后兼容
```

## Key Code Structures

```typescript
// useSSEStream.ts
export function useSSEStream() {
  async function streamSSE(
    response: Response,
    onEvent: (event: any) => void,
    onError?: (error: any) => void
  ): Promise<void>
  return { streamSSE }
}

// useBatchOperations.ts
export function useBatchOperations(recordsRef: Ref<any[]>, fetchRecords: () => Promise<void>) {
  const analyzing = ref(false)
  const batchTranslating = ref(false)
  const showAnalyzeProgress = ref(false)
  // ...
  async function startBatchAnalyze(mode: 'incremental' | 'full')
  async function startBatchTranslate(mode: 'untranslated' | 'all')
  return { analyzing, batchTranslating, showAnalyzeProgress, startBatchAnalyze, startBatchTranslate, ... }
}
```

## Agent Extensions

无需使用外部扩展，本项目为纯 Vue 3 前端重构，不涉及金融数据、微信文章、浏览器自动化等场景。