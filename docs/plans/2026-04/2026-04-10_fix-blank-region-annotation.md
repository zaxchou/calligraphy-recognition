---
name: fix-blank-region-annotation
overview: 修复标注图中留白区域不显示的问题：让 draw_annotated_image 函数自动计算留白区域（100% - 绘画 - 题跋），而不依赖 LLM 返回的 blank_regions
todos:
  - id: fix-draw-annotated
    content: 修改 draw_annotated_image() 用 numpy mask 自动计算并绘制留白区域
    status: completed
  - id: reanalyze-verify
    content: 重置 217c378e 图像并重新分析，验证标注图三种颜色正确显示
    status: in_progress
    dependencies:
      - fix-draw-annotated
---

## 用户需求

标注图（annotated_*.jpg）中留白区域没有正确显示，整张图看起来全是绘画区域。用户要求：

1. 先计算绘画面积（绘画多边形）
2. 再计算题跋面积（题跋多边形）
3. 留白 = 100% - 绘画% - 题跋%，自动将留白区域用淡绿色画出来

## 问题根因

- `draw_annotated_image()` 只画 LLM 返回的 `blank_regions`，但 LLM 返回的 blank_regions points 为空
- mask 路径（tubi_worker.py）已正确计算留白 = 全图 - 绘画 - 题跋，但 `draw_annotated_image` 路径没有这个逻辑
- 当 GrabCut 关闭时走 `draw_annotated_image` 路径，留白区域无法显示

## 修复方案

修改 `draw_annotated_image()` 函数，不再依赖 LLM 的 `blank_regions`，改为自动计算：用 numpy 创建绘画和题跋的 mask，留白 = 全图 - 绘画 mask - 题跋 mask，然后三类区域分别着色绘制

## Tech Stack

- Python + PIL + numpy（项目已有依赖）
- 不引入新依赖

## Implementation Approach

修改 `draw_annotated_image()` 函数（`backend/app/api/tubi.py` 第210-316行）：

1. 将绘画和题跋的多边形转为 numpy mask（使用 PIL 的 `ImageDraw.polygon` 在黑白图上绘制）
2. 留白 mask = 全白 - 绘画 mask - 题跋 mask
3. 用三个独立的 RGBA overlay 层分别绘制三类区域的半透明着色
4. 不再使用 `blank_regions` 数据

### 为什么这样改

- 与 tubi_worker.py 中 mask 路径的逻辑一致（全图 - 绘画 - 题跋 = 留白）
- numpy 数组操作高效，不增加额外依赖
- 保持 PIL 风格不引入 cv2 到 tubi.py

## Implementation Notes

- 绘画和题跋的多边形坐标是绝对像素值（已在之前处理中转换），绘制时需注意缩放
- 留白区域在边缘可能和绘画/题跋有像素级重叠，需确保互斥（题跋优先级最高）
- `draw_region_fast` 中 `scale_x/scale_y` 的作用域问题（使用 `locals()` 判断），需要保留原有缩放逻辑
- 透明度需保持与现有配色一致：绘画蓝色(74,144,226,80)，题跋红色(220,50,50,80)，留白淡绿色(100,180,100,50)

## Directory Structure

```
backend/
├── app/
│   └── api/
│       └── tubi.py  # [MODIFY] 修改 draw_annotated_image() 函数，用 numpy mask 自动计算留白区域
```

## Key Code Structures

修改后的 `draw_annotated_image` 核心逻辑：

```python
import numpy as np

# 在函数内：
# 1. 创建缩放后的绘画/题跋 mask
paint_mask_arr = np.zeros((img_h, img_w), dtype=np.uint8)
insc_mask_arr = np.zeros((img_h, img_w), dtype=np.uint8)

# 2. 用 PIL ImageDraw 在 mask 上绘制多边形
mask_img = Image.new('L', (img_w, img_h), 0)
mask_draw = ImageDraw.Draw(mask_img)
# 绘制绘画多边形 → paint_mask_arr
# 绘制题跋多边形 → insc_mask_arr

# 3. 题跋优先，从绘画中扣除重叠
paint_mask_arr = np.where(insc_mask_arr > 0, 0, paint_mask_arr)

# 4. 留白 = 全图 - 绘画 - 题跋
blank_mask_arr = np.where((paint_mask_arr == 0) & (insc_mask_arr == 0), 255, 0)

# 5. 分别创建三个 overlay 层着色
```