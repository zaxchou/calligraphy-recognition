---
name: tubi-manual-annotation-v9-flow
overview: 手动标注保存后，自动调用 V9 分析流程计算 position_analysis、painting/blank 区域，并生成完整三色标注图，同时让 TubiAnalysis 页面保存后自动刷新展示结果。
todos:
  - id: backend-add-draw-all-regions
    content: "[后端] 在 tubi.py 新增 draw_all_regions_image() 函数，使用 cv2 绘制红/蓝/灰三色区域标注图"
    status: pending
  - id: backend-modify-update-regions
    content: "[后端] 修改 update_regions_manual()，调用 analyze_inscription_position() 保存 position_analysis，调用 draw_all_regions_image()"
    status: pending
    dependencies:
      - backend-add-draw-all-regions
  - id: frontend-modify-save-redirect
    content: "[前端] 修改 InscriptionAnnotator.vue 的 saveRegions()，保存成功后跳转到 /tubi/{imageId} 分析页面"
    status: pending
---

## 用户需求

在 `InscriptionAnnotator.vue` 手动标注题跋区域并保存后：

1. 自动调用 V9 流程计算剩余绘画区域和留白面积
2. 生成面积占比示意图（三色：题跋红/绘画蓝/留白灰）
3. 更新右侧"题跋空间分布分析"面板（形式类型、覆盖率、布局示意图）

访问 `http://localhost:3000/#/tubi/e2981a8b-0873-4b10-be4a-5577cd3564db` 时需看到完整分析结果。

## 现状分析

### 当前手动标注保存流程

- 前端 `InscriptionAnnotator.vue` 第521-557行 → `saveRegions()` 发送 PATCH 到 `/api/v1/tubi/{id}/regions`
- 后端 `tubi.py` 第1208-1286行 `update_regions_manual()`：
- 调用 `calculate_area_stats_fillpoly()` 计算面积统计 ✅ 已有
- 调用 `draw_annotated_image()` 生成标注图（仅题跋红色）✅ 已有
- **缺少** `analyze_inscription_position()` 调用 → `position_analysis` 为空 ❌
- **缺少** 保存绘画区域和留白区域到 regions（目前只有 `inscription_regions`）❌
- 返回值包含 `annotated_image_url` ✅ 已有

### TubiAnalysis 展示流程

- `tubiApi.getAnalysisResult(imageId)` → `GET /api/v1/tubi/result/{image_id}` 返回完整数据含 `position_analysis`
- "题跋空间分布分析" 面板读取 `positionAnalysis` 和 `diagramRegions` 展示形式类型/覆盖率/布局示意图
- 饼图读取 `areaStats`（inscription/painting/blank 三项）

### 差距

1. **后端**：手动标注保存后不调用 `analyze_inscription_position()`，导致 `position_analysis` 为空，右侧面板无数据
2. **标注图**：当前只画题跋（红色），需要画全部三种区域
3. **前端**：保存成功后直接 `router.back()` 返回，无法看到更新后的分析面板

## 核心功能

### 1. 后端 - 增强手动标注保存流程

在 `update_regions_manual()` 中，保存数据后增加：

- 调用 `analyze_inscription_position()` 计算位置分析数据（形式类型、覆盖率、重叠率、边距等）
- 保存 `position_analysis` 到数据库
- 扩展标注图绘制：支持题跋（红）、绘画（蓝）、留白（灰）三种区域颜色

### 2. 前端 - 保存后跳转到分析页面

`saveRegions()` 成功后，跳转到 `/tubi/{imageId}` 分析页面，自动加载并展示：

- 饼图（面积占比）
- 题跋空间分布分析（形式类型、覆盖率、布局示意图）
- 标注图预览

## 技术方案

### 后端修改（tubi.py）

#### A. 新增 `draw_all_regions_image()` 函数

在 `draw_annotated_image()` 之后新增，使用 cv2 绘制三种区域：

- 题跋：红色半透明 (220, 50, 50, 50%透明度)
- 绘画：蓝色半透明 (50, 100, 220, 50%透明度)
- 留白：灰色半透明 (180, 180, 180, 30%透明度)

#### B. 修改 `update_regions_manual()` 函数

在现有代码后追加：

```python
# 1. 调用位置分析（analyze_inscription_position）
try:
    position_analysis = analyze_inscription_position(
        regions_dict, width, height, 
        image_path=get_full_file_path(db_analysis.filepath, PROJECT_ROOT)
    )
    db_analysis.position_analysis = position_analysis
except Exception as e:
    logger.error("位置分析失败: %s", e)

# 2. 生成三色标注图（替换仅题跋的版本）
try:
    annotated_path = os.path.join(ANNOTATED_DIR, f"annotated_{db_analysis.image_id}.jpg")
    draw_all_regions_image(...)
    db_analysis.annotated_image_path = f"data/annotated/annotated_{db_analysis.image_id}.jpg"
except Exception as e:
    logger.error("生成标注图失败: %s", e)

# 3. 更新 status
db_analysis.status = "analyzed"
```

### 前端修改（InscriptionAnnotator.vue）

#### A. `saveRegions()` 函数修改

保存成功后，跳转到分析页面：

```javascript
// 原来
ElMessage.success('标注已保存')
router.back()

// 改为
ElMessage.success('标注已保存，正在加载分析结果...')
router.push(`/tubi/${route.params.id}`)
```

## 目录结构

```
backend/app/api/
└── tubi.py              # [MODIFY] update_regions_manual, 新增 draw_all_regions_image

frontend/src/views/
└── InscriptionAnnotator.vue   # [MODIFY] saveRegions 跳转逻辑
```

## 实现步骤

1. **[后端] 新增 `draw_all_regions_image()` 函数** — 在 tubi.py 中，使用 cv2 绘制三种区域（红/蓝/灰）到原图上，保存为标注图
2. **[后端] 修改 `update_regions_manual()`** — 调用 `analyze_inscription_position()` 保存 `position_analysis`，调用 `draw_all_regions_image()` 生成三色标注图
3. **[前端] 修改 `saveRegions()`** — 保存成功后跳转到 `/tubi/{imageId}` 分析页面

## 技术选型

- 后端：Python + FastAPI（现有）
- 前端：Vue 3 + TypeScript + Element Plus（现有）
- 绘图：PIL/Pillow（现有） + OpenCV（已有依赖）

## 实现方案

### 后端核心修改

**新增 `draw_all_regions_image()` 函数（tubi.py）**：

- 使用 cv2.imread 读取原图
- 创建三个独立的 mask（inscription/painting/blank）
- 使用 cv2.addWeighted 分别绘制三种颜色叠加
- 按优先级（留白→绘画→题跋）叠加，后绘制覆盖先绘制
- 保存为 `annotated_{image_id}.jpg`

**修改 `update_regions_manual()`**：

1. 保存 regions_dict 后，调用 `analyze_inscription_position()`
2. 将返回的 `position_analysis` JSON 保存到 `db_analysis.position_analysis`
3. 调用 `draw_all_regions_image()` 生成三色标注图
4. 更新 `db_analysis.status = "analyzed"`
5. commit 后返回完整的分析数据

### 前端核心修改

**修改 `InscriptionAnnotator.vue` 的 `saveRegions()`**：

- fetch 保存成功后，不 `router.back()`，改为 `router.push('/tubi/' + imageId)`
- 这会自动加载分析结果页面，包含饼图和位置分析面板

## 注意事项

- `analyze_inscription_position()` 是纯算法函数，不需要 AI 调用，可同步执行
- `draw_all_regions_image()` 需要 `import cv2`，需确保依赖已安装
- 前端跳转后 TubiAnalysis 页面会自动调用 `getAnalysisResult` 获取最新数据