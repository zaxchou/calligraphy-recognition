---
name: tubi-manual-two-regions
overview: 简化方案：InscriptionAnnotator 支持同时标注题跋和绘画两个区域，留白自动计算为剩余部分，生成三色标注图。
todos:
  - id: frontend-add-region-type
    content: "[前端] InscriptionAnnotator.vue 添加区域类型切换功能（题跋/绘画按钮），polygons 数据结构支持类型标记"
    status: completed
  - id: frontend-three-colors
    content: "[前端] 根据区域类型显示不同颜色（题跋红/绘画蓝），保存时传递类型信息，成功后跳转到分析页面"
    status: completed
    dependencies:
      - frontend-add-region-type
  - id: backend-draw-three-colors
    content: "[后端] tubi.py 新增 draw_all_regions_image() 函数，使用 cv2 绘制红/蓝/灰三色区域标注图"
    status: completed
  - id: backend-handle-types
    content: "[后端] 修改 update_regions_manual()，根据 region.type 分别处理 inscription/painting，调用 draw_all_regions_image()"
    status: completed
    dependencies:
      - backend-draw-three-colors
---

## 用户需求

修改手动标注流程，在 InscriptionAnnotator.vue 页面同时支持手动画出题跋区域和绘画区域：

1. 工具栏添加区域类型切换（题跋/绘画）
2. 题跋区域用红色显示，绘画区域用蓝色显示
3. 留白面积自动计算（100% - 题跋% - 绘画%）
4. 后端生成三色标注图（红/蓝/灰）
5. 保存后跳转到分析页面展示结果

## 现状分析

**当前 InscriptionAnnotator.vue：**

- 只支持一种区域类型（默认作为 inscription_regions）
- polygons 数组只存储顶点坐标，没有类型标记
- 保存时发送 `{regions: [{x1,y1,x2,y2}, ...]}`，全部归为 inscription_regions

**当前后端 PATCH /{id}/regions：**

- `RegionData` 模型已有 `type` 字段（默认 "inscription"）
- `update_regions_manual()` 将所有 regions 放入 `inscription_regions`
- `painting_regions` 和 `blank_regions` 为空
- `draw_annotated_image()` 只绘制红色题跋区域

## 核心功能

1. **前端**：添加区域类型切换，polygons 标记类型，保存时传递类型信息
2. **后端**：根据类型分别存入 inscription_regions/painting_regions，自动生成 blank_regions（留白 = 总面积 - 题跋 - 绘画）
3. **后端**：绘制三色标注图（题跋红/绘画蓝/留白灰）
4. **前端**：保存成功后跳转到 `/tubi/{imageId}` 展示分析结果

## 技术方案

### 前端修改（InscriptionAnnotator.vue）

**数据结构变更：**

```javascript
// 原：polygons = [[{x,y},...], ...]
// 新：polygons = [{type: 'inscription'|'painting', points: [{x,y},...]}, ...]
```

**新增功能：**

1. 工具栏添加区域类型选择器（题跋/绘画切换按钮）
2. `currentPolyType` 响应式变量记录当前绘制类型
3. 多边形根据类型显示不同颜色（红色/蓝色）
4. 保存时传递 `{regions: [{type, x1, y1, x2, y2}, ...]}`
5. 保存成功后 `router.push('/tubi/' + imageId)`

### 后端修改（tubi.py）

**修改 `update_regions_manual()`：**

1. 根据 `region.type` 分别放入 `inscription_regions` 或 `painting_regions`
2. `blank_regions` 保持为空（由 `calculate_area_stats_fillpoly` 自动计算留白面积）
3. 调用 `draw_all_regions_image()` 生成三色标注图

**新增 `draw_all_regions_image()`：**

- 使用 OpenCV 读取原图
- 创建三个 mask（inscription/painting/blank）
- 使用 `cv2.addWeighted` 叠加颜色：
- 题跋：红色 (BGR: 60, 60, 220)，透明度 50%
- 绘画：蓝色 (BGR: 220, 100, 50)，透明度 50%
- 留白：灰色 (BGR: 180, 180, 180)，透明度 30%
- 保存为 `annotated_{image_id}.jpg`

## 目录结构

```
backend/app/api/
└── tubi.py              # [MODIFY] update_regions_manual, 新增 draw_all_regions_image

frontend/src/views/
└── InscriptionAnnotator.vue   # [MODIFY] 添加区域类型切换、三色显示、保存跳转
```