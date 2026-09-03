---
name: inscription-annotator
overview: 新建题跋多边形手动标注工具：前端独立页面 + 后端更新接口，支持从作品详情页和校对页进入，标注结果写入 tubi_analyses 表的 regions 和 inscription_percent 字段。
todos:
  - id: backend-add-regions-api
    content: 在后端 tubi.py 新增 PATCH /api/v1/tubi/:id/regions 接口
    status: completed
  - id: frontend-create-annotator-view
    content: 新建 InscriptionAnnotator.vue：SVG 多边形编辑器 + 右侧面板 + 实时面积显示
    status: completed
  - id: frontend-register-route
    content: 在 router/index.ts 注册 /annotate/:id 路由
    status: completed
    dependencies:
      - frontend-create-annotator-view
  - id: integrate-detail-page
    content: 在 TubiAnalysis.vue 作品详情页增加「手动标注」按钮
    status: completed
    dependencies:
      - frontend-register-route
      - backend-add-regions-api
  - id: integrate-verify-page
    content: 在 ContentVerify.vue 校对页增加「手动标注」按钮
    status: completed
    dependencies:
      - frontend-register-route
      - backend-add-regions-api
---

## 用户需求

在题跋分析系统中新增手动多边形标注工具，用于在 AI 自动分析失败或不准确时人工修正题跋区域。

## 产品概述

新增一个独立的手动标注页面 `InscriptionAnnotator.vue`，通过弹出窗口方式使用，支持对已上传到数据库的图片进行多边形区域标注。

## 核心功能

- **多边形绘制**：点击图片添加顶点，双击封闭多边形；已有关键点可拖拽调整；支持撤销
- **多区域支持**：可绘制多个独立的题跋区域多边形
- **实时面积**：右上角实时显示当前已标注总面积及占图片百分比
- **保存落库**：调用后端 API 直接更新 `tubi_analyses` 的 `regions`、`inscription_percent` 等字段，不触发任何 AI 分析流程
- **入口集成**：作品详情页（TubiAnalysis.vue）和校对页（ContentVerify.vue）均提供「手动标注」按钮

## 使用场景

AI 分析失败或结果离谱时，用户点击「手动标注」→ 打开标注页 → 在图片上绘制题跋区域 → 保存 → 返回原页面，数据自动刷新

## 技术栈

- 前端：Vue 3 + Composition API + TypeScript（内联 SVG 多边形编辑器，不引入额外依赖）
- 后端：FastAPI，新增 `PATCH /api/v1/tubi/:id/regions` 端点
- 数据格式：矩形格式（`{x1, y1, x2, y2}`），与现有 `regions` JSON 结构完全一致

## 实现方案

### 后端

1. 在 `backend/app/api/tubi.py` 新增 `PATCH /api/v1/tubi/{id}/regions` 路由
2. 接收 `{"inscription_regions": [{x1,y1,x2,y2}, ...]}`，可选携带 `painting_regions` 和 `blank_regions`
3. 调用 `area_calculator.calculate_area_stats()` 计算三个百分比
4. 更新 `tubi_analyses` 表的 `regions`、`inscription_percent`、`painting_percent`、`blank_percent`、`updated_at`

### 前端

1. 新建 `frontend/src/views/InscriptionAnnotator.vue`（独立页面）
2. 路由：`/annotate/:id`，在 `frontend/src/router/index.ts` 注册
3. 标注层：基于 SVG 实现——`mousedown` 添加顶点，`mousemove` 拖拽顶点（点击判断阈值 8px），`dblclick` 封闭多边形
4. 右侧面板：当前多边形列表（显示面积），工具栏（完成当前 / 删除当前多边形 / 撤销）
5. 右上角：实时显示已标注总面积及百分比
6. 保存：PATCH `/api/v1/tubi/:id/regions`，成功后 `router.back()` 返回

### 集成

- `TubiAnalysis.vue`：在题跋分析操作区增加「手动标注」按钮
- `ContentVerify.vue`：在校对操作区增加「手动标注」按钮

## 目录结构

```
frontend/src/
├── views/
│   └── InscriptionAnnotator.vue   # [NEW] 独立标注页面
├── router/
│   └── index.ts                   # [MODIFY] 注册 /annotate/:id 路由
backend/app/api/
└── tubi.py                        # [MODIFY] 新增 PATCH regions 端点
frontend/src/
├── views/
│   ├── TubiAnalysis.vue           # [MODIFY] 增加「手动标注」按钮
│   └── ContentVerify.vue         # [MODIFY] 增加「手动标注」按钮
```

## 关键数据流

用户标注 → 生成矩形列表 → PATCH API → 后端计算 percentage → 更新 DB → 前端刷新原页面饼图/数据