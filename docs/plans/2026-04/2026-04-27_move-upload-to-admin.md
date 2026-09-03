---
name: move-upload-to-admin
overview: 将题跋图片上传功能从 Tubi 页面迁移到管理后台 ContentVerify 页面，新增"作品上传"tab
todos:
  - id: add-upload-tab
    content: 在 ContentVerify.vue 新增"作品上传"tab 并引入 TubiUploadDialog
    status: completed
  - id: remove-tubi-upload
    content: 移除 Tubi 前台上传入口（Gallery/Home/Analysis）
    status: completed
    dependencies:
      - add-upload-tab
  - id: test-push
    content: 测试并推送
    status: completed
    dependencies:
      - remove-tubi-upload
---

## 产品概述

将题跋图片上传功能从 Tubi 前台页面迁移到管理后台，统一管理入口

## 核心功能

- 在管理后台 ContentVerify 新增"作品上传"tab，作为第一个 tab
- 引入现有 TubiUploadDialog 组件，支持拖拽上传、模式选择、进度跟踪
- 移除 Tubi 前台（TubiGallery/TubiHome/TubiAnalysis）中的上传入口
- 上传完成后自动刷新管理后台的记录列表

## 技术栈

- 前端框架：Vue 3 + Element Plus（现有项目）
- 状态管理：uploadStore 全局单例（无需改动）
- API：tubiApi（无需改动）

## 实现方案

### 核心思路

TubiUploadDialog 组件本身是独立的、自包含的，只需在 ContentVerify 中引入并对接刷新逻辑即可。上传组件、阶段子组件、uploadStore、API 层均无需修改。

### 关键技术决策

1. **新 tab 位置**：放在第一个（题跋校对之前），因为上传是数据入口，逻辑上先有数据再校对
2. **TubiUploadDialog 直接复用**：该组件通过 `ref` 暴露 `open()` 方法，在 tab 面板中内嵌使用，不需要弹窗模式
3. **上传后刷新**：`@uploaded` 和 `@refresh` 事件对接 ContentVerify 的 `fetchRecords()`
4. **前台移除上传入口**：删除 TubiGallery 中的"批量上传"按钮及相关事件链

## 实现细节

### 修改文件清单

**[MODIFY] `frontend/src/views/ContentVerify.vue`**

- 在 `<el-tabs>` 中新增 `<el-tab-pane label="作品上传" name="upload">`，放在题跋校对之前
- 在 tab 面板中引入 TubiUploadDialog 组件
- 导入 TubiUploadDialog
- VALID_TABS 数组中添加 'upload'
- 对接 `@uploaded` 和 `@refresh` 事件到 `fetchRecords()`
- 页面副标题更新

**[MODIFY] `frontend/src/components/tubi/TubiGallery.vue`**

- 移除"批量上传"按钮
- 从 defineEmits 中移除 'show-batch-upload'

**[MODIFY] `frontend/src/views/TubiHome.vue`**

- 从 defineEmits 中移除 'show-batch-upload'
- 移除 TubiGallery 上的 `@show-batch-upload` 事件绑定

**[MODIFY] `frontend/src/views/TubiAnalysis.vue`**

- 移除 TubiUploadDialog 组件引用（第106-111行）
- 移除 import TubiUploadDialog
- 移除 uploadDialogRef
- 移除 openUploadDialog 方法
- 移除 TubiHome 上的 `@show-batch-upload` 事件绑定
- 移除 onUploaded 方法