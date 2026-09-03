---
name: content-analysis-incremental-mode
overview: 内容分析批量重跑增加增量/全量选项
todos:
  - id: content-verify-mode-select
    content: 在 ContentVerify.vue 新增 analyzeMode ref 和 el-select 模式选择器，triggerBatchAnalyze 根据模式传参
    status: completed
---

## 用户需求

在「重新分析」按钮旁边增加模式选择下拉框：

- **增量模式（默认）**：只分析新上传/未校验的记录（`force_reanalyze=false`）
- **全量模式**：重新分析所有记录含已校验的（`force_reanalyze=true`）

## 产品概述

现有校对页面的「重新分析全部」按钮写死了 `force_reanalyze=true`，导致每次点击都会重跑全部 169 条记录，耗时且浪费 API 配额。用户希望默认只分析新数据，必要时才选择全量重跑。

## 核心功能

- 在「重新分析」按钮旁新增 `el-select` 模式选择器
- 两个选项：增量（只分析未校验）/ 全量（强制重跑含已校验）
- 默认选中增量模式
- 按钮文案随选项动态变化

## 技术方案

### 技术选型

- 前端框架：Vue 3 + ElementPlus（项目已有 el-select/el-radio-group 组件）
- 无需新增依赖

### 实现思路

在按钮组区域新增 `el-select` 组件，默认值 `analyzeMode = 'incremental'`。`triggerBatchAnalyze()` 函数根据模式传参调用后端 `batch_analyze` 接口。

### 关键文件

- `frontend/src/views/ContentVerify.vue`（唯一改动文件）
- 后端 `backend/app/api/content_analysis.py` 的 `batch_analyze` 已有 `force_reanalyze` 参数，**无需改动**

### 目录结构

```
frontend/src/views/ContentVerify.vue  [MODIFY]
  - 第 23 行附近：新增 analyzeMode ref + el-select 模式选择器
  - 第 671-685 行：triggerBatchAnalyze() 读取 analyzeMode 决定 force_reanalyze 参数
```

### 实现细节

```javascript
// 新增
const analyzeMode = ref('incremental')  // 'incremental' | 'full'

// 模板（按钮组区域）
<el-select v-model="analyzeMode" size="small" style="width:120px">
  <el-option label="增量（只分析未校验）" value="incremental" />
  <el-option label="全量（含已校验）" value="full" />
</el-select>
<el-button @click="triggerBatchAnalyze">
  {{ analyzeMode === 'full' ? '重新分析全部' : '重新分析未校验' }}
</el-button>

// triggerBatchAnalyze()
const force = analyzeMode.value === 'full'
const res = await fetch(`/content-analysis/batch?artist=李鱓&force_reanalyze=${force}`, ...)
```