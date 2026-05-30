"""
方向D：VL 网格标注探针 (Grid Segmentation)

核心思路：不让 VL 输出坐标，而是让 VL 输出低分辨率网格标注（如 32x32），
每个格子标注类别（I=题跋/P=绘画/B=留白），然后上采样回原始分辨率做 IoU。

优势：VL 对"涂色/填格子"比"报坐标"更直观，可能突破坐标精度瓶颈。

用法:
    cd backend
    # 单图测试
    python -m app.tubi.evaluation.grid_segmentation_probe --image=荷花图

    # 3图对比
    python -m app.tubi.evaluation.grid_segmentation_probe --quick

    # 指定网格大小
    python -m app.tubi.evaluation.grid_segmentation_probe --quick --grid=64
"""

import json
import os
import sys
import time
import base64
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 加载 .env
from dotenv import load_dotenv
_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_BASE, ".env"))

import cv2
import numpy as np
from PIL import Image
import httpx

from app.tiba.evaluation.gt_loader import load_ground_truth, GroundTruthRecord
from app.tiba.evaluation.iou_evaluator import polygons_to_mask, compute_iou


# ── 配置 ────────────────────────────────────────────────────────────────────
API_KEY = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("QWEN_VL_PROBE_MODEL", "qwen3-vl-plus")

REPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "evaluation_reports", "vl_probe"
)

# 网格标注的编码方式
# I = Inscription (题跋), P = Painting (绘画), B = Blank (留白)
GRID_LABELS = {"I": 1, "P": 2, "B": 0}  # 映射到 mask 值


# ── 图像编码 ────────────────────────────────────────────────────────────────
def encode_image_for_grid(image_path: str, max_side: int = 2048, quality: int = 85) -> Tuple[str, float]:
    """将图片编码为 base64，返回 (base64_str, scale_ratio)"""
    img = Image.open(image_path)
    w, h = img.size

    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        ratio = 1.0

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, ratio


import io  # 前置到 encode_image 之前


# ── Prompt 构建 ─────────────────────────────────────────────────────────────
def build_grid_prompt(image_width: int, image_height: int, grid_cols: int, grid_rows: int) -> str:
    """
    构建网格标注 prompt

    让 VL 把图像想象成一个 grid_cols x grid_rows 的网格，
    每个格子标注 I(题跋)/P(绘画)/B(留白)
    """
    return f"""你是一位专业的中国书画鉴定专家。请分析这张图片，用网格标注法标注区域。

## 任务说明

将图像视为一个 **{grid_cols}列 x {grid_rows}行** 的网格（共 {grid_cols * grid_rows} 个格子）。
原始图像尺寸为 {image_width}x{image_height} 像素，因此：
- 每列宽度 ≈ {image_width / grid_cols:.0f} 像素
- 每行高度 ≈ {image_height / grid_rows:.0f} 像素

对每个格子，判断其**主体内容**属于以下哪一类：
- **I** = 题跋区域（书法文字、诗文、款识、题记）
- **P** = 绘画区域（画中的物象：花、鸟、山、水、人物等）
- **B** = 留白区域（无内容的宣纸/绢面背景，包括大面积空白）

## 标注规则

1. **题跋优先**：如果格子中同时有题跋和绘画，以面积占比大的为准
2. **印章处理**：印章属于其依附的区域（题跋旁的印章归题跋，绘画中的印章归绘画）
3. **边界格子**：边界处的格子以主体内容为准，不要过度标注
4. **留白判定**：只有确实没有文字和绘画的空白区域才标 B，淡墨渲染区域标 P

## 输出格式

请输出一个 JSON，格式如下：

```json
{{
  "description": "简要描述画面布局",
  "grid_rows": {grid_rows},
  "grid_cols": {grid_cols},
  "grid": [
    "BBBBBBBBBBIIIIIIIIIIIIII",
    "BBBBBBBBBBIIIIIIIIIIIIII",
    "BBBBBBBBBBIIIIIIIIIIIIII",
    "BPPPPPPPPBBIIIIIIIIIIII",
    "BPPPPPPPPBBBBBBBBBBBBBB",
    "BPPPPPPPPBBBBBBBBBBBBBB",
    "BBBBPPPPPPBBBBBBBBBBBBB",
    "BBBBPPPPPPBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBB"
  ]
}}
```

**重要**：
- grid 数组必须有恰好 {grid_rows} 行
- 每行字符串必须恰好 {grid_cols} 个字符
- 每个字符只能是 I、P、B 之一
- 先输出描述，再输出 grid
- 第1行 = 图像最上方，第{grid_rows}行 = 图像最下方
- 每行第1列 = 图像最左方，第{grid_cols}列 = 图像最右方
"""


def build_grid_prompt_v2(image_width: int, image_height: int, grid_cols: int, grid_rows: int) -> str:
    """
    V2: 增加自检步骤，类似 v3_self_critique 的思路
    """
    return f"""你是一位专业的中国书画鉴定专家。请分析这张图片，用网格标注法标注区域。

## 任务说明

将图像视为一个 **{grid_cols}列 x {grid_rows}行** 的网格（共 {grid_cols * grid_rows} 个格子）。
原始图像尺寸为 {image_width}x{image_height} 像素，因此：
- 每列宽度 ≈ {image_width / grid_cols:.0f} 像素
- 每行高度 ≈ {image_height / grid_rows:.0f} 像素

对每个格子，判断其主体内容属于：
- **I** = 题跋（书法文字、诗文、款识、题记、印章旁款识）
- **P** = 绘画（画中物象：花、鸟、山、水、人物、淡墨渲染等）
- **B** = 留白（无内容的宣纸/绢面背景）

## 第一步：观察与描述
先仔细观察画面，描述：
1. 整体构图（立轴/横幅/册页）
2. 题跋位置和内容
3. 绘画内容和位置
4. 留白分布

## 第二步：初步标注
在脑中构建 {grid_rows}x{grid_cols} 网格，逐行标注每个格子。

## 第三步：自我检查
对初步标注进行自检：
1. 题跋区域是否完整？有没有遗漏角落的小字？
2. 绘画区域是否合理？淡墨渲染部分应标P而非B
3. 留白区域是否准确？只有真正空白的地方才标B
4. 题跋和绘画的边界是否清晰？不应该有大量重叠
5. 网格行数是否恰好{grid_rows}？列数是否恰好{grid_cols}？

## 第四步：输出最终标注

```json
{{
  "description": "简要描述画面布局",
  "grid_rows": {grid_rows},
  "grid_cols": {grid_cols},
  "grid": [
    "第1行的{grid_cols}个字符...",
    "第2行的{grid_cols}个字符...",
    ...
  ]
}}
```

**关键要求**：
- grid 数组恰好 {grid_rows} 行，每行恰好 {grid_cols} 个字符
- 字符只能是 I、P、B
- 第1行=图像顶部，第{grid_rows}行=图像底部
- 每行第1列=图像左侧，第{grid_cols}列=图像右侧
"""


# ── API 调用 ────────────────────────────────────────────────────────────────
def call_grid_segmentation(
    image_path: str,
    image_width: int,
    image_height: int,
    grid_size: int = 32,
    prompt_version: str = "v2",
) -> Dict:
    """
    调用 VL 模型进行网格标注分割

    Args:
        grid_size: 网格大小（列数），行数按比例计算
        prompt_version: "v1" (基础) | "v2" (带自检)

    Returns:
        {
            "success": bool,
            "description": str,
            "grid": List[str],  # 每行一个字符串
            "grid_rows": int,
            "grid_cols": int,
            "raw_response": str,
            "elapsed_sec": float,
        }
    """
    if not API_KEY:
        raise ValueError("QWEN_API_KEY or DASHSCOPE_API_KEY not set")

    # 按比例计算行数，但限制总格子数避免超出 token 限制
    aspect_ratio = image_height / image_width
    grid_cols = grid_size
    grid_rows = max(4, round(grid_size * aspect_ratio))

    # 安全限制：总格子数不超过 4096（避免超出 max_tokens）
    # 4096 格子 ≈ 4096 字符 + JSON 格式 ≈ ~8000 token
    max_total_cells = 4096
    if grid_rows * grid_cols > max_total_cells:
        # 按比例缩小
        scale = (max_total_cells / (grid_rows * grid_cols)) ** 0.5
        grid_cols = max(8, int(grid_cols * scale))
        grid_rows = max(8, int(grid_rows * scale))
        print(f"INFO: Grid size reduced to {grid_cols}x{grid_rows} (was {grid_size}x{round(grid_size * aspect_ratio)}) to fit token limit")

    target_b64, scale = encode_image_for_grid(image_path)

    if prompt_version == "v1":
        prompt = build_grid_prompt(image_width, image_height, grid_cols, grid_rows)
    else:
        prompt = build_grid_prompt_v2(image_width, image_height, grid_cols, grid_rows)

    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{target_b64}"}},
    ]

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "max_tokens": 16384,
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

    response_text = result["choices"][0]["message"]["content"]
    print(f"INFO: Grid API returned in {elapsed:.1f}s")

    parsed = _parse_grid_response(response_text, grid_rows, grid_cols)
    parsed["_raw_response"] = response_text
    parsed["_elapsed_sec"] = elapsed
    parsed["_scale_ratio"] = scale
    return parsed


def _parse_grid_response(content: str, expected_rows: int, expected_cols: int) -> Dict:
    """从 VL 返回的文本中提取网格标注 JSON，支持截断恢复"""
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end + 1]
        else:
            # JSON 可能被截断（没有闭合的 }），尝试手动提取 grid
            return _parse_truncated_grid(content, expected_rows, expected_cols)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"WARNING: JSON parse failed: {e}, attempting truncated grid extraction...")
        return _parse_truncated_grid(content, expected_rows, expected_cols)

    grid = data.get("grid", [])
    desc = data.get("description", "")
    grid_rows = data.get("grid_rows", expected_rows)
    grid_cols = data.get("grid_cols", expected_cols)

    # 验证网格
    valid = True
    issues = []

    if len(grid) != expected_rows:
        issues.append(f"Expected {expected_rows} rows, got {len(grid)}")
        # 尝试修复：如果行数不对但差距不大，裁剪或补充
        if len(grid) > expected_rows:
            grid = grid[:expected_rows]
        else:
            # 补充 B 行
            while len(grid) < expected_rows:
                grid.append("B" * expected_cols)

    for i, row in enumerate(grid):
        # 清理：移除空格等
        row = row.strip().replace(" ", "")
        grid[i] = row

        if len(row) != expected_cols:
            issues.append(f"Row {i}: expected {expected_cols} cols, got {len(row)}")
            # 修复：截断或补充
            if len(row) > expected_cols:
                grid[i] = row[:expected_cols]
            else:
                grid[i] = row + "B" * (expected_cols - len(row))

        # 检查字符合法性
        for ch in grid[i]:
            if ch not in "IPB":
                issues.append(f"Row {i}: invalid char '{ch}'")
                grid[i] = grid[i].replace(ch, "B")

    if issues:
        print(f"WARNING: Grid validation issues: {issues[:3]}...")

    return {
        "success": True,
        "description": desc,
        "grid": grid,
        "grid_rows": expected_rows,
        "grid_cols": expected_cols,
        "validation_issues": issues,
    }


def _parse_truncated_grid(content: str, expected_rows: int, expected_cols: int) -> Dict:
    """
    当 JSON 被截断时，用正则从文本中逐行提取网格行。
    每行格式如 "IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIII" 或 "BPPPPPPPPBBIIIIIIIIIIII"
    """
    # 提取 description（如果有的话）
    desc = ""
    desc_match = re.search(r'"description"\s*:\s*"([^"]*)"', content)
    if desc_match:
        desc = desc_match.group(1)

    # 提取所有看起来像网格行的字符串（只包含 I/P/B 的连续字符，长度 >= expected_cols * 0.5）
    min_len = max(4, expected_cols // 2)
    grid_rows_raw = re.findall(r'"([IPB]{%d,})"' % min_len, content)

    if not grid_rows_raw:
        print(f"ERROR: No grid rows found in truncated response")
        return {"success": False, "error": "Truncated: no grid rows found", "grid": [], "grid_rows": 0, "grid_cols": 0, "description": desc}

    # 修复每行长度
    grid = []
    for row in grid_rows_raw:
        row = row.strip()
        if len(row) > expected_cols:
            row = row[:expected_cols]
        elif len(row) < expected_cols:
            row = row + "B" * (expected_cols - len(row))
        grid.append(row)

    # 修复行数
    if len(grid) > expected_rows:
        grid = grid[:expected_rows]
    elif len(grid) < expected_rows:
        missing = expected_rows - len(grid)
        print(f"WARNING: Truncated grid: got {len(grid)}/{expected_rows} rows, filling {missing} with B")
        while len(grid) < expected_rows:
            grid.append("B" * expected_cols)

    print(f"INFO: Recovered truncated grid: {len(grid)} rows x {expected_cols} cols (expected {expected_rows}x{expected_cols})")

    return {
        "success": True,
        "description": desc,
        "grid": grid,
        "grid_rows": expected_rows,
        "grid_cols": expected_cols,
        "validation_issues": ["truncated_response_recovered"],
    }


# ── 网格 → Mask 转换 ──────────────────────────────────────────────────────
def grid_to_masks(grid: List[str], grid_rows: int, grid_cols: int,
                  target_width: int, target_height: int) -> Dict[str, np.ndarray]:
    """
    将 VL 输出的网格标注转换为原始分辨率的三类 mask

    Args:
        grid: 网格标注，每行一个字符串
        grid_rows: 网格行数
        grid_cols: 网格列数
        target_width: 目标图像宽度
        target_height: 目标图像高度

    Returns:
        {
            "inscription_mask": np.ndarray (target_height x target_width, uint8, 0/255),
            "painting_mask": np.ndarray,
            "blank_mask": np.ndarray,
        }
    """
    # 先构建低分辨率 mask
    insc_low = np.zeros((grid_rows, grid_cols), dtype=np.uint8)
    paint_low = np.zeros((grid_rows, grid_cols), dtype=np.uint8)
    blank_low = np.zeros((grid_rows, grid_cols), dtype=np.uint8)

    for r, row in enumerate(grid):
        if r >= grid_rows:
            break
        for c, ch in enumerate(row):
            if c >= grid_cols:
                break
            if ch == "I":
                insc_low[r, c] = 255
            elif ch == "P":
                paint_low[r, c] = 255
            elif ch == "B":
                blank_low[r, c] = 255

    # 上采样到目标分辨率（使用最近邻插值保持清晰边界）
    insc_mask = cv2.resize(insc_low, (target_width, target_height), interpolation=cv2.INTER_NEAREST)
    paint_mask = cv2.resize(paint_low, (target_width, target_height), interpolation=cv2.INTER_NEAREST)
    blank_mask = cv2.resize(blank_low, (target_width, target_height), interpolation=cv2.INTER_NEAREST)

    return {
        "inscription_mask": insc_mask,
        "painting_mask": paint_mask,
        "blank_mask": blank_mask,
    }


def grid_to_polygons(grid: List[str], grid_rows: int, grid_cols: int,
                     target_width: int, target_height: int) -> Dict[str, List[Dict]]:
    """
    将网格标注转换为多边形格式（与 GT 格式一致，便于 IoU 计算）

    Returns:
        {
            "inscription_regions": [{"points": [{"x": ..., "y": ...}, ...]}, ...],
            "painting_regions": [...],
        }
    """
    masks = grid_to_masks(grid, grid_rows, grid_cols, target_width, target_height)

    result = {"inscription_regions": [], "painting_regions": []}

    for label, mask_key in [("inscription", "inscription_mask"), ("painting", "painting_mask")]:
        mask = masks[mask_key]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            # 简化轮廓
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            if len(approx) < 3:
                continue

            points = []
            for pt in approx:
                points.append({"x": float(pt[0][0]), "y": float(pt[0][1])})

            result[f"{label}_regions"].append({"points": points})

    return result


# ── IoU 评估 ────────────────────────────────────────────────────────────────
def evaluate_grid_against_gt(
    grid: List[str],
    grid_rows: int,
    grid_cols: int,
    gt_record: GroundTruthRecord,
) -> Dict:
    """
    评估网格标注与 Ground Truth 的 IoU

    Returns:
        {
            "inscription_iou": float,
            "painting_iou": float,
            "blank_iou": float,
            "overall_iou": float,
        }
    """
    # 生成网格 mask
    grid_masks = grid_to_masks(grid, grid_rows, grid_cols, gt_record.width, gt_record.height)

    # 生成 GT mask
    gt_insc = polygons_to_mask(
        gt_record.regions.get("inscription_regions", []),
        gt_record.width, gt_record.height
    )
    gt_paint = polygons_to_mask(
        gt_record.regions.get("painting_regions", []),
        gt_record.width, gt_record.height
    )

    # 计算 IoU
    insc_iou = compute_iou(grid_masks["inscription_mask"], gt_insc)
    paint_iou = compute_iou(grid_masks["painting_mask"], gt_paint)

    # Overall: 题跋+绘画的并集 vs GT的并集
    pred_combined = np.maximum(grid_masks["inscription_mask"], grid_masks["painting_mask"])
    gt_combined = np.maximum(gt_insc, gt_paint)
    overall_iou = compute_iou(pred_combined, gt_combined)

    # 留白 IoU（可选）
    gt_blank = np.zeros_like(gt_insc)
    gt_blank[(gt_insc == 0) & (gt_paint == 0)] = 255
    blank_iou = compute_iou(grid_masks["blank_mask"], gt_blank)

    return {
        "inscription_iou": insc_iou,
        "painting_iou": paint_iou,
        "blank_iou": blank_iou,
        "overall_iou": overall_iou,
    }


# ── 可视化 ──────────────────────────────────────────────────────────────────
def visualize_grid_comparison(
    image_path: str,
    grid: List[str],
    grid_rows: int,
    grid_cols: int,
    gt_record: GroundTruthRecord,
    output_path: str,
):
    """生成对比可视化：原图 + 网格标注 + GT"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"WARNING: Cannot read {image_path}")
        return

    h, w = img.shape[:2]

    # 网格 mask → 彩色叠加
    grid_masks = grid_to_masks(grid, grid_rows, grid_cols, w, h)
    grid_overlay = img.copy()
    # 题跋=红色，绘画=蓝色，留白=灰色
    grid_overlay[grid_masks["inscription_mask"] > 0] = [0, 0, 200]  # BGR red
    grid_overlay[grid_masks["painting_mask"] > 0] = [200, 0, 0]  # BGR blue
    grid_overlay[grid_masks["blank_mask"] > 0] = [180, 180, 180]  # BGR gray
    # 混合
    grid_vis = cv2.addWeighted(img, 0.5, grid_overlay, 0.5, 0)

    # GT mask → 彩色叠加
    gt_insc = polygons_to_mask(gt_record.regions.get("inscription_regions", []), w, h)
    gt_paint = polygons_to_mask(gt_record.regions.get("painting_regions", []), w, h)
    gt_overlay = img.copy()
    gt_overlay[gt_insc > 0] = [0, 0, 200]
    gt_overlay[gt_paint > 0] = [200, 0, 0]
    gt_vis = cv2.addWeighted(img, 0.5, gt_overlay, 0.5, 0)

    # 拼接
    # 确保尺寸一致
    target_h = min(grid_vis.shape[0], gt_vis.shape[0])
    target_w = min(grid_vis.shape[1], gt_vis.shape[1])
    grid_vis = cv2.resize(grid_vis, (target_w, target_h))
    gt_vis = cv2.resize(gt_vis, (target_w, target_h))

    combined = np.hstack([grid_vis, gt_vis])

    # 添加标签
    cv2.putText(combined, "Grid Prediction", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(combined, "Ground Truth", (target_w + 20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    cv2.imwrite(output_path, combined)
    print(f"  Saved: {output_path}")


# ── 单图测试 ────────────────────────────────────────────────────────────────
def probe_single_image_grid(
    record: GroundTruthRecord,
    grid_size: int = 32,
    prompt_version: str = "v2",
) -> Dict:
    """
    对单张图执行网格标注探针测试

    Returns:
        {
            "success": bool,
            "grid_iou": {inscription_iou, painting_iou, blank_iou, overall_iou},
            "grid": [...],
            "description": str,
            "elapsed_sec": float,
        }
    """
    print(f"\n{'='*60}")
    print(f"GRID PROBE: {record.title or record.image_id} | Grid={grid_size} | Prompt={prompt_version}")
    print(f"Image: {record.filepath}")
    print(f"Size: {record.width}x{record.height}")

    try:
        result = call_grid_segmentation(
            record.filepath,
            record.width,
            record.height,
            grid_size=grid_size,
            prompt_version=prompt_version,
        )
    except Exception as e:
        print(f"ERROR: API call failed: {e}")
        return {"success": False, "error": str(e)}

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Unknown")}

    grid = result["grid"]
    grid_rows = result["grid_rows"]
    grid_cols = result["grid_cols"]

    # 打印网格（缩略）
    print(f"\n  Grid ({grid_rows}x{grid_cols}):")
    # 如果太大，只打印前几行和后几行
    if grid_rows <= 20:
        for row in grid:
            print(f"    {row}")
    else:
        for row in grid[:5]:
            print(f"    {row}")
        print(f"    ... ({grid_rows - 10} rows omitted) ...")
        for row in grid[-5:]:
            print(f"    {row}")

    # 计算 IoU
    iou = evaluate_grid_against_gt(grid, grid_rows, grid_cols, record)
    print(f"\n  Grid IoU: Insc={iou['inscription_iou']:.3f} Paint={iou['painting_iou']:.3f} Blank={iou['blank_iou']:.3f} Overall={iou['overall_iou']:.3f}")

    return {
        "success": True,
        "grid_iou": iou,
        "grid": grid,
        "grid_rows": grid_rows,
        "grid_cols": grid_cols,
        "description": result.get("description", ""),
        "elapsed_sec": result.get("_elapsed_sec", 0),
    }


# ── 快速对比测试 ────────────────────────────────────────────────────────────
def run_grid_vs_bbox_comparison(
    test_titles: List[str] = None,
    grid_sizes: List[int] = None,
    artist: str = "李鱓",
):
    """
    对比 Grid vs BBox vs Polygon 的 IoU

    Args:
        test_titles: 测试图标题列表，默认3张
        grid_sizes: 网格大小列表，默认 [32, 48]
    """
    if test_titles is None:
        test_titles = ["荷花图", "土墙蝶花图", "煮茶图"]
    if grid_sizes is None:
        grid_sizes = [32, 48]

    from app.tiba.evaluation.vl_segmentation_probe import (
        probe_single_image as probe_bbox,
    )

    print("=" * 70)
    print("方向D验证：Grid Segmentation vs BBox vs Polygon")
    print("=" * 70)

    records = load_ground_truth(artist=artist)
    test_records = []
    for title in test_titles:
        for r in records:
            if r.title == title:
                test_records.append(r)
                break

    print(f"测试图片: {[r.title for r in test_records]}")
    print(f"网格大小: {grid_sizes}")

    results = []

    for record in test_records:
        print(f"\n{'#'*70}")
        print(f"# IMAGE: {record.title}")
        print(f"{'#'*70}")

        entry = {"image_id": record.image_id, "title": record.title}

        # 1. BBox baseline (v3_self_critique)
        print("\n>>> BBox (v3_self_critique)")
        try:
            bbox_result = probe_bbox(record, use_polygon=False, prompt_version="v3_self_critique")
            if bbox_result.get("success"):
                entry["bbox"] = bbox_result["bbox_iou"]
                print(f"  BBox IoU: I={entry['bbox']['inscription_iou']:.3f} P={entry['bbox']['painting_iou']:.3f} O={entry['bbox']['overall_iou']:.3f}")
        except Exception as e:
            print(f"  BBox ERROR: {e}")

        # 2. Polygon baseline (v3_polygon)
        print("\n>>> Polygon (v3_polygon)")
        try:
            poly_result = probe_bbox(record, use_polygon=True, prompt_version="v3_polygon")
            if poly_result.get("success"):
                entry["polygon"] = poly_result["bbox_iou"]
                print(f"  Polygon IoU: I={entry['polygon']['inscription_iou']:.3f} P={entry['polygon']['painting_iou']:.3f} O={entry['polygon']['overall_iou']:.3f}")
        except Exception as e:
            print(f"  Polygon ERROR: {e}")

        # 3. Grid (各尺寸)
        for gs in grid_sizes:
            print(f"\n>>> Grid {gs}x{gs}")
            try:
                grid_result = probe_single_image_grid(record, grid_size=gs, prompt_version="v2")
                if grid_result.get("success"):
                    entry[f"grid_{gs}"] = grid_result["grid_iou"]
                    print(f"  Grid {gs} IoU: I={grid_result['grid_iou']['inscription_iou']:.3f} P={grid_result['grid_iou']['painting_iou']:.3f} O={grid_result['grid_iou']['overall_iou']:.3f}")

                    # 生成可视化
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    vis_dir = os.path.join(REPORT_DIR, f"grid_probe_{ts}")
                    os.makedirs(vis_dir, exist_ok=True)
                    vis_path = os.path.join(vis_dir, f"vis_{record.image_id}_grid{gs}.jpg")
                    visualize_grid_comparison(
                        record.filepath,
                        grid_result["grid"],
                        grid_result["grid_rows"],
                        grid_result["grid_cols"],
                        record,
                        vis_path,
                    )
            except Exception as e:
                print(f"  Grid {gs} ERROR: {e}")

        results.append(entry)

    # 汇总
    print(f"\n{'='*70}")
    print("汇总对比")
    print(f"{'='*70}")

    header = f"{'作品':<12} {'BBox O':>8} {'Poly O':>8}"
    for gs in grid_sizes:
        header += f" {'Grid'+str(gs)+' O':>10}"
    print(header)
    print("-" * (12 + 8 + 8 + 10 * len(grid_sizes)))

    for r in results:
        line = f"{r['title']:<12}"
        bbox_o = r.get("bbox", {}).get("overall_iou", 0)
        poly_o = r.get("polygon", {}).get("overall_iou", 0)
        line += f" {bbox_o:>8.3f} {poly_o:>8.3f}"
        for gs in grid_sizes:
            grid_o = r.get(f"grid_{gs}", {}).get("overall_iou", 0)
            line += f" {grid_o:>10.3f}"
        print(line)

    # 保存报告
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(REPORT_DIR, f"grid_probe_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    report_path = os.path.join(out_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_images": test_titles,
            "grid_sizes": grid_sizes,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n报告保存: {report_path}")
    return results


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="方向D: VL Grid Segmentation Probe")
    parser.add_argument("--quick", action="store_true", help="快速3图对比测试")
    parser.add_argument("--image", type=str, help="单图测试（按标题匹配）")
    parser.add_argument("--grid", type=int, default=32, help="网格大小（默认32）")
    parser.add_argument("--grid-sizes", type=str, default="32,48", help="多个网格大小，逗号分隔")
    parser.add_argument("--prompt", type=str, default="v2", help="Prompt版本: v1/v2")
    parser.add_argument("--artist", type=str, default="李鱓", help="画家筛选")

    args = parser.parse_args()

    if args.quick:
        grid_sizes = [int(x) for x in args.grid_sizes.split(",")]
        run_grid_vs_bbox_comparison(grid_sizes=grid_sizes)
    elif args.image:
        records = load_ground_truth(artist=args.artist)
        for r in records:
            if r.title == args.image:
                result = probe_single_image_grid(r, grid_size=args.grid, prompt_version=args.prompt)
                print(f"\nResult: {json.dumps(result.get('grid_iou', {}), indent=2)}")
                break
        else:
            print(f"未找到标题为 '{args.image}' 的图片")
    else:
        parser.print_help()
