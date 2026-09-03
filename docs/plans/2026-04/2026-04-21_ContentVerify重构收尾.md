---
name: ContentVerify重构收尾
overview: 修复 TubiImageZoomDialog title prop 生效问题，移除 VerifyPanel 硬编码 API_BASE
todos:
  - id: fix-tubi-dialog-title
    content: 修复 TubiImageZoomDialog.vue title prop 绑定
    status: completed
  - id: fix-verify-panel-api-base
    content: 给 VerifyPanel.vue 添加 apiBase prop 并替换硬编码地址
    status: completed
    dependencies:
      - fix-tubi-dialog-title
  - id: pass-api-base-content-verify
    content: ContentVerify.vue 向 VerifyPanel 传递 apiBase prop
    status: completed
    dependencies:
      - fix-verify-panel-api-base
  - id: build-verify-push
    content: npm run build 验证后 commit + push
    status: completed
    dependencies:
      - pass-api-base-content-verify
---

## 产品概述

完成 `ContentVerify.vue` 重构计划的收尾工作。原计划5项任务中，4项已完成，剩余1项（TubiImageZoomDialog title prop）存在 bug，同时发现 VerifyPanel.vue 中图片 URL 硬编码了开发环境地址。

## 核心功能

- 修复 TubiImageZoomDialog.vue：template 中的 `title` 绑定使用传入的 prop 而非硬编码
- 修复 VerifyPanel.vue：imageUrl / fullImageUrl 计算属性中硬编码的 `http://localhost:8001` 改为通过 props 传入的 apiBase
- ContentVerify.vue 向 VerifyPanel 传递 `apiBase` prop

## Tech Stack

- Frontend: Vue 3 + Vite + ElementPlus + `<script setup>` + Composition API

## 实现方法

采用**渐进式收尾策略**，每步修改后执行 `npm run build` 验证编译通过，然后 `git commit`。

### 修改内容

1. **TubiImageZoomDialog.vue** [MODIFY]：将 template 第4行 `title="原图查看"` 改为 `:title="title"`，使传入的 `title` prop 生效（默认仍回退到"原图查看"）
2. **VerifyPanel.vue** [MODIFY]：

- props 中新增 `apiBase: { type: String, default: 'http://localhost:8001' }`
- imageUrl / fullImageUrl 计算属性中 `'http://localhost:8001/static/...'` 改为 `` `${props.apiBase}/static/...` ``

3. **ContentVerify.vue** [MODIFY]：`<VerifyPanel>` 标签上添加 `:api-base="API_BASE"` 属性传递

## 架构设计

无需新增文件或模块，仅在现有组件间调整 props 绑定和 URL 构建方式。

## Directory Structure

```
frontend/src/
├── views/
│   ├── ContentVerify.vue          # [MODIFY] VerifyPanel 添加 apiBase prop 传递
│   └── VerifyPanel.vue            # [MODIFY] 新增 apiBase prop，替换硬编码地址
└── components/tubi/
    └── TubiImageZoomDialog.vue    # [MODIFY] title prop 绑定到 template
```