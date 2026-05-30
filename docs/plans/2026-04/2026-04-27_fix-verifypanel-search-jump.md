---
name: fix-verifypanel-search-jump
overview: 修复 VerifyPanel 搜索结果"跳转"按钮：改为在当前面板内切换记录（不弹新页面），并修复所有搜索结果都跳到同一个作品的 bug
todos:
  - id: fix-jump-button
    content: 修改 VerifyPanel.vue：跳转按钮改用 onSelectSearchResult，删除 jumpToDetail 和 router 相关代码，修复 jumpToRecordById 竞态 bug
    status: completed
---

## 需求概述

修复 ContentVerify 页面搜索对话框中"跳转"按钮的行为：点击后应在当前 VerifyPanel 面板内切换到对应记录（方便校对编辑），而不是弹出新的作品详情页。同时修复所有搜索结果都跳转到同一个作品（"花卉册八开之三"）的 bug。

## 核心问题

1. "跳转"按钮当前调用 `jumpToDetail(item)` 打开新标签页，用户不需要
2. `jumpToRecordById` 在清除筛选条件后，watch 异步将 `currentIndex` 重置为 0，导致总是跳到列表第一条记录

## 技术方案

### 修改文件

- `frontend/src/views/VerifyPanel.vue`

### 修复内容（共 4 处修改）

**修改 1：模板 — "跳转"按钮改用面板内切换**

- 第 226 行：`@click.stop="jumpToDetail(item)"` → `@click.stop="onSelectSearchResult(item)"`
- `onSelectSearchResult` 已有正确的面板内切换逻辑（调用 `jumpToRecordById`）

**修改 2：删除不再需要的 router 相关代码**

- 第 237 行：删除 `import { useRouter } from 'vue-router'`
- 第 257 行：删除 `const router = useRouter()`

**修改 3：修复 `jumpToRecordById` 的 watch 竞态 bug**

- 第 437-460 行：将函数改为 `async`，在清除筛选条件后使用 `await nextTick()` 等待 `filteredRecords` 重新计算完成，再设置 `currentIndex`
- 原因：第 385 行的 `watch([filterPeriod, verifyFilter], () => { currentIndex.value = 0 })` 会在筛选条件变化时异步重置 `currentIndex` 为 0，导致后续设置的正确索引被覆盖

**修改 4：删除 `jumpToDetail` 函数**

- 第 558-561 行：删除整个 `jumpToDetail` 函数

### 实现原理

- `onSelectSearchResult(item)` → `jumpToRecordById(item.id)` → 在 `filteredRecords` 中查找匹配记录 → 设置 `currentIndex` 切换面板显示
- 如果记录被筛选条件过滤掉了，先清除筛选，用 `nextTick` 等待 Vue 响应式更新完成，再重新查找并设置正确的索引

# Agent Extensions

无需使用 Agent Extensions。