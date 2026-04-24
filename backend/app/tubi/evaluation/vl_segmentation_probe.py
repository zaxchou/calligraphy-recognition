"""
VL 语义分割探针 (D2 方案验证)

用改进版 prompt 调用 qwen3-vl-plus，测试其直接输出题跋/绘画区域坐标的能力。
与 Ground Truth 做 IoU 对比，评估纯 VL 分割的可行性。

用法:
    cd backend
    python -m app.tubi.evaluation.vl_segmentation_probe

输出:
    data/evaluation_reports/vl_probe/{timestamp}/
    - report.json: 详细结果
    - vis_*.jpg: 可视化对比图
"""

import json
import os
import time
import base64
import io
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# 加载 .env
from dotenv import load_dotenv

# 找到项目根目录的 .env
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_BASE, ".env"))

import cv2
import numpy as np
from PIL import Image
import httpx

from app.tubi.evaluation.gt_loader import load_ground_truth, GroundTruthRecord
from app.tubi.evaluation.iou_evaluator import polygons_to_mask, compute_iou, compute_class_iou
from app.tubi.evaluation import vl_cv_hybrid
from app.tubi.evaluation import grabcut_refiner


# ── 配置 ────────────────────────────────────────────────────────────────────
MAX_SIDE = 2048  # 与现有系统一致
QUALITY = 85

# API 配置（从环境变量读取，与现有系统一致）
API_KEY = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("QWEN_VL_PROBE_MODEL", "qwen3-vl-plus")  # 可覆盖为更强的模型

# 报告输出目录
REPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "evaluation_reports", "vl_probe"
)


# ── 图像编码 ────────────────────────────────────────────────────────────────
def encode_image(image_path: str, max_side: int = MAX_SIDE, quality: int = QUALITY) -> Tuple[str, float]:
    """将图片编码为 base64，返回 (base64_str, scale_ratio)"""
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        scale_ratio = 1.0
        longest = max(w, h)
        if longest > max_side:
            scale_ratio = max_side / float(longest)
            img = img.resize((int(w * scale_ratio), int(h * scale_ratio)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode(), scale_ratio


# ── Prompt 设计 ─────────────────────────────────────────────────────────────

def build_probe_prompt(image_width: int, image_height: int, use_polygon: bool = True) -> str:
    """标准 Prompt（无 few-shot）"""
    coord_example = '{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "区域描述"}'
    coord_rule = f"""- 坐标使用相对值（0-1之间），基于图像尺寸 {image_width}x{image_height}
- x1,y1 是左上角，x2,y2 是右下角"""

    return f"""你是一位专业的中国书画鉴定专家，精通明清书画的题跋与绘画分析。

请仔细分析这张图片，完成以下任务：

## 任务一：视觉描述（必须先完成）
请先详细描述：
1. 图片中有几个题跋（书法文字）区域？分别位于什么位置？内容大致是什么？
2. 图片中有几个绘画区域？分别画的是什么？位于什么位置？
3. 有没有印章？位于哪里？

## 任务二：区域标注（基于上述描述）
请输出以下JSON格式数据，标注所有题跋区域和绘画区域：

```json
{{
    "description": "你对画面的整体描述",
    "inscription_regions": [
        {coord_example}
    ],
    "painting_regions": [
        {coord_example}
    ]
}}
```

## 关键规则
{coord_rule}
- **必须覆盖所有题跋文字和主要绘画内容，不能遗漏**
- 如果题跋有多行/多列，请分别标注每一块的区域
- 不要输出任何JSON之外的内容
- 每个区域必须附带简短的 note 说明这是什么"""


def build_probe_prompt_v1_layout_cot(image_width: int, image_height: int) -> str:
    """
    V1: Layout-aware Chain-of-Thought
    要求模型先判断布局类型，再逐步推理区域划分
    """
    return f"""你是一位专业的中国书画鉴定专家，精通明清书画的题跋与绘画分析。

请按以下步骤分析这张图片：

## 步骤一：判断画面布局类型
先判断这幅画属于哪种布局（选择最符合的一项）：
- **立轴**：竖长条，高度明显大于宽度，题跋通常在上方或侧面
- **横幅**：横长条，宽度明显大于高度，题跋通常在上方或两侧
- **横卷/手卷**：超宽横幅，有引首、拖尾题跋，画面连续展开
- **册页**：方形或接近方形，画面独立完整
- **扇面**：扇形或圆形构图
- **其他**：不符合以上类型

## 步骤二：识别所有视觉元素
列出画面中所有元素：
1. **题跋区域**：有几处书法文字？每处位置（上/下/左/右/中）？排列方式（竖排/横排）？
2. **绘画区域**：主体绘画在哪里？有没有分散的局部绘画（如边角补景）？
3. **印章**：引首章、款印、收藏印的位置。
4. **留白**：题跋与绘画之间的空白区域宽度大约占画面的百分之几？

## 步骤三：确定区域划分策略
根据布局类型和元素分布，决定如何划分区域：
- 如果多处题跋**紧密相邻**（间距 < 画面宽度的 5%），应合并为一个题跋区域。
- 如果题跋与绘画之间有**明显留白分界线**（留白宽度 ≥ 画面尺寸的 5%），应分为两个独立区域。
- 如果绘画主体旁边有**小幅补景**（如边角花草）且与主体连续，可合并为一个绘画区域。
- **边界处理**：bbox 应包含内容的最外边缘，并向外扩展 2-3% 以包含自然留白。

## 步骤四：输出区域标注
基于以上分析，输出 JSON 格式坐标。坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

```json
{{
    "description": "整体描述，包含布局类型和画面内容概述",
    "layout_type": "立轴/横幅/横卷/册页/扇面/其他",
    "inscription_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "位置+内容简述，说明为何这样划分"}}
    ],
    "painting_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "位置+内容简述"}}
    ]
}}
```

## 关键规则
- x1,y1 是左上角，x2,y2 是右下角
- **必须覆盖所有题跋文字和主要绘画内容**
- 题跋区域应尽量合并（紧密相邻的多列题跋合并为一个区域）
- bbox 边界应包含内容外边缘 + 2-3% 的自然留白
- 不要输出 JSON 之外的内容"""


def build_probe_prompt_v2_rule_based(image_width: int, image_height: int) -> str:
    """
    V2: Rule-based，给出详细的数值判定规则
    """
    return f"""你是一位专业的中国书画鉴定专家。请严格按以下规则分析这张图片并标注区域。

## 判定规则

### 1. 题跋区域判定
符合以下全部条件的区域应标记为题跋：
- 区域内有书法文字（行书/草书/楷书/隶书等）
- 文字有行列结构（竖排或横排）
- 通常位于画面边缘（上、下、左、右），但也可位于画面中空白处

### 2. 绘画区域判定
符合以下条件的区域应标记为绘画：
- 区域内有图像内容（花鸟、山水、人物、器物等）
- 占据画面主体或显著局部
- 以笔墨/色彩绘制，非文字

### 3. 区域合并规则（必须遵守）
- **题跋合并**：如果两处题跋之间的留白间距 < 画面宽度的 **5%**，必须合并为一个题跋区域。
- **绘画合并**：如果主体绘画与边角补景之间连续无分界，合并为一个绘画区域。
- **不要过度拆分**：不要把一列竖排题跋中的每行拆成独立区域。

### 4. 边界规则（必须遵守）
- bbox 外边界应覆盖内容的**最外像素**，并向外扩展 **2-3%** 以包含自然留白。
- 不要过紧（遗漏留白）也不要过松（包含大面积无关背景）。
- 题跋 bbox 的上边界应在第一行文字上方 2-3%，下边界应在最后一行文字下方 2-3%。

### 5. 重叠检查
- 题跋区域和绘画区域之间**不应有显著重叠**（重叠面积 < 各自面积的 10% 可接受）。
- 如果检测到明显重叠，请调整边界使两者分开。

## 输出格式
坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

```json
{{
    "description": "画面整体描述",
    "inscription_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "描述及判定依据"}}
    ],
    "painting_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "描述及判定依据"}}
    ]
}}
```

## 关键规则
- x1,y1 是左上角，x2,y2 是右下角
- 每个区域必须附带 note，说明判定依据
- 不要输出 JSON 之外的内容"""


def build_probe_prompt_v3_self_critique(image_width: int, image_height: int) -> str:
    """
    V3: Self-critique，要求模型自检后修正
    """
    return f"""你是一位专业的中国书画鉴定专家。请分析这张图片并标注题跋/绘画区域。

## 分析任务

### 第一轮：初步标注
先描述画面内容（布局、题跋位置、绘画内容、印章），然后初步标注区域坐标。

### 第二轮：自我检查（必须完成）
对初步标注进行自我检查，回答以下问题：

1. **遗漏检查**：是否遗漏了任何题跋或绘画区域？
   - 检查画面四个边缘和角落是否有小字题跋或局部绘画被忽略。
   - 检查是否有印章旁边的款识被遗漏。

2. **合并检查**：题跋区域是否拆分过度？
   - 如果相邻题跋间距很小（< 画面宽度的 5%），应合并。
   - 不要把一列竖排文字拆成多个区域。

3. **边界检查**：每个 bbox 边界是否合理？
   - 边界是否过紧（遗漏了文字/图像边缘）？
   - 边界是否过松（包含了大量无关留白或背景）？
   - 边界应覆盖内容外边缘 + 2-3% 自然留白。

4. **重叠检查**：题跋区域和绘画区域是否有显著重叠？
   - 如果有，请调整边界分开两者。

5. **布局适配**：标注是否符合画面的实际布局？
   - 立轴：题跋通常在上方，绘画在下方。
   - 横幅：题跋通常在上方或一侧，绘画在中部。
   - 横卷：可能有引首题跋和拖尾题跋，注意别遗漏。

### 第三轮：输出修正后的最终标注
基于自我检查的结果，输出修正后的 JSON。如果检查通过无需修改，直接输出初步标注即可。

## 输出格式
坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

```json
{{
    "description": "整体描述",
    "inscription_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "描述"}}
    ],
    "painting_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "描述"}}
    ]
}}
```

## 关键规则
- x1,y1 是左上角，x2,y2 是右下角
- 题跋尽量合并，不要过度拆分
- bbox 包含内容外边缘 + 2-3% 留白
- 不要输出 JSON 之外的内容"""


def build_probe_prompt_v3_polygon(image_width: int, image_height: int) -> str:
    """
    V3-Polygon: Self-critique + 多边形输出（替代矩形框）

    核心改进：用多边形顶点描述区域轮廓，比矩形框更精确，减少四个直角包含的无关像素。
    """
    return f"""你是一位专业的中国书画鉴定专家。请分析这张图片并标注题跋/绘画区域。

## 分析任务

### 第一轮：初步标注
先描述画面内容（布局、题跋位置、绘画内容、印章），然后初步标注区域坐标。

### 第二轮：自我检查（必须完成）
对初步标注进行自我检查，回答以下问题：

1. **遗漏检查**：是否遗漏了任何题跋或绘画区域？
   - 检查画面四个边缘和角落是否有小字题跋或局部绘画被忽略。
   - 检查是否有印章旁边的款识被遗漏。

2. **合并检查**：题跋区域是否拆分过度？
   - 如果相邻题跋间距很小（< 画面宽度的 5%），应合并。
   - 不要把一列竖排文字拆成多个区域。

3. **边界检查**：每个多边形边界是否合理？
   - 边界是否过紧（遗漏了文字/图像边缘）？
   - 边界是否过松（包含了大量无关留白或背景）？
   - 边界应覆盖内容外边缘 + 2-3% 自然留白。
   - **多边形顶点应落在区域轮廓的关键转折处**，不要在直线段上浪费顶点。

4. **重叠检查**：题跋区域和绘画区域是否有显著重叠？
   - 如果有，请调整边界分开两者。

5. **布局适配**：标注是否符合画面的实际布局？
   - 立轴：题跋通常在上方，绘画在下方。
   - 横幅：题跋通常在上方或一侧，绘画在中部。
   - 横卷：可能有引首题跋和拖尾题跋，注意别遗漏。

### 第三轮：输出修正后的最终标注
基于自我检查的结果，输出修正后的 JSON。

## 输出格式（多边形，非矩形框）
坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

**非常重要**：每个区域用多边形描述，提供 **4-8 个顶点**（按顺时针顺序）。
- 顶点应放在区域轮廓的**关键转折点**（拐角、弯曲处）
- 如果区域接近矩形，用4个顶点即可
- 如果区域有斜边或不规则轮廓，用6-8个顶点
- **不要输出矩形框的 x1,y1,x2,y2，必须用 points 数组**

```json
{{
    "description": "整体描述",
    "inscription_regions": [
        {{
            "points": [
                {{"x": 0.10, "y": 0.05}},
                {{"x": 0.30, "y": 0.05}},
                {{"x": 0.30, "y": 0.50}},
                {{"x": 0.10, "y": 0.50}}
            ],
            "note": "描述"
        }}
    ],
    "painting_regions": [
        {{
            "points": [
                {{"x": 0.05, "y": 0.55}},
                {{"x": 0.85, "y": 0.50}},
                {{"x": 0.90, "y": 0.95}},
                {{"x": 0.05, "y": 0.95}}
            ],
            "note": "描述"
        }}
    ]
}}
```

## 关键规则
- **必须使用 points 数组，不要用 x1,y1,x2,y2**
- 顶点按**顺时针**顺序排列
- 4-8个顶点即可，不要过多（减少格式错误风险）
- 题跋尽量合并，不要过度拆分
- 多边形包含内容外边缘 + 2-3% 留白
- 不要输出 JSON 之外的内容"""


def build_probe_prompt_inscription_only(image_width: int, image_height: int) -> str:
    """
    分层分析 - 题跋层：只识别题跋区域，完全忽略绘画内容
    """
    return f"""你是一位专业的中国书画鉴定专家。你的任务是**只识别这张图片中的题跋（书法文字）区域**。

## 任务说明
- **只关注题跋**：书法文字、款识、印章旁的小字都属于题跋。
- **完全忽略绘画内容**：不要分析也不要输出任何绘画区域的信息。
- **只输出题跋区域的坐标**。

## 分析步骤

### 第一步：识别所有题跋元素
仔细检查画面，找出所有包含书法文字的区域：
1. 主要题跋：大幅诗、文、题记
2. 款识：作者署名、年月、地点
3. 小字补跋：边角补充说明
4. 引首题字：横卷/手卷开头的引首

### 第二步：确定题跋区域
根据识别的元素，确定题跋区域：
- 如果多处题跋**紧密相邻**（间距 < 画面宽度的 5%），**合并为一个题跋区域**。
- 不要把一列竖排文字拆成多个独立区域。
- 题跋 bbox 应覆盖全部题跋文字的最外边缘，并向外扩展 2-3% 以包含自然留白。

### 第三步：自我检查
- 是否遗漏了任何题跋？（检查四边和角落）
- 是否拆分过度？（相邻题跋应合并）
- 边界是否过紧或过松？

## 输出格式
坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

```json
{{
    "description": "题跋内容描述",
    "inscription_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "位置+内容简述"}}
    ]
}}
```

## 关键规则
- x1,y1 是左上角，x2,y2 是右下角
- **只输出 inscription_regions，不要输出 painting_regions**
- 题跋尽量合并，不要过度拆分
- bbox 包含文字外边缘 + 2-3% 留白
- 不要输出 JSON 之外的内容"""


def build_probe_prompt_painting_only(image_width: int, image_height: int) -> str:
    """
    分层分析 - 绘画层：只识别绘画区域，完全忽略题跋内容
    """
    return f"""你是一位专业的中国书画鉴定专家。你的任务是**只识别这张图片中的绘画区域**。

## 任务说明
- **只关注绘画**：花鸟、山水、人物、器物等图像内容。
- **完全忽略题跋**：不要分析也不要输出任何题跋区域的信息。
- **只输出绘画区域的坐标**。

## 分析步骤

### 第一步：识别所有绘画元素
仔细检查画面，找出所有图像内容：
1. 主体绘画：画面主要物象（如荷花、松石、花鸟等）
2. 边角补景：主体旁边的局部景物（如坡石、小草、远树）
3. 背景渲染：淡墨渲染的天空、水面、地面

### 第二步：确定绘画区域
根据识别的元素，确定绘画区域：
- 如果主体绘画与边角补景**连续无分界**，合并为一个绘画区域。
- 如果有**明显留白分界线**（留白宽度 ≥ 画面尺寸的 5%），分为两个独立区域。
- 绘画 bbox 应覆盖全部绘画内容的最外边缘，并向外扩展 2-3% 以包含自然留白。
- **不要包含题跋区域**：如果绘画 bbox 与题跋区域重叠，请缩小绘画 bbox 避开题跋。

### 第三步：自我检查
- 是否遗漏了任何局部绘画？（检查边角和背景）
- 是否包含了题跋或大面积无关空白？
- 边界是否过紧（遗漏绘画边缘）或过松（包含过多空白）？

## 输出格式
坐标为相对值（0-1），基于图像尺寸 {image_width}x{image_height}。

```json
{{
    "description": "绘画内容描述",
    "painting_regions": [
        {{"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.5, "note": "位置+内容简述"}}
    ]
}}
```

## 关键规则
- x1,y1 是左上角，x2,y2 是右下角
- **只输出 painting_regions，不要输出 inscription_regions**
- 绘画区域包含主体+连续补景，不过度拆分
- bbox 覆盖内容外边缘 + 2-3% 留白
- **严禁与题跋区域重叠**
- 不要输出 JSON 之外的内容"""


def build_fewshot_prompt(
    example_bboxes: Dict,
    target_width: int,
    target_height: int,
) -> str:
    """
    Few-shot Prompt：给 VL 看示例图+理想标注，让它学习输出精确 bbox
    """
    # 构建示例 JSON
    insc_examples = []
    for i, r in enumerate(example_bboxes.get("inscription_regions", [])):
        insc_examples.append(
            f'{{"x1": {r["x1"]:.4f}, "y1": {r["y1"]:.4f}, "x2": {r["x2"]:.4f}, "y2": {r["y2"]:.4f}, "note": "{r.get("note", f"题跋{i+1}")}"}}'
        )
    paint_examples = []
    for i, r in enumerate(example_bboxes.get("painting_regions", [])):
        paint_examples.append(
            f'{{"x1": {r["x1"]:.4f}, "y1": {r["y1"]:.4f}, "x2": {r["x2"]:.4f}, "y2": {r["y2"]:.4f}, "note": "{r.get("note", f"绘画{i+1}")}"}}'
        )

    return f"""你是一位专业的中国书画鉴定专家，精通明清书画的题跋与绘画分析。

## 示例
上面第一张图片是一张示例作品，其标注如下：

```json
{{
    "inscription_regions": [
        {', '.join(insc_examples) if insc_examples else '[]'}
    ],
    "painting_regions": [
        {', '.join(paint_examples) if paint_examples else '[]'}
    ]
}}
```

注意以上标注的**风格特点**：
- 题跋区域：**整体合并标注**，即使题跋有多列竖行，也作为一个完整区域覆盖全部题跋内容（包括列间留白）
- 绘画区域：覆盖主要绘画内容，**不过度扩展**到画面边缘的空白处
- bbox 是区域的**外接矩形**，包含内容及其周围的合理留白

## 任务
请对上面第二张图片做同样的标注，**严格遵循示例图的标注风格**：

1. 先描述画面内容（题跋数量位置、绘画内容、印章位置）
2. 输出JSON格式 bbox，坐标相对值（0-1），基于图像尺寸 {target_width}x{target_height}
3. **题跋区域必须整体合并**：如果有多列题跋，请合并为一个完整区域，不要拆分成多个小区域
4. **绘画区域覆盖主体内容即可**，不要扩展到画面边缘的空白
5. bbox 应包含内容及其周围的合理留白，不是最小外接矩形

输出格式：
```json
{{
    "description": "整体描述",
    "inscription_regions": [{{"x1":0.1,"y1":0.1,"x2":0.3,"y2":0.5,"note":"描述"}}],
    "painting_regions": [{{"x1":0.1,"y1":0.1,"x2":0.3,"y2":0.5,"note":"描述"}}]
}}
```
不要输出JSON之外的内容。"""


# ── 从 GT 多边形计算外接矩形 ─────────────────────────────────────────────────

def compute_gt_bboxes(record: GroundTruthRecord) -> Dict:
    """从 GT 多边形计算外接矩形 bbox"""
    w, h = record.width, record.height
    bboxes = {"inscription_regions": [], "painting_regions": []}

    for region_type in ["inscription_regions", "painting_regions"]:
        for poly in record.regions.get(region_type, []):
            pts = poly.get("points", [])
            if not pts:
                continue
            xs = [p["x"] for p in pts]
            ys = [p["y"] for p in pts]
            bboxes[region_type].append({
                "x1": min(xs),
                "y1": min(ys),
                "x2": max(xs),
                "y2": max(ys),
                "note": f"GT {region_type.replace('_', ' ')}",
            })

    return bboxes


# ── API 调用 ────────────────────────────────────────────────────────────────

def call_vl_segmentation(
    image_path: str,
    image_width: int,
    image_height: int,
    use_polygon: bool = True,
    fewshot_example: Optional[Tuple[str, Dict]] = None,
    prompt_version: str = "default",
    layer: str = "both",
) -> Dict:
    """
    调用 VL 模型进行分割

    Args:
        fewshot_example: (示例图路径, 示例bboxes字典) 或 None
        prompt_version: "default" | "v1_layout_cot" | "v2_rule_based" | "v3_self_critique"
        layer: "both" | "inscription" | "painting" — 分层分析模式
    """
    if not API_KEY:
        raise ValueError("QWEN_API_KEY or DASHSCOPE_API_KEY not set")

    target_b64, scale = encode_image(image_path)

    if fewshot_example:
        example_path, example_bboxes = fewshot_example
        example_b64, _ = encode_image(example_path)
        prompt = build_fewshot_prompt(example_bboxes, image_width, image_height)

        # Few-shot: 先传示例图+说明，再传目标图
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{example_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{target_b64}"}},
        ]
        print(f"INFO: Calling {MODEL} with few-shot (2 images)...")
    else:
        # 根据 prompt_version 和 layer 选择 prompt
        if layer == "inscription":
            prompt = build_probe_prompt_inscription_only(image_width, image_height)
            print(f"INFO: Calling {MODEL} for INSCRIPTION layer...")
        elif layer == "painting":
            prompt = build_probe_prompt_painting_only(image_width, image_height)
            print(f"INFO: Calling {MODEL} for PAINTING layer...")
        else:
            prompt_builders = {
                "default": build_probe_prompt,
                "v1_layout_cot": build_probe_prompt_v1_layout_cot,
                "v2_rule_based": build_probe_prompt_v2_rule_based,
                "v3_self_critique": build_probe_prompt_v3_self_critique,
                "v3_polygon": build_probe_prompt_v3_polygon,
            }
            builder = prompt_builders.get(prompt_version, build_probe_prompt)
            # 多边形版本自动设置 use_polygon=True
            if prompt_version == "v3_polygon":
                use_polygon = True
            prompt = builder(image_width, image_height)
            print(f"INFO: Calling {MODEL} for segmentation (prompt={prompt_version}, polygon={use_polygon})...")

        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{target_b64}"}},
        ]

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "max_tokens": 8192,
        "temperature": 0.2,
    }

    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
    elapsed = time.time() - t0

    content = result["choices"][0]["message"]["content"]
    print(f"INFO: API returned in {elapsed:.1f}s")

    parsed = _parse_vl_response(content)
    parsed["_raw_response"] = content
    parsed["_elapsed_sec"] = elapsed
    parsed["_scale_ratio"] = scale
    return parsed


def _parse_vl_response(content: str) -> Dict:
    """从 VL 返回的文本中提取 JSON"""
    import re

    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 尝试找最外层 {}
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start : end + 1]
        else:
            json_str = content

    try:
        data = json.loads(json_str)
        return {
            "success": True,
            "description": data.get("description", ""),
            "inscription_regions": data.get("inscription_regions", []),
            "painting_regions": data.get("painting_regions", []),
        }
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "inscription_regions": [],
            "painting_regions": [],
        }


# ── BBox → Mask ─────────────────────────────────────────────────────────────

def regions_to_mask(regions: List[Dict], width: int, height: int) -> np.ndarray:
    """将区域列表转为二值 mask，支持多边形(points)和矩形(x1,y1,x2,y2)"""
    mask = np.zeros((height, width), dtype=np.uint8)
    for r in regions:
        if "points" in r and r["points"]:
            # 多边形格式
            pts = []
            for pt in r["points"]:
                px = int(pt.get("x", 0) * width)
                py = int(pt.get("y", 0) * height)
                px = max(0, min(width - 1, px))
                py = max(0, min(height - 1, py))
                pts.append([px, py])
            if len(pts) >= 3:
                pts_array = np.array(pts, dtype=np.int32)
                cv2.fillPoly(mask, [pts_array], 255)
        elif "x1" in r:
            # 矩形 bbox 格式
            x1 = int(r["x1"] * width)
            y1 = int(r["y1"] * height)
            x2 = int(r["x2"] * width)
            y2 = int(r["y2"] * height)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = 255
    return mask


# ── 可视化 ───────────────────────────────────────────────────────────────────

def visualize_comparison(
    image_path: str,
    gt_record: GroundTruthRecord,
    pred_insc_mask: np.ndarray,
    pred_paint_mask: np.ndarray,
    iou_result: Dict,
    output_path: str,
):
    """生成 GT vs Pred 对比图（baseline 模式）"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"WARNING: Cannot read image {image_path}")
        return
    h, w = img.shape[:2]

    # GT masks
    gt_insc = polygons_to_mask(gt_record.regions.get("inscription_regions", []), w, h)
    gt_paint = polygons_to_mask(gt_record.regions.get("painting_regions", []), w, h)

    # 1. 原图
    vis_original = img.copy()

    # 2. GT 叠加（题跋=红，绘画=蓝）
    vis_gt = img.copy()
    vis_gt[gt_insc > 0] = vis_gt[gt_insc > 0] * 0.5 + np.array([0, 0, 255]) * 0.5
    vis_gt[gt_paint > 0] = vis_gt[gt_paint > 0] * 0.5 + np.array([255, 0, 0]) * 0.5

    # 3. Pred 叠加
    vis_pred = img.copy()
    vis_pred[pred_insc_mask > 0] = vis_pred[pred_insc_mask > 0] * 0.5 + np.array([0, 0, 255]) * 0.5
    vis_pred[pred_paint_mask > 0] = vis_pred[pred_paint_mask > 0] * 0.5 + np.array([255, 0, 0]) * 0.5

    # 4. 差异图
    vis_diff = img.copy()
    tp_insc = (gt_insc > 0) & (pred_insc_mask > 0)
    fn_insc = (gt_insc > 0) & (pred_insc_mask == 0)
    fp_insc = (gt_insc == 0) & (pred_insc_mask > 0)
    vis_diff[tp_insc] = [0, 255, 0]
    vis_diff[fn_insc] = [0, 255, 255]
    vis_diff[fp_insc] = [255, 0, 255]

    top = np.hstack([vis_original, vis_gt])
    bottom = np.hstack([vis_pred, vis_diff])
    combined = np.vstack([top, bottom])

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(w, h) / 2000)
    thickness = max(1, int(font_scale * 2))
    y_offset = int(30 * font_scale)

    labels = [
        ("Original", (10, y_offset)),
        ("Ground Truth (Red=Insc, Blue=Paint)", (w + 10, y_offset)),
        (f"VL BBox (InscIoU={iou_result.get('inscription_iou', 0):.3f}, PaintIoU={iou_result.get('painting_iou', 0):.3f})", (10, h + y_offset)),
        (f"Diff (Green=TP, Yellow=FN, Magenta=FP)", (w + 10, h + y_offset)),
    ]
    for text, (x, y) in labels:
        cv2.putText(combined, text, (x, y), font, font_scale, (255, 255, 255), thickness + 1)
        cv2.putText(combined, text, (x, y), font, font_scale, (0, 0, 0), thickness)

    cv2.imwrite(output_path, combined)
    print(f"INFO: Saved baseline visualization to {output_path}")


def visualize_hybrid_comparison(
    image_path: str,
    gt_record: GroundTruthRecord,
    bbox_insc_mask: np.ndarray,
    bbox_paint_mask: np.ndarray,
    hybrid_insc_mask: np.ndarray,
    hybrid_paint_mask: np.ndarray,
    bbox_iou: Dict,
    hybrid_iou: Dict,
    output_path: str,
):
    """生成 BBox vs Hybrid 对比图（2行 x 4列）"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"WARNING: Cannot read image {image_path}")
        return
    h, w = img.shape[:2]

    gt_insc = polygons_to_mask(gt_record.regions.get("inscription_regions", []), w, h)
    gt_paint = polygons_to_mask(gt_record.regions.get("painting_regions", []), w, h)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(w, h) / 2000)
    thickness = max(1, int(font_scale * 2))
    y_offset = int(30 * font_scale)

    def _make_panel(pred_insc, pred_paint, label):
        """生成预测叠加图 + 差异图（水平拼接）"""
        # 预测叠加
        vis_pred = img.copy()
        vis_pred[pred_insc > 0] = vis_pred[pred_insc > 0] * 0.5 + np.array([0, 0, 255]) * 0.5
        vis_pred[pred_paint > 0] = vis_pred[pred_paint > 0] * 0.5 + np.array([255, 0, 0]) * 0.5

        # 差异图
        vis_diff = np.zeros_like(img)
        tp_i = (gt_insc > 0) & (pred_insc > 0)
        fn_i = (gt_insc > 0) & (pred_insc == 0)
        fp_i = (gt_insc == 0) & (pred_insc > 0)
        vis_diff[tp_i] = [0, 255, 0]
        vis_diff[fn_i] = [0, 255, 255]
        vis_diff[fp_i] = [255, 0, 255]

        # 合并为一个 2h x w 的竖图
        panel = np.vstack([vis_pred, vis_diff])

        cv2.putText(panel, f"{label} Pred", (10, y_offset), font, font_scale, (255, 255, 255), thickness + 1)
        cv2.putText(panel, f"{label} Pred", (10, y_offset), font, font_scale, (0, 0, 0), thickness)
        cv2.putText(panel, f"{label} Diff", (10, h + y_offset), font, font_scale, (255, 255, 255), thickness + 1)
        cv2.putText(panel, f"{label} Diff", (10, h + y_offset), font, font_scale, (0, 0, 0), thickness)

        return panel

    # 原图和 GT
    vis_original = img.copy()
    vis_gt = img.copy()
    vis_gt[gt_insc > 0] = vis_gt[gt_insc > 0] * 0.5 + np.array([0, 0, 255]) * 0.5
    vis_gt[gt_paint > 0] = vis_gt[gt_paint > 0] * 0.5 + np.array([255, 0, 0]) * 0.5

    # 补齐原图和GT到 2h 高度（复制一行）
    vis_original_2h = np.vstack([vis_original, vis_original])
    vis_gt_2h = np.vstack([vis_gt, vis_gt])

    # BBox 面板
    bbox_panel = _make_panel(bbox_insc_mask, bbox_paint_mask, "BBox")
    insc_txt = f"I={bbox_iou['inscription_iou']:.3f}"
    paint_txt = f"P={bbox_iou['painting_iou']:.3f}"
    overall_txt = f"O={bbox_iou['overall_iou']:.3f}"
    cv2.putText(bbox_panel, f"{insc_txt} {paint_txt} {overall_txt}", (10, 2 * h - 20), font, font_scale, (255, 255, 255), thickness + 1)
    cv2.putText(bbox_panel, f"{insc_txt} {paint_txt} {overall_txt}", (10, 2 * h - 20), font, font_scale, (0, 0, 0), thickness)

    # Hybrid 面板
    hybrid_panel = _make_panel(hybrid_insc_mask, hybrid_paint_mask, "Hybrid")
    insc_txt_h = f"I={hybrid_iou['inscription_iou']:.3f}"
    paint_txt_h = f"P={hybrid_iou['painting_iou']:.3f}"
    overall_txt_h = f"O={hybrid_iou['overall_iou']:.3f}"
    delta_txt = f"dO={hybrid_iou['overall_iou'] - bbox_iou['overall_iou']:+.3f}"
    cv2.putText(hybrid_panel, f"{insc_txt_h} {paint_txt_h} {overall_txt_h} {delta_txt}", (10, 2 * h - 20), font, font_scale, (255, 255, 255), thickness + 1)
    cv2.putText(hybrid_panel, f"{insc_txt_h} {paint_txt_h} {overall_txt_h} {delta_txt}", (10, 2 * h - 20), font, font_scale, (0, 0, 0), thickness)

    # 最终 2h x 4w 大图
    combined = np.hstack([vis_original_2h, vis_gt_2h, bbox_panel, hybrid_panel])
    cv2.imwrite(output_path, combined)
    print(f"INFO: Saved hybrid comparison to {output_path}")


# ── 主流程 ───────────────────────────────────────────────────────────────────

def probe_single_image(
    record: GroundTruthRecord,
    use_polygon: bool = False,
    use_hybrid: bool = False,
    use_refine: bool = False,
    fewshot_example_record: Optional[GroundTruthRecord] = None,
    prompt_version: str = "default",
) -> Dict:
    """
    对单张图执行 VL 探针测试，可选 hybrid 精修、GrabCut精修、few-shot 示例、prompt 版本、多边形输出

    Args:
        use_polygon: True=要求VL输出多边形顶点，False=输出矩形框
        use_hybrid: True=启用旧的shrink-to-fit精修
        use_refine: True=启用GrabCut多边形精修（方案A）
        fewshot_example_record: 提供一张示例图+GT bbox，让 VL 学习精确标注风格
        prompt_version: "default" | "v1_layout_cot" | "v2_rule_based" | "v3_self_critique" | "v3_polygon"
    """
    use_fewshot = fewshot_example_record is not None
    print(f"\n{'='*60}")
    print(f"PROBE: {record.title or record.image_id} | Hybrid={use_hybrid} | Refine={use_refine} | FewShot={use_fewshot} | Prompt={prompt_version} | Polygon={use_polygon}")
    print(f"Image: {record.filepath}")
    print(f"Size: {record.width}x{record.height}")
    print(f"GT Insc regions: {len(record.regions.get('inscription_regions', []))}")
    print(f"GT Paint regions: {len(record.regions.get('painting_regions', []))}")

    if not os.path.exists(record.filepath):
        return {"success": False, "error": "Image file not found"}

    # 准备 few-shot 示例
    fewshot_example = None
    if use_fewshot:
        if not os.path.exists(fewshot_example_record.filepath):
            print(f"WARNING: Few-shot example image not found: {fewshot_example_record.filepath}")
            use_fewshot = False
        else:
            example_bboxes = compute_gt_bboxes(fewshot_example_record)
            fewshot_example = (fewshot_example_record.filepath, example_bboxes)
            print(f"Few-shot example: {fewshot_example_record.title or fewshot_example_record.image_id}")
            print(f"  Example Insc: {len(example_bboxes['inscription_regions'])}, Paint: {len(example_bboxes['painting_regions'])}")

    # 1. 调用 VL
    vl_result = call_vl_segmentation(
        record.filepath, record.width, record.height,
        use_polygon=use_polygon, fewshot_example=fewshot_example,
        prompt_version=prompt_version,
    )

    if not vl_result.get("success"):
        print(f"ERROR: VL call failed: {vl_result.get('error')}")
        return vl_result

    print(f"VL Description: {vl_result.get('description', '')[:200]}...")
    print(f"VL Insc regions: {len(vl_result.get('inscription_regions', []))}")
    print(f"VL Paint regions: {len(vl_result.get('painting_regions', []))}")

    # 2. BBox baseline mask & IoU
    pred_insc_bbox = regions_to_mask(vl_result.get("inscription_regions", []), record.width, record.height)
    pred_paint_bbox = regions_to_mask(vl_result.get("painting_regions", []), record.width, record.height)

    gt_insc_mask = polygons_to_mask(record.regions.get("inscription_regions", []), record.width, record.height)
    gt_paint_mask = polygons_to_mask(record.regions.get("painting_regions", []), record.width, record.height)

    insc_iou_bbox = compute_iou(pred_insc_bbox, gt_insc_mask)
    paint_iou_bbox = compute_iou(pred_paint_bbox, gt_paint_mask)
    gt_total = np.logical_or(gt_insc_mask > 0, gt_paint_mask > 0)
    pred_total_bbox = np.logical_or(pred_insc_bbox > 0, pred_paint_bbox > 0)
    overall_iou_bbox = compute_iou(pred_total_bbox.astype(np.uint8) * 255, gt_total.astype(np.uint8) * 255)

    print(f"BBox IoU -> Insc: {insc_iou_bbox:.3f}, Paint: {paint_iou_bbox:.3f}, Overall: {overall_iou_bbox:.3f}")

    result = {
        "success": True,
        "image_id": record.image_id,
        "title": record.title,
        "width": record.width,
        "height": record.height,
        "vl_result": {
            "description": vl_result.get("description", ""),
            "inscription_regions": vl_result.get("inscription_regions", []),
            "painting_regions": vl_result.get("painting_regions", []),
            "elapsed_sec": vl_result.get("_elapsed_sec", 0),
        },
        "bbox_iou": {
            "inscription_iou": insc_iou_bbox,
            "painting_iou": paint_iou_bbox,
            "overall_iou": overall_iou_bbox,
        },
    }

    # 3. Hybrid 精修（VL bbox + CV 局部精修）- 旧方案
    if use_hybrid:
        print("INFO: Running CV refinement inside VL bboxes...")
        try:
            hybrid_seg = vl_cv_hybrid.run_hybrid_segmentation(
                record.filepath,
                vl_result.get("inscription_regions", []),
                vl_result.get("painting_regions", []),
            )
            pred_insc_hybrid = hybrid_seg["inscription_mask"]
            pred_paint_hybrid = hybrid_seg["painting_mask"]

            insc_iou_hybrid = compute_iou(pred_insc_hybrid, gt_insc_mask)
            paint_iou_hybrid = compute_iou(pred_paint_hybrid, gt_paint_mask)
            pred_total_hybrid = np.logical_or(pred_insc_hybrid > 0, pred_paint_hybrid > 0)
            overall_iou_hybrid = compute_iou(pred_total_hybrid.astype(np.uint8) * 255, gt_total.astype(np.uint8) * 255)

            print(f"Hybrid IoU -> Insc: {insc_iou_hybrid:.3f}, Paint: {paint_iou_hybrid:.3f}, Overall: {overall_iou_hybrid:.3f}")
            print(f"Improvement -> Insc: {insc_iou_hybrid - insc_iou_bbox:+.3f}, Paint: {paint_iou_hybrid - paint_iou_bbox:+.3f}, Overall: {overall_iou_hybrid - overall_iou_bbox:+.3f}")

            result["hybrid_iou"] = {
                "inscription_iou": insc_iou_hybrid,
                "painting_iou": paint_iou_hybrid,
                "overall_iou": overall_iou_hybrid,
            }
            result["hybrid_regions"] = {
                "inscription_regions": hybrid_seg["inscription_regions"],
                "painting_regions": hybrid_seg["painting_regions"],
            }
        except Exception as e:
            print(f"ERROR: Hybrid refinement failed: {e}")
            result["hybrid_error"] = str(e)

    # 4. GrabCut 精修（方案A：多边形自适应 + GrabCut边界精修）
    if use_refine:
        print("INFO: Running GrabCut polygon refinement (方案A)...")
        try:
            refined_seg = grabcut_refiner.run_grabcut_refinement(
                record.filepath,
                vl_result.get("inscription_regions", []),
                vl_result.get("painting_regions", []),
            )
            pred_insc_refined = refined_seg["inscription_mask"]
            pred_paint_refined = refined_seg["painting_mask"]

            insc_iou_refined = compute_iou(pred_insc_refined, gt_insc_mask)
            paint_iou_refined = compute_iou(pred_paint_refined, gt_paint_mask)
            pred_total_refined = np.logical_or(pred_insc_refined > 0, pred_paint_refined > 0)
            overall_iou_refined = compute_iou(pred_total_refined.astype(np.uint8) * 255, gt_total.astype(np.uint8) * 255)

            print(f"Refined IoU -> Insc: {insc_iou_refined:.3f}, Paint: {paint_iou_refined:.3f}, Overall: {overall_iou_refined:.3f}")
            print(f"Improvement -> Insc: {insc_iou_refined - insc_iou_bbox:+.3f}, Paint: {paint_iou_refined - paint_iou_bbox:+.3f}, Overall: {overall_iou_refined - overall_iou_bbox:+.3f}")

            result["refine_iou"] = {
                "inscription_iou": insc_iou_refined,
                "painting_iou": paint_iou_refined,
                "overall_iou": overall_iou_refined,
            }
            result["refine_regions"] = {
                "inscription_regions": refined_seg["inscription_regions"],
                "painting_regions": refined_seg["painting_regions"],
            }
        except Exception as e:
            print(f"ERROR: GrabCut refinement failed: {e}")
            import traceback
            traceback.print_exc()
            result["refine_error"] = str(e)

    return result


def run_probe(
    images_to_test: Optional[List[str]] = None,
    use_hybrid: bool = True,
    use_refine: bool = False,
    fewshot_example_id: Optional[str] = None,
    prompt_version: str = "default",
    use_polygon: bool = False,
):
    """
    运行 VL 探针测试，支持 Hybrid 精修、GrabCut精修、Few-shot 学习、Prompt 版本选择

    Args:
        images_to_test: 指定要测试的图片 title 或 image_id 列表，None=自动选前3张
        use_hybrid: True=启用 VL+CV Hybrid 精修（旧方案）
        use_refine: True=启用 GrabCut多边形精修（方案A）
        fewshot_example_id: 指定 few-shot 示例图的 title/image_id，None=不使用 few-shot
        prompt_version: "default" | "v1_layout_cot" | "v2_rule_based" | "v3_self_critique" | "v3_polygon"
        use_polygon: True=要求VL输出多边形顶点（与prompt_version=v3_polygon等价）
    """
    # 加载 GT
    print("INFO: Loading Ground Truth data...")
    records = load_ground_truth(artist="李鱓")
    print(f"INFO: Loaded {len(records)} GT records")

    if not records:
        print("ERROR: No GT records found")
        return

    # 选择 few-shot 示例图（必须在测试集之前确定，且不能出现在测试集中）
    fewshot_record = None
    if fewshot_example_id:
        for r in records:
            if fewshot_example_id in (r.title, r.image_id, str(r.id)):
                fewshot_record = r
                break
        if fewshot_record:
            print(f"INFO: Few-shot example selected: {fewshot_record.title or fewshot_record.image_id}")
        else:
            print(f"WARNING: Few-shot example '{fewshot_example_id}' not found in GT records")

    # 选择测试图片
    if images_to_test:
        test_records = []
        for identifier in images_to_test:
            for r in records:
                if identifier in (r.title, r.image_id, str(r.id)):
                    test_records.append(r)
                    break
    else:
        # 默认选前3张（跳过 few-shot 示例图）
        excluded_ids = {fewshot_record.image_id} if fewshot_record else set()
        test_records = [r for r in records if r.image_id not in excluded_ids][:3]

    print(f"INFO: Testing {len(test_records)} images: {[r.title or r.image_id for r in test_records]}")
    print(f"INFO: Mode: Hybrid={use_hybrid} | Refine={use_refine} | FewShot={'ON' if fewshot_record else 'OFF'} | Prompt={prompt_version} | Polygon={use_polygon}")

    # 创建报告目录
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPORT_DIR, ts)
    os.makedirs(out_dir, exist_ok=True)

    results = []
    for record in test_records:
        result = probe_single_image(
            record, use_hybrid=use_hybrid, use_refine=use_refine,
            fewshot_example_record=fewshot_record,
            prompt_version=prompt_version, use_polygon=use_polygon,
        )
        results.append(result)

        if not result.get("success"):
            continue

        # 生成 baseline 可视化（总是生成）
        pred_insc_bbox = regions_to_mask(
            result["vl_result"]["inscription_regions"], record.width, record.height
        )
        pred_paint_bbox = regions_to_mask(
            result["vl_result"]["painting_regions"], record.width, record.height
        )
        vis_base_path = os.path.join(out_dir, f"vis_{record.image_id}_baseline.jpg")
        visualize_comparison(
            record.filepath,
            record,
            pred_insc_bbox,
            pred_paint_bbox,
            result["bbox_iou"],
            vis_base_path,
        )

        # 生成 hybrid 对比可视化
        if use_hybrid and "hybrid_iou" in result:
            pred_insc_hybrid = regions_to_mask(
                result["hybrid_regions"]["inscription_regions"], record.width, record.height
            )
            pred_paint_hybrid = regions_to_mask(
                result["hybrid_regions"]["painting_regions"], record.width, record.height
            )
            vis_hybrid_path = os.path.join(out_dir, f"vis_{record.image_id}_hybrid.jpg")
            visualize_hybrid_comparison(
                record.filepath,
                record,
                pred_insc_bbox,
                pred_paint_bbox,
                pred_insc_hybrid,
                pred_paint_hybrid,
                result["bbox_iou"],
                result["hybrid_iou"],
                vis_hybrid_path,
            )

        # 生成 refine 对比可视化
        if use_refine and "refine_iou" in result:
            pred_insc_refined = regions_to_mask(
                result["refine_regions"]["inscription_regions"], record.width, record.height
            )
            pred_paint_refined = regions_to_mask(
                result["refine_regions"]["painting_regions"], record.width, record.height
            )
            vis_refine_path = os.path.join(out_dir, f"vis_{record.image_id}_refined.jpg")
            visualize_hybrid_comparison(
                record.filepath,
                record,
                pred_insc_bbox,
                pred_paint_bbox,
                pred_insc_refined,
                pred_paint_refined,
                result["bbox_iou"],
                result["refine_iou"],
                vis_refine_path,
            )

    # 保存报告
    successful = [r for r in results if r.get("success")]
    report = {
        "model": MODEL,
        "timestamp": ts,
        "mode": "refine" if use_refine else ("hybrid" if use_hybrid else "bbox"),
        "prompt_version": prompt_version,
        "use_polygon": use_polygon,
        "test_count": len(results),
        "successful_count": len(successful),
        "results": results,
        "bbox_summary": {
            "avg_insc_iou": sum(r["bbox_iou"]["inscription_iou"] for r in successful) / max(1, len(successful)),
            "avg_paint_iou": sum(r["bbox_iou"]["painting_iou"] for r in successful) / max(1, len(successful)),
            "avg_overall_iou": sum(r["bbox_iou"]["overall_iou"] for r in successful) / max(1, len(successful)),
        },
    }

    if use_hybrid:
        hybrid_successful = [r for r in successful if "hybrid_iou" in r]
        if hybrid_successful:
            report["hybrid_summary"] = {
                "avg_insc_iou": sum(r["hybrid_iou"]["inscription_iou"] for r in hybrid_successful) / max(1, len(hybrid_successful)),
                "avg_paint_iou": sum(r["hybrid_iou"]["painting_iou"] for r in hybrid_successful) / max(1, len(hybrid_successful)),
                "avg_overall_iou": sum(r["hybrid_iou"]["overall_iou"] for r in hybrid_successful) / max(1, len(hybrid_successful)),
            }
            report["hybrid_improvement"] = {
                "insc_delta": report["hybrid_summary"]["avg_insc_iou"] - report["bbox_summary"]["avg_insc_iou"],
                "paint_delta": report["hybrid_summary"]["avg_paint_iou"] - report["bbox_summary"]["avg_paint_iou"],
                "overall_delta": report["hybrid_summary"]["avg_overall_iou"] - report["bbox_summary"]["avg_overall_iou"],
            }

    if use_refine:
        refine_successful = [r for r in successful if "refine_iou" in r]
        if refine_successful:
            report["refine_summary"] = {
                "avg_insc_iou": sum(r["refine_iou"]["inscription_iou"] for r in refine_successful) / max(1, len(refine_successful)),
                "avg_paint_iou": sum(r["refine_iou"]["painting_iou"] for r in refine_successful) / max(1, len(refine_successful)),
                "avg_overall_iou": sum(r["refine_iou"]["overall_iou"] for r in refine_successful) / max(1, len(refine_successful)),
            }
            report["refine_improvement"] = {
                "insc_delta": report["refine_summary"]["avg_insc_iou"] - report["bbox_summary"]["avg_insc_iou"],
                "paint_delta": report["refine_summary"]["avg_paint_iou"] - report["bbox_summary"]["avg_paint_iou"],
                "overall_delta": report["refine_summary"]["avg_overall_iou"] - report["bbox_summary"]["avg_overall_iou"],
            }

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"REPORT SAVED: {report_path}")
    print(f"Prompt Version: {prompt_version}")
    print(f"BBox Summary:")
    print(f"  Avg Insc IoU:  {report['bbox_summary']['avg_insc_iou']:.3f}")
    print(f"  Avg Paint IoU: {report['bbox_summary']['avg_paint_iou']:.3f}")
    print(f"  Avg Overall:   {report['bbox_summary']['avg_overall_iou']:.3f}")
    if use_hybrid and "hybrid_summary" in report:
        print(f"Hybrid Summary:")
        print(f"  Avg Insc IoU:  {report['hybrid_summary']['avg_insc_iou']:.3f}  ({report['hybrid_improvement']['insc_delta']:+.3f})")
        print(f"  Avg Paint IoU: {report['hybrid_summary']['avg_paint_iou']:.3f}  ({report['hybrid_improvement']['paint_delta']:+.3f})")
        print(f"  Avg Overall:   {report['hybrid_summary']['avg_overall_iou']:.3f}  ({report['hybrid_improvement']['overall_delta']:+.3f})")
    if use_refine and "refine_summary" in report:
        print(f"Refined Summary:")
        print(f"  Avg Insc IoU:  {report['refine_summary']['avg_insc_iou']:.3f}  ({report['refine_improvement']['insc_delta']:+.3f})")
        print(f"  Avg Paint IoU: {report['refine_summary']['avg_paint_iou']:.3f}  ({report['refine_improvement']['paint_delta']:+.3f})")
        print(f"  Avg Overall:   {report['refine_summary']['avg_overall_iou']:.3f}  ({report['refine_improvement']['overall_delta']:+.3f})")
    print(f"{'='*60}\n")

    return report


# ── 分层分析（Layered Analysis）：两次调用，先题跋后绘画 ─────────────────────────

def probe_single_image_layered(
    record: GroundTruthRecord,
    prompt_version: str = "v3_self_critique",
) -> Dict:
    """
    分层分析：第一次调用只识别题跋，第二次调用只识别绘画，合并结果

    原理：减少单次任务的复杂度，避免题跋和绘画互相干扰
    """
    print(f"\n{'='*60}")
    print(f"LAYERED PROBE: {record.title or record.image_id}")
    print(f"Image: {record.filepath}")
    print(f"Size: {record.width}x{record.height}")

    if not os.path.exists(record.filepath):
        return {"success": False, "error": "Image file not found"}

    # ── 第一层：题跋分析 ──────────────────────────────────────────────────────
    print(f"\n>>> LAYER 1: INSCRIPTION ONLY")
    vl_insc = call_vl_segmentation(
        record.filepath, record.width, record.height,
        use_polygon=False, layer="inscription",
    )

    if not vl_insc.get("success"):
        print(f"ERROR: Inscription layer failed: {vl_insc.get('error')}")
        return {"success": False, "error": f"Inscription layer: {vl_insc.get('error')}"}

    insc_regions = vl_insc.get("inscription_regions", [])
    print(f"Layer1 Result: {len(insc_regions)} inscription region(s)")
    for i, r in enumerate(insc_regions):
        print(f"  Insc {i+1}: ({r.get('x1',0):.3f},{r.get('y1',0):.3f})-({r.get('x2',0):.3f},{r.get('y2',0):.3f}) {r.get('note','')}")

    # ── 第二层：绘画分析 ──────────────────────────────────────────────────────
    print(f"\n>>> LAYER 2: PAINTING ONLY")
    vl_paint = call_vl_segmentation(
        record.filepath, record.width, record.height,
        use_polygon=False, layer="painting",
    )

    if not vl_paint.get("success"):
        print(f"ERROR: Painting layer failed: {vl_paint.get('error')}")
        return {"success": False, "error": f"Painting layer: {vl_paint.get('error')}"}

    paint_regions = vl_paint.get("painting_regions", [])
    print(f"Layer2 Result: {len(paint_regions)} painting region(s)")
    for i, r in enumerate(paint_regions):
        print(f"  Paint {i+1}: ({r.get('x1',0):.3f},{r.get('y1',0):.3f})-({r.get('x2',0):.3f},{r.get('y2',0):.3f}) {r.get('note','')}")

    # ── 合并结果 ──────────────────────────────────────────────────────────────
    merged_result = {
        "success": True,
        "description": f"[Layered] Insc: {vl_insc.get('description','')[:100]}... Paint: {vl_paint.get('description','')[:100]}...",
        "inscription_regions": insc_regions,
        "painting_regions": paint_regions,
        "_layered_meta": {
            "insc_elapsed": vl_insc.get("_elapsed_sec", 0),
            "paint_elapsed": vl_paint.get("_elapsed_sec", 0),
            "total_elapsed": vl_insc.get("_elapsed_sec", 0) + vl_paint.get("_elapsed_sec", 0),
        },
    }

    # ── IoU 计算 ──────────────────────────────────────────────────────────────
    pred_insc = regions_to_mask(insc_regions, record.width, record.height)
    pred_paint = regions_to_mask(paint_regions, record.width, record.height)

    gt_insc_mask = polygons_to_mask(record.regions.get("inscription_regions", []), record.width, record.height)
    gt_paint_mask = polygons_to_mask(record.regions.get("painting_regions", []), record.width, record.height)

    insc_iou = compute_iou(pred_insc, gt_insc_mask)
    paint_iou = compute_iou(pred_paint, gt_paint_mask)
    gt_total = np.logical_or(gt_insc_mask > 0, gt_paint_mask > 0)
    pred_total = np.logical_or(pred_insc > 0, pred_paint > 0)
    overall_iou = compute_iou(pred_total.astype(np.uint8) * 255, gt_total.astype(np.uint8) * 255)

    print(f"\nLayered IoU -> Insc: {insc_iou:.3f}, Paint: {paint_iou:.3f}, Overall: {overall_iou:.3f}")

    return {
        "success": True,
        "image_id": record.image_id,
        "title": record.title,
        "width": record.width,
        "height": record.height,
        "layered_result": merged_result,
        "layered_iou": {
            "inscription_iou": insc_iou,
            "painting_iou": paint_iou,
            "overall_iou": overall_iou,
        },
        "vl_result": {  # 兼容现有可视化
            "description": merged_result["description"],
            "inscription_regions": insc_regions,
            "painting_regions": paint_regions,
            "elapsed_sec": merged_result["_layered_meta"]["total_elapsed"],
        },
        "bbox_iou": {  # 兼容现有报告格式
            "inscription_iou": insc_iou,
            "painting_iou": paint_iou,
            "overall_iou": overall_iou,
        },
    }


def run_layered_probe(
    images_to_test: Optional[List[str]] = None,
    compare_with_single: bool = True,
) -> Dict:
    """
    运行分层分析探针，可选与单通道V3对比

    Args:
        images_to_test: 指定测试图片，None=默认前3张
        compare_with_single: True=同时运行单通道V3作为对比基线
    """
    print("INFO: Loading Ground Truth data...")
    records = load_ground_truth(artist="李鱓")
    print(f"INFO: Loaded {len(records)} GT records")

    if not records:
        print("ERROR: No GT records found")
        return {}

    # 选择测试图片
    if images_to_test:
        test_records = []
        for identifier in images_to_test:
            for r in records:
                if identifier in (r.title, r.image_id, str(r.id)):
                    test_records.append(r)
                    break
    else:
        test_records = records[:3]

    print(f"INFO: Testing {len(test_records)} images: {[r.title or r.image_id for r in test_records]}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPORT_DIR, f"layered_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    all_results = []

    for record in test_records:
        print(f"\n{'#'*70}")
        print(f"# IMAGE: {record.title or record.image_id}")
        print(f"{'#'*70}")

        # ── 分层分析 ──
        layered_result = probe_single_image_layered(record)

        # ── 单通道V3对比（可选）──
        single_result = None
        if compare_with_single:
            print(f"\n>>> BASELINE: Single-pass V3")
            single_result = probe_single_image(record, use_hybrid=False, prompt_version="v3_self_critique")

        if not layered_result.get("success"):
            print(f"WARNING: Layered analysis failed for {record.title}")
            continue

        # 保存结果
        result_entry = {
            "image_id": record.image_id,
            "title": record.title,
            "layered": layered_result.get("layered_iou", {}),
        }
        if single_result and single_result.get("success"):
            result_entry["single_v3"] = single_result.get("bbox_iou", {})
            result_entry["delta"] = {
                "insc_delta": layered_result["layered_iou"]["inscription_iou"] - single_result["bbox_iou"]["inscription_iou"],
                "paint_delta": layered_result["layered_iou"]["painting_iou"] - single_result["bbox_iou"]["painting_iou"],
                "overall_delta": layered_result["layered_iou"]["overall_iou"] - single_result["bbox_iou"]["overall_iou"],
            }
            print(f"\n>>> COMPARISON:")
            print(f"  Single V3:  I={single_result['bbox_iou']['inscription_iou']:.3f} P={single_result['bbox_iou']['painting_iou']:.3f} O={single_result['bbox_iou']['overall_iou']:.3f}")
            print(f"  Layered:    I={layered_result['layered_iou']['inscription_iou']:.3f} P={layered_result['layered_iou']['painting_iou']:.3f} O={layered_result['layered_iou']['overall_iou']:.3f}")
            print(f"  Delta:      I={result_entry['delta']['insc_delta']:+.3f} P={result_entry['delta']['paint_delta']:+.3f} O={result_entry['delta']['overall_delta']:+.3f}")

        all_results.append(result_entry)

        # 可视化
        pred_insc_l = regions_to_mask(layered_result["vl_result"]["inscription_regions"], record.width, record.height)
        pred_paint_l = regions_to_mask(layered_result["vl_result"]["painting_regions"], record.width, record.height)
        vis_path = os.path.join(out_dir, f"vis_{record.image_id}_layered.jpg")
        visualize_comparison(record.filepath, record, pred_insc_l, pred_paint_l, layered_result["layered_iou"], vis_path)

        # 如果有单通道结果，生成对比图
        if single_result and single_result.get("success"):
            pred_insc_s = regions_to_mask(single_result["vl_result"]["inscription_regions"], record.width, record.height)
            pred_paint_s = regions_to_mask(single_result["vl_result"]["painting_regions"], record.width, record.height)
            vis_compare_path = os.path.join(out_dir, f"vis_{record.image_id}_compare.jpg")
            visualize_hybrid_comparison(
                record.filepath, record,
                pred_insc_s, pred_paint_s,
                pred_insc_l, pred_paint_l,
                single_result["bbox_iou"], layered_result["layered_iou"],
                vis_compare_path,
            )

    # 汇总报告
    successful = [r for r in all_results if "layered" in r]
    report = {
        "model": MODEL,
        "timestamp": ts,
        "mode": "layered",
        "test_count": len(test_records),
        "successful_count": len(successful),
        "results": all_results,
    }

    if successful:
        report["layered_summary"] = {
            "avg_insc_iou": sum(r["layered"]["inscription_iou"] for r in successful) / len(successful),
            "avg_paint_iou": sum(r["layered"]["painting_iou"] for r in successful) / len(successful),
            "avg_overall_iou": sum(r["layered"]["overall_iou"] for r in successful) / len(successful),
        }

        single_successful = [r for r in successful if "single_v3" in r]
        if single_successful:
            report["single_v3_summary"] = {
                "avg_insc_iou": sum(r["single_v3"]["inscription_iou"] for r in single_successful) / len(single_successful),
                "avg_paint_iou": sum(r["single_v3"]["painting_iou"] for r in single_successful) / len(single_successful),
                "avg_overall_iou": sum(r["single_v3"]["overall_iou"] for r in single_successful) / len(single_successful),
            }
            report["improvement"] = {
                "insc_delta": report["layered_summary"]["avg_insc_iou"] - report["single_v3_summary"]["avg_insc_iou"],
                "paint_delta": report["layered_summary"]["avg_paint_iou"] - report["single_v3_summary"]["avg_paint_iou"],
                "overall_delta": report["layered_summary"]["avg_overall_iou"] - report["single_v3_summary"]["avg_overall_iou"],
            }

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"LAYERED REPORT SAVED: {report_path}")
    if "layered_summary" in report:
        print(f"Layered Summary:")
        print(f"  Avg Insc IoU:  {report['layered_summary']['avg_insc_iou']:.3f}")
        print(f"  Avg Paint IoU: {report['layered_summary']['avg_paint_iou']:.3f}")
        print(f"  Avg Overall:   {report['layered_summary']['avg_overall_iou']:.3f}")
    if "single_v3_summary" in report:
        print(f"Single V3 Summary:")
        print(f"  Avg Insc IoU:  {report['single_v3_summary']['avg_insc_iou']:.3f}")
        print(f"  Avg Paint IoU: {report['single_v3_summary']['avg_paint_iou']:.3f}")
        print(f"  Avg Overall:   {report['single_v3_summary']['avg_overall_iou']:.3f}")
    if "improvement" in report:
        print(f"Improvement (Layered - Single):")
        print(f"  Insc:  {report['improvement']['insc_delta']:+.3f}")
        print(f"  Paint: {report['improvement']['paint_delta']:+.3f}")
        print(f"  Overall: {report['improvement']['overall_delta']:+.3f}")
    print(f"{'='*60}\n")

    return report


def run_prompt_ab_test(
    images_to_test: Optional[List[str]] = None,
    prompt_versions: List[str] = None,
) -> Dict:
    """
    A/B 测试多个 Prompt 版本，输出对比报告

    Args:
        images_to_test: 测试图片列表，None=默认前3张
        prompt_versions: Prompt 版本列表，如 ["default", "v1_layout_cot", "v2_rule_based"]
    """
    if prompt_versions is None:
        prompt_versions = ["default", "v1_layout_cot", "v2_rule_based", "v3_self_critique"]

    print(f"\n{'='*70}")
    print(f"PROMPT A/B TEST")
    print(f"Versions: {prompt_versions}")
    print(f"Images: {images_to_test or 'default first 3'}")
    print(f"{'='*70}\n")

    all_reports = {}
    for version in prompt_versions:
        print(f"\n>>> Running prompt version: {version}")
        report = run_probe(
            images_to_test=images_to_test,
            use_hybrid=False,
            prompt_version=version,
        )
        if report:
            all_reports[version] = report

    # 生成对比摘要
    print(f"\n{'='*70}")
    print(f"PROMPT A/B TEST SUMMARY")
    print(f"{'='*70}")
    print(f"{'Version':<20} {'Insc':>8} {'Paint':>8} {'Overall':>8} {'Success':>8}")
    print(f"{'-'*60}")
    for version, report in all_reports.items():
        s = report.get("bbox_summary", {})
        success = report.get("successful_count", 0)
        total = report.get("test_count", 0)
        print(f"{version:<20} {s.get('avg_insc_iou', 0):>8.3f} {s.get('avg_paint_iou', 0):>8.3f} {s.get('avg_overall_iou', 0):>8.3f} {f'{success}/{total}':>8}")

    # 找出最佳版本
    best_version = max(
        all_reports.items(),
        key=lambda x: x[1].get("bbox_summary", {}).get("avg_overall_iou", 0),
    )
    print(f"\nBEST PROMPT: {best_version[0]} (Overall IoU: {best_version[1]['bbox_summary']['avg_overall_iou']:.3f})")
    print(f"{'='*70}\n")

    return all_reports


if __name__ == "__main__":
    import sys
    # 默认启用 hybrid 模式，可传 --bbox-only 关闭
    use_hybrid = "--bbox-only" not in sys.argv
    # GrabCut 精修模式: --refine
    use_refine = "--refine" in sys.argv
    # 多边形输出: --polygon
    use_polygon = "--polygon" in sys.argv
    # Few-shot 示例图 ID，如: --fewshot=煮茶图
    fewshot_id = None
    # Prompt 版本，如: --prompt=v1_layout_cot
    prompt_version = "default"
    # A/B 测试模式: --ab-test
    ab_test_mode = "--ab-test" in sys.argv
    # 分层分析模式: --layered
    layered_mode = "--layered" in sys.argv

    for arg in sys.argv:
        if arg.startswith("--fewshot="):
            fewshot_id = arg.split("=", 1)[1]
        elif arg.startswith("--prompt="):
            prompt_version = arg.split("=", 1)[1]

    if ab_test_mode:
        run_prompt_ab_test()
    elif layered_mode:
        run_layered_probe()
    else:
        run_probe(
            use_hybrid=use_hybrid,
            use_refine=use_refine,
            fewshot_example_id=fewshot_id,
            prompt_version=prompt_version,
            use_polygon=use_polygon,
        )
