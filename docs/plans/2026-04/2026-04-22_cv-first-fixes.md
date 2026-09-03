---
name: cv-first-fixes
overview: 修复CV-First架构的三个问题：标注图增加蓝色绘画区域叠加、保护手动编辑数据不被覆盖、手动保存接口标记user_edited
todos:
  - id: worker-blue-overlay
    content: tubi_worker.py 标注图绘制逻辑增加绘画区域蓝色叠加
    status: pending
  - id: worker-protect-edits
    content: tubi_worker.py 增加 user_edited 检测逻辑保护手动编辑数据
    status: pending
  - id: api-user-edited-flag
    content: tubi.py update_regions_manual 接口保存时注入 user_edited 标记
    status: pending
  - id: cleanup-temp-script
    content: 删除 backend/check_coords.py 临时诊断脚本
    status: pending
  - id: verify-fix
    content: 验证修复效果：重新分析测试图片并检查标注图与数据库regions
    status: pending
    dependencies:
      - worker-blue-overlay
      - worker-protect-edits
      - api-user-edited-flag
---

## Product Overview

完成CV-First架构集成后的三个关键修复任务，解决用户反馈的标注图颜色缺失、手动编辑页数据混乱（已定位根因）、以及手动编辑数据被覆盖的问题。

## User Requirements

用户明确要求解决以下三个问题：

1. **标注图颜色问题**：生成的标注图中绘画区域应显示为蓝色，当前只显示红色题跋区域，导致用户误以为绘画区域被算进了题跋区域。
2. **手动编辑页数据混乱**：打开 `/annotate/` 页面时，区域数据显示为"乱的"。根因已定位：`_mask_to_polygon_regions` 生成了过多碎片多边形（20+20+9=49个），前端SVG渲染拥挤导致视觉混乱。此问题已在 `integration.py` 中通过增加闭运算合并碎片、提高面积门槛、降低 `max_regions` 修复。
3. **数据安全要求**：重新分析时绝对不能覆盖用户之前手动编辑过的 `/annotate/` 数据。需要在手动保存时注入 `user_edited` 标记，并在重新分析时检测该标记以跳过覆盖。

## Core Features

- 标注图三色绘制：题跋（红）+ 绘画（蓝）+ OCR框
- Regions去碎片化：减少CV-First生成的多边形数量
- 手动编辑数据保护：`user_edited` 标记机制

## Tech Stack Selection

- **Backend**: Python + FastAPI + OpenCV + SQLAlchemy
- **Frontend**: Vue 3 + SVG (已有 `InscriptionAnnotator.vue`)
- **Database**: SQLite (JSON字段存储regions)

## Implementation Approach

### 1. 标注图增加绘画区域蓝色叠加

在 `tubi_worker.py` 第422-465行的 OpenCV 标注图绘制逻辑中，于红色题跋叠加之前增加绘画区域的蓝色叠加绘制。使用 `regions_to_mask` 从 `regions["painting_regions"]` 生成 painting_mask，然后用 `cv2.addWeighted` + `cv2.copyTo` 实现蓝色半透明叠加。

### 2. 保护已有手动编辑的 regions

在 `tubi_worker.py` 第467行 `db_analysis.regions = regions` 之前，增加检测逻辑：

- 读取现有 `db_analysis.regions`
- 检查其中是否存在 `_meta.user_edited = True` 标记
- 如果存在，跳过覆盖，仅更新 `_meta` 中的分析元信息（如 `cv_first_group`, `confidence` 等）

### 3. 手动保存接口注入 `user_edited` 标记

在 `backend/app/api/tubi.py` 的 `update_regions_manual` 接口（第2481行）中，保存 `regions_dict` 时注入 `_meta: {"user_edited": True}` 标记，使后续重新分析能够识别这是用户手动编辑的数据。

### 4. 清理临时脚本

删除 `backend/check_coords.py` 临时诊断脚本。

## Implementation Notes

- **坐标安全**：`integration.py` 中的 `_scale_regions_to_original` 逻辑已验证正确（scale=预处理尺寸/原始尺寸，坐标除以scale放大回原始尺寸）。通过 `check_coords.py` 验证：1089x4310图像的region坐标完全在图像范围内。
- **数据兼容性**：`regions` 字段为JSON类型，直接存dict。`_meta` 字段不会被前端 `InscriptionAnnotator.vue` 渲染，因此不会影响编辑体验。
- **Blast radius控制**：`user_edited` 标记机制是增量添加的，不影响未标记的旧数据（旧数据会被正常覆盖，符合现有行为）。只有手动保存后的数据才会被保护。
- **Performance**：闭运算和面积过滤在预处理图像（最大2048px长边）上执行，计算开销可忽略。

## Architecture Design

无需新架构，仅修改现有流程中的三个节点：

1. **`integration.py`**：已修改 `_mask_to_polygon_regions`（闭运算+提高门槛+max_regions=5/3）
2. **`tubi_worker.py`**：标注图绘制节点 + regions写库节点
3. **`tubi.py`**：`update_regions_manual` API节点

## Agent Extensions

无需使用外部扩展。本任务为代码修复，修改范围已明确。