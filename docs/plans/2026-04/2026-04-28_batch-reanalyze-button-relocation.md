---
name: batch-reanalyze-button-relocation
overview: 将"批量重跑"按钮从 ContentAnalysis（大数据分析）页面移到 ContentVerify（管理后台）页面，替换原来的"分析"按钮
todos:
  - id: remove-batch-reanalyze-from-content-analysis
    content: 移除 ContentAnalysis.vue 中的批量重跑按钮及相关代码
    status: pending
  - id: rename-analyze-button-in-content-verify
    content: 将 ContentVerify.vue 中的"分析"按钮改名为"批量重跑"
    status: pending
---

## 需求概述

将"批量重跑"按钮从 ContentAnalysis.vue（大数据分析页）移动到 ContentVerify.vue（管理后台页），取代原有的"分析"按钮。

## 具体改动

1. **ContentAnalysis.vue**：移除"批量重跑"按钮及相关代码
2. **ContentVerify.vue**：将"分析"按钮改名为"批量重跑"，更新图标和弹窗文案

## 技术方案

这是一个简单的 UI 调整任务，不需要复杂的技术方案。

### 改动点

1. **ContentAnalysis.vue**：

- 移除"批量重跑"按钮（line 21-29）
- 移除 `batchReanalyzeLoading` ref（line 529）
- 移除 `batchReanalyze` 函数（line 548-591）
- 移除结果弹窗相关代码（line 531-538, 440-470）

2. **ContentVerify.vue**：

- 将"分析"按钮改为"批量重跑"（line 37-38）
- 图标从 `<RefreshRight />` 改为 `<Refresh />`
- 弹窗标题从"批量重新分析"改为"批量重跑"（line 112）
- 弹窗描述更新为更清晰的说明

# Agent Extensions

无