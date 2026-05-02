"""
起承转合分析 — 共享核心模块
============================
提供 analyze_qichengzhuanhe() 函数，可被：
- qichengzhuanhe_api.py（前端独立页面 API）
- stages.py（composition 主分析流程）
共同调用，避免代码重复。
"""
from __future__ import annotations

import base64
import json as _json
import logging
import os
import threading
from typing import Any, Dict

import cv2
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Prompt（单一来源，两处复用）
# ---------------------------------------------------------------------------
QICHENGZHUANHE_PROMPT = """你是一位专业的中国画构图分析专家，严格遵循传统"起承转合"章法与豪哥经验规则。你的任务是**精准定位画材生长链的物理路径**，而非主观构图想象。

请按以下步骤逐步分析这张国画作品，最终输出 JSON。**每一步都必须明确思考**，但最终只返回 JSON 结果。

---

### 第一步：画材提取与主干链识别（客观分析）

1. 列出画面中所有独立的画材（如梅花、茶壶、蒲扇、山石等）。
2. 对每个画材，定位其生物/物理起源点（根部、鳞茎、盆底、器柄、基座等）的坐标（百分比 x∈[0,100]，y∈[0,100]）。若起源点在画外，允许坐标超出此范围（如 x=-5, y=30），并注明"画外"。
3. 从所有画材中，选出**唯一一条**主干生长链，必须同时满足：
   - 有大本营（起源点）；
   - 从大本营延伸出明确的主干或主结构；
   - 主干或主结构的延长线能触及画面延展后的边缘（可延长推断）。
   如果多条满足，选择大本营最靠近画面边缘、主干最粗壮者；若多根主干延长线在画外交汇，该汇聚点作为起的候选。
4. 对该主干链，找出主干延长线与画面**延展后边缘**的**首个交点**（若交点在角落则无效，需重新选择次优主干链）。记录该交点的坐标和边缘方向。若交点位于原画面之外，坐标可超出 0–100。
5. 描述从大本营出发后，主干的整体走向（例如：从右下向右上，再向左）。

---

### 第二步：起承转合候选点定位（基于主干链）

**起**：
- 必须是第一步中确定的边缘交点，或画外多线汇聚点，且满足：
  - 若在原画面内，坐标必须在边缘（x≤5 或 x≥95 或 y≤5 或 y≥95），另一维在5-95之间，不能是角落；
  - 若在原画面外，坐标可超出 0–100，且必须能通过生长逻辑明确推断（如多线汇聚、主根延伸）；
  - 是生长链最前端（根→干→枝→花，不可逆）。
- 记录坐标、是否在画内 (`in_frame`)、理由。

**承**：
- 从起出发后，沿生长方向遇到的第一个、面积最大、笔墨最实的画材实体的面积中心点；
- 必须与起属于同一生长链（同根同源）；
- 与起的欧氏距离 ≤30%（画面对角线为100），若起在画外，距离计算时以画面内第一个可见实体为准；
- 坐标在画面内（0–100）。
- 记录坐标与理由（**cheng_list 只有1个元素**）。

**转**：
- 必须同时满足两个条件：
  ① 从承到转的向量与从起到承的向量夹角 >45°（方向明显突变）；
  ② 转点是当前生长链末端的视觉张力峰值（花蕊、鸟眼、石棱、器物口沿），且是该生长链的自然终止点。
- 记录坐标与理由（**zhuan_list 只有1个元素**）。

**合**：
- 在画面内（x∈[5,95], y∈[5,95]）；
- 从转到合的向量应与从起到承的向量形成几何闭环（夹角>45°且方向趋向闭合）；
- **印章强化规则**：若题跋下方或右侧有印章，合点需向印章方向偏移至少10%（区域级偏移即可）。
- 记录坐标与理由。

---

### 第三步：铁律验证与最终输出

逐条检查以下铁律，若违反任意一条，则 `is_valid = false` 并说明原因；否则 `is_valid = true`：

1. **起**：符合生长逻辑（画内边缘或画外汇聚点），非角落（若在画内），是生长链前端。
2. **承**：与起同链、邻近、唯一。
3. **转**：方向突变、生长链末端、唯一。
4. **合**：在画面内、回旋收束、印章影响（若适用）。
5. **唯一性**：`cheng_list` 和 `zhuan_list` 均只有1个元素。
6. **禁止行为**：起无法推断画外源点；承在留白；转脱离生长链；合无回旋趋势等。

---

### 输出格式（仅返回 JSON，不要其他文字）

```json
{
  "is_valid": true,
  "validation_reason": "如果为false，写明违反哪条规则；为true时可为空",
  "analysis": "视线流动路径分析（一句话概括起承转合的动态）",
  "material_types": "主要画材列表（逗号分隔）",
  "growth_direction": "从某边缘入画或从画外引入，视线走向描述",
  "has_inscription": true,
  "inscription_edge": "贴边/半贴边/不贴边/无题跋",
  "seal_positions": [{"x": 50, "y": 80, "near": "题跋下方"}],
  "qi": {
    "x": 105,
    "y": 30,
    "in_frame": false,
    "reason": "多根梅枝延长线在画外右上角汇聚，为主干源点"
  },
  "cheng_list": [{"x": 70, "y": 70, "reason": "主花花头面积中心"}],
  "zhuan_list": [{"x": 35, "y": 45, "reason": "枝条转折处花苞，方向突变"}],
  "he": {"x": 55, "y": 20, "reason": "回旋收束于题跋与印章之间"},
  "path_shape": "三角形"
}
```"""


# ---------------------------------------------------------------------------
# 引导模式 Prompt（当已有构图分析文本时使用）
# ---------------------------------------------------------------------------
GUIDED_QCZH_PROMPT_TEMPLATE = """你是中国画构图专家。请基于以下专家讲评，在画面上标注一条流畅的起承转合曲线路径。

【构图分析（来自专家讲评）】
{llm_analysis}

你需要输出一条包含 8-12 个节点的连续路径（百分比坐标，x∈[0,100], y∈[0,100]，原点左上角）：

【关键约束——必须遵守】
1. 起(qi)：画面势能起点，靠近边缘。**必须从物象的生长根源出发**（树根、石基、最粗主枝干的入画处），**绝不从题跋、树叶、花、果实等末梢开始**。若题跋恰好在边缘，忽略它。
2. 承节点(path_points)：沿主干方向推进 2-4 个中间点，必须经过画眼（鸟/禽/大果实/主花头/主体器物）或其附近。
3. 转节点(path_points)：在方向/节奏突变处设 2-3 个点，如从上升转为下落、从左向右弹回。
4. 合(he)：势能收束点。优先选主物象气口或留白回旋处，**不要将寥寥数字的穷款当作合点**。
5. 整条路径为 qi → path_points[0..N] → he 的连续序列，共 8-12 个点。

【坐标域提示】
- 起点在墨色最重、最粗的枝干/石块入画边缘，排除文字区域。
- 承沿主干推进，经画眼。
- 转在方向变化最大处。
- 合在留白回旋处或主物象的收束气口。

只返回 JSON：
{{"qi":{{"x":数字,"y":数字,"label":"起·描述"}},"path_points":[{{"x":数字,"y":数字,"label":"承·描述"}},{{"x":数字,"y":数字,"label":"承·描述"}},{{"x":数字,"y":数字,"label":"转·描述"}},{{"x":数字,"y":数字,"label":"转·描述"}},...],"he":{{"x":数字,"y":数字,"label":"合·描述"}},"path_shape":"之字形/对角线/C形/三角形/回环/上升"}}
"""


# ---------------------------------------------------------------------------
# 中文字体（PIL 渲染）
# ---------------------------------------------------------------------------
_CJK_FONT_PATHS = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",     # 微软雅黑 Bold
    r"C:\Windows\Fonts\simhei.ttf",     # 黑体
    r"C:\Windows\Fonts\simsun.ttc",     # 宋体
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]
_cached_font = None
_cached_font_size = None
_font_lock = threading.Lock()


def _get_cjk_font(size: int = 28) -> ImageFont.FreeTypeFont:
    global _cached_font, _cached_font_size
    if _cached_font is not None and _cached_font_size == size:
        return _cached_font
    with _font_lock:
        # Double-check after acquiring lock
        if _cached_font is not None and _cached_font_size == size:
            return _cached_font
        for fp in _CJK_FONT_PATHS:
            if os.path.exists(fp):
                try:
                    _cached_font = ImageFont.truetype(fp, size)
                    _cached_font_size = size
                    return _cached_font
                except Exception:
                    continue
        logger.warning("No CJK font found, using default")
        _cached_font = ImageFont.load_default()
        _cached_font_size = size
        return _cached_font


# ---------------------------------------------------------------------------
# 图像工具函数
# ---------------------------------------------------------------------------

def encode_bgr_to_base64(img_bgr: np.ndarray, max_side: int = 1024) -> str:
    """把 cv2 BGR 图像缩放后 base64 编码（纯 base64 字符串，不带 data: 前缀）"""
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def encode_preview(img_bgr: np.ndarray, max_side: int = 1600) -> str:
    """把 cv2 BGR 图像缩放到 max_side 后 base64 编码为 data:image/jpeg;base64,..."""
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def generate_lineart(img_bgr: np.ndarray) -> np.ndarray:
    """
    将彩色国画图像转为白底黑色**实线**线稿图。

    策略（v2: CV+AI 融合优化）：
    0. 双边滤波替代高斯模糊 —— 在降噪的同时保留边缘，对国画效果更好
    1. Otsu + 自适应阈值 提取墨迹（深色区域）
    2. 色差通道提取浅色画材（鸟、浅色树干等与背景色不同的区域）
    3. 腐蚀 + 轮廓提取 → 只保留边缘线条，去除大面积实心色块
    4. Canny 补充细微轮廓边缘
    5. 合并所有通道 → 膨胀加粗 → 去噪 → 实线输出
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    total_pixels = h * w
    max_side = max(h, w)

    # ---- 0. 双边滤波去噪（替代高斯模糊，保留边缘）----
    # 双边滤波在平滑区域的同时保持边缘锐利，比高斯模糊更适合国画
    d = max(5, min(15, max_side // 100))
    # 确保 d 为奇数（OpenCV bilateralFilter 和 GaussianBlur 要求奇数核）
    if d % 2 == 0:
        d += 1
    sigma_color = 75   # 颜色空间标准差
    sigma_space = 75   # 坐标空间标准差
    blurred = cv2.bilateralFilter(gray, d, sigma_color, sigma_space)

    # ---- 1. Otsu 二值化 → 提取深色墨迹 ----
    otsu_val, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # ---- 1b. 自适应阈值补充（对泛黄/不均匀背景更鲁棒）----
    # 自适应阈值根据局部亮度动态调整，能捕获 Otsu 可能遗漏的区域
    adaptive = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=21, C=5
    )
    # 与 Otsu 结果取交集（两个方法都认为是前景才保留），减少噪声
    binary = cv2.bitwise_and(binary, adaptive)

    # ---- 2. 色差通道 → 提取浅色但有颜色的画材（鸟、浅色树干等）----
    # 用 HSV 色差检测与宣纸背景不同的区域
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    blur_k = max(5, d if d % 2 == 1 else d + 1)  # 确保 GaussianBlur 核大小为奇数
    h_blur = cv2.GaussianBlur(hsv, (blur_k, blur_k), 0)

    # 中国画宣纸背景通常偏黄/暖色，计算饱和度和明度偏移
    sat = h_blur[:, :, 1].astype(np.float32)
    val = h_blur[:, :, 2].astype(np.float32)
    hue = h_blur[:, :, 0].astype(np.float32)

    # 有颜色但可能很浅的区域：饱和度有差异 或 明度有明显差异
    sat_median = np.median(sat)
    val_median = np.median(val)

    # 色差掩码：饱和度高于背景 + 明度与背景有差距
    sat_dev = np.abs(sat - sat_median)
    val_dev = np.abs(val - val_median)

    # 自适应阈值
    sat_thresh = max(8, sat_median * 0.4)
    val_thresh = max(15, val_median * 0.15)

    # 浅色画材特征：有一定饱和度偏差，或明度偏差（不满足深色墨迹阈值的部分）
    color_mask = ((sat_dev > sat_thresh) | (val_dev > val_thresh)).astype(np.uint8) * 255

    # 从颜色掩码中排除已经被 Otsu 捕获的深色区域（避免重复），只保留浅色部分
    color_only = cv2.subtract(color_mask, binary)
    # 小形态学清理
    clean_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    color_only = cv2.morphologyEx(color_only, cv2.MORPH_CLOSE, clean_kernel, iterations=1)
    color_only = cv2.morphologyEx(color_only, cv2.MORPH_OPEN, clean_kernel, iterations=1)

    # 合并深色+浅色画材
    binary = cv2.bitwise_or(binary, color_only)

    color_ratio = cv2.countNonZero(color_only) / total_pixels * 100
    logger.debug(f"lineart color channel: sat_thresh={sat_thresh:.1f}, val_thresh={val_thresh:.1f}, "
                 f"color_ratio={color_ratio:.2f}%")

    # ---- 3. 腐蚀 + 轮廓提取（只留线条，不留色块）----
    erode_iter = 1 if max_side < 2000 else 2
    erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thinned = cv2.erode(binary, erode_kernel, iterations=erode_iter)

    edges_from_binary = cv2.Canny(thinned, 50, 150, apertureSize=3)

    # ---- 4. Canny 在原图灰度上补充细微轮廓 ----
    median = np.median(blurred)
    canny_lower = max(20, int(0.3 * median))
    canny_upper = max(40, int(0.8 * median))
    edges = cv2.Canny(blurred, canny_lower, canny_upper, apertureSize=3)

    # ---- 5. 合并 ----
    combined = cv2.bitwise_or(edges_from_binary, edges)

    # ---- 5. 膨胀加粗 → 实线效果 ----
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    combined = cv2.dilate(combined, dilate_kernel, iterations=1)

    # ---- 6. 去噪 ----
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=1)

    # 白底黑线
    lineart = 255 - combined

    edge_ratio = cv2.countNonZero(combined) / total_pixels * 100
    logger.debug(f"lineart v2: {w}x{h}, bilateral d={d}, otsu={otsu_val:.0f}, canny=[{canny_lower},{canny_upper}], "
                 f"edge_ratio={edge_ratio:.2f}%")

    return lineart


def _catmull_rom_spline(points, num_segments=50):
    """生成穿过所有控制点的 Catmull-Rom 平滑曲线点序列。"""
    if len(points) < 2:
        return [(int(p[0]), int(p[1])) for p in points]
    pts = [(float(p[0]), float(p[1])) for p in points]
    n = len(pts)
    result = []
    for i in range(n - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(n - 1, i + 2)]
        for t in range(num_segments):
            t0 = t / num_segments
            t2 = t0 * t0
            t3 = t2 * t0
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t0 +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t0 +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            result.append((int(x), int(y)))
    result.append((int(pts[-1][0]), int(pts[-1][1])))
    return result


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_arrows_on_lineart(lineart: np.ndarray, arrows: list, labels: list,
                           curve_points: list | None = None) -> np.ndarray:
    """在线稿图上绘制起承转合路径。curve_points 不为空时绘制平滑曲线，否则绘制折线箭头。"""
    if not arrows and not curve_points:
        return lineart

    if len(lineart.shape) == 2:
        canvas = cv2.cvtColor(lineart, cv2.COLOR_GRAY2BGR)
    else:
        canvas = lineart.copy()

    h, w = canvas.shape[:2]
    max_side = max(h, w)
    scale = max(1.0, max_side / 800)

    colors_bgr = [
        (229, 57, 53),
        (255, 152, 0),
        (25, 118, 210),
        (46, 125, 50),
        (123, 31, 162),
        (0, 131, 143),
    ]
    colors_rgb = [(c[2], c[1], c[0]) for c in colors_bgr]

    line_thickness = max(3, int(3 * scale))
    tip_length = 0.08

    if curve_points and len(curve_points) >= 4:
        clamped = []
        for px, py in curve_points:
            clamped.append((max(0, min(w - 1, int(px))), max(0, min(h - 1, int(py)))))
        spline = _catmull_rom_spline(clamped, num_segments=60)
        curve_thick = max(5, int(6 * scale))

        for i in range(len(spline) - 1):
            t = i / max(1, len(spline) - 2)
            if t < 0.333:
                color = _lerp_color(colors_bgr[0], colors_bgr[1], t / 0.333)
            elif t < 0.666:
                color = _lerp_color(colors_bgr[1], colors_bgr[2], (t - 0.333) / 0.333)
            else:
                color = _lerp_color(colors_bgr[2], colors_bgr[3], (t - 0.666) / 0.334)
            cv2.line(canvas, spline[i], spline[i + 1], color, curve_thick)

        steps = len(spline)
        for ai in range(3):
            idx = int((ai + 1) * steps / 4)
            if idx + 4 < steps:
                p0 = spline[idx]
                p1 = spline[idx + 4]
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                length = (dx * dx + dy * dy) ** 0.5
                if length > 0:
                    dx, dy = dx / length, dy / length
                    tip = (int(p1[0] + dx * 10 * scale), int(p1[1] + dy * 10 * scale))
                    cv2.arrowedLine(canvas, spline[idx], tip, colors_bgr[ai + 1],
                                    max(2, int(2.5 * scale)), tipLength=0.3)
    else:
        for idx, arr in enumerate(arrows):
            color = colors_bgr[idx % len(colors_bgr)]
            sx, sy, ex, ey = int(arr[0]), int(arr[1]), int(arr[2]), int(arr[3])
            sx = max(0, min(w - 1, sx))
            sy = max(0, min(h - 1, sy))
            ex = max(0, min(w - 1, ex))
            ey = max(0, min(h - 1, ey))
            cv2.arrowedLine(canvas, (sx, sy), (ex, ey), color, line_thickness, tipLength=tip_length)

    def _draw_label_pil(cv_canvas, x, y, text, color_rgb):
        radius = max(20, int(20 * scale))
        font_size = max(26, int(26 * scale))
        cv_color = (color_rgb[2], color_rgb[1], color_rgb[0])
        cx, cy = int(x), int(y)
        cv2.circle(cv_canvas, (cx, cy), radius, cv_color, -1)
        cv2.circle(cv_canvas, (cx, cy), radius, (255, 255, 255), max(2, int(2 * scale)))

        font = _get_cjk_font(font_size)
        pil_img = Image.fromarray(cv2.cvtColor(cv_canvas, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = cx - tw // 2
        ty = cy - th // 2 - bbox[1]
        draw.text((tx, ty), text, fill=(255, 255, 255), font=font)
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if curve_points and len(curve_points) >= 4:
        n = len(curve_points)
        label_indices = [0, n // 3, 2 * n // 3, n - 1]
        for li, ci in enumerate(label_indices):
            if li >= len(labels):
                break
            px, py = int(curve_points[ci][0]), int(curve_points[ci][1])
            px = max(0, min(w - 1, px))
            py = max(0, min(h - 1, py))
            canvas = _draw_label_pil(canvas, px, py, labels[li], colors_rgb[li])
        return canvas

    for idx in range(min(len(arrows), len(labels) - 1)):
        arr = arrows[idx]
        sx = max(0, min(w - 1, int(arr[0])))
        sy = max(0, min(h - 1, int(arr[1])))
        canvas = _draw_label_pil(canvas, sx, sy, labels[idx], colors_rgb[idx])

    if len(labels) > len(arrows):
        last_arr = arrows[-1]
        ex = max(0, min(w - 1, int(last_arr[2])))
        ey = max(0, min(h - 1, int(last_arr[3])))
        canvas = _draw_label_pil(canvas, ex, ey, labels[-1],
                                  colors_rgb[(len(labels) - 1) % len(colors_rgb)])

    return canvas


# ---------------------------------------------------------------------------
# 核心分析函数（同步）
# ---------------------------------------------------------------------------

def _build_chat_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _parse_llm_result(llm_result: dict, w: int, h: int, *, guided_analysis_text: str = "") -> Dict[str, Any]:
    """将 LLM 返回的 JSON 结果转换为箭头坐标格式。

    支持两种输出格式：
    - 引导模式：{"qi":{"x":..,"y":..,"label":".."}, "path_points":[{...},...], "he":{..}, "path_shape":".."}
    - 自主模式：{"qi":{..}, "cheng_list":[{..}], "zhuan_list":[{..}], "he":{..}, "path_shape":"..", ...}
    """
    is_guided = isinstance(llm_result.get("path_points"), list) and len(llm_result.get("path_points", [])) >= 2

    def _edge_dist(pt):
        x = float(pt.get("x", 50))
        y = float(pt.get("y", 50))
        return min(x, y, 100 - x, 100 - y)

    def pct_to_px(pct_dict, allow_out_of_frame=False):
        if not isinstance(pct_dict, dict):
            return {"x": w // 2, "y": h // 2, "reason": "", "in_frame": True, "label": ""}
        result = {
            "x": int(pct_dict.get("x", 50) * w / 100),
            "y": int(pct_dict.get("y", 50) * h / 100),
            "reason": pct_dict.get("reason", ""),
            "in_frame": pct_dict.get("in_frame", True),
            "label": (pct_dict.get("label") or "").strip(),
        }
        return result

    if is_guided:
        qi_raw = llm_result.get("qi") or {"x": 10, "y": 85, "label": "起"}
        he_raw = llm_result.get("he") or {"x": 80, "y": 15, "label": "合"}
        mid_raw = llm_result.get("path_points") or []
        path_shape = llm_result.get("path_shape", "之字形")

        qi_pct = dict(qi_raw) if isinstance(qi_raw, dict) else {}
        he_pct = dict(he_raw) if isinstance(he_raw, dict) else {}

        n_mid = len(mid_raw)
        logger.info("QCZH GLM raw: qi=(%s,%s) he=(%s,%s) path_points=%d path=%s",
                    qi_pct.get("x"), qi_pct.get("y"),
                    he_pct.get("x"), he_pct.get("y"), n_mid, path_shape)

        qi = pct_to_px(qi_pct, allow_out_of_frame=True)
        he = pct_to_px(he_pct)
        he["x"] = max(int(w * 0.05), min(int(w * 0.95), he["x"]))
        he["y"] = max(int(h * 0.05), min(int(h * 0.95), he["y"]))

        mid_px = []
        for i, mp in enumerate(mid_raw):
            if isinstance(mp, dict):
                px = pct_to_px(mp)
                px["type"] = "承" if i < len(mid_raw) // 2 else "转"
                mid_px.append(px)

        all_pts = [qi] + mid_px + [he]

        arrows = []
        arrow_labels = []
        prev = all_pts[0]
        for pt in all_pts[1:]:
            arrows.append([prev["x"], prev["y"], pt["x"], pt["y"]])
            arrow_labels.append(pt.get("type", "承"))
            prev = pt
        arrow_labels.insert(0, "起")
        if arrow_labels[-1] != "合":
            arrow_labels[-1] = "合"

        glm_labels = {}
        if isinstance(qi_raw, dict):
            glm_labels["qi"] = (qi_raw.get("label") or "起").strip()
        if isinstance(he_raw, dict):
            glm_labels["he"] = (he_raw.get("label") or "合").strip()
        for i, mp in enumerate(mid_raw):
            if isinstance(mp, dict):
                glm_labels[f"mid_{i}"] = (mp.get("label") or "").strip()

        narrative = guided_analysis_text if guided_analysis_text else f"路径：{path_shape}"

        curve_points = [[p["x"], p["y"]] for p in all_pts]

        return {
            "is_valid": True,
            "validation_reason": "",
            "arrows": arrows,
            "arrow_labels": arrow_labels,
            "points": {"qi": qi, "mid": mid_px, "he": he},
            "llm_analysis": narrative,
            "path_type": path_shape,
            "material_type": "",
            "growth_direction": "",
            "has_inscription": True,
            "inscription_edge": "",
            "seal_positions": [],
            "glm_labels": glm_labels,
            "curve_points": curve_points,
        }

    # 自主模式（完整学术 prompt）
    qi_raw = llm_result.get("qi")
    he_raw = llm_result.get("he")
    qi_pct = dict(qi_raw) if isinstance(qi_raw, dict) else {}
    he_pct = dict(he_raw) if isinstance(he_raw, dict) else {}

    qi_he_swapped = False
    if qi_pct and he_pct:
        if _edge_dist(qi_pct) > _edge_dist(he_pct):
            qi_he_swapped = True
            qi_pct, he_pct = he_pct, qi_pct
            llm_result["qi"], llm_result["he"] = he_pct, qi_pct
        if qi_pct.get("x", 50) > 50:
            for key in ("qi", "cheng_list", "zhuan_list", "he"):
                val = llm_result.get(key)
                if isinstance(val, dict) and "x" in val:
                    val["x"] = 100 - val["x"]
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict) and "x" in item:
                            item["x"] = 100 - item["x"]

    qi = pct_to_px(qi_raw, allow_out_of_frame=True) if qi_raw else {"x": w // 10, "y": h * 9 // 10, "reason": "默认左下", "in_frame": True, "label": ""}

    cheng_raw = llm_result.get("cheng_list") or llm_result.get("cheng") or []
    if not isinstance(cheng_raw, list):
        cheng_raw = [cheng_raw]
    cheng_list = [pct_to_px(c) for c in cheng_raw if c]
    if cheng_list:
        cheng_list = cheng_list[:1]

    zhuan_raw = llm_result.get("zhuan_list") or llm_result.get("zhuan") or []
    if not isinstance(zhuan_raw, list):
        zhuan_raw = [zhuan_raw]
    zhuan_list = [pct_to_px(z) for z in zhuan_raw if z]
    if not zhuan_list:
        zhuan_list = [{"x": w // 2, "y": h // 3, "reason": "默认中央", "in_frame": True, "label": ""}]
    zhuan_list = zhuan_list[:1]

    he = pct_to_px(he_raw) if he_raw else {"x": w * 9 // 10, "y": h // 10, "reason": "默认右上", "in_frame": True, "label": ""}
    he["x"] = max(int(w * 0.05), min(int(w * 0.95), he["x"]))
    he["y"] = max(int(h * 0.05), min(int(h * 0.95), he["y"]))

    path_points = []
    for c in cheng_list:
        path_points.append({**c, "type": "承"})
    for z in zhuan_list:
        path_points.append({**z, "type": "转"})

    if path_points:
        ordered = []
        remaining = list(range(len(path_points)))
        cur_x, cur_y = qi["x"], qi["y"]
        while remaining:
            best_idx = min(remaining,
                           key=lambda i: (path_points[i]["x"] - cur_x) ** 2 + (path_points[i]["y"] - cur_y) ** 2)
            ordered.append(path_points[best_idx])
            remaining.remove(best_idx)
            cur_x, cur_y = path_points[best_idx]["x"], path_points[best_idx]["y"]
        path_points = ordered

    arrows = []
    labels = []
    prev = qi
    for pt in path_points:
        arrows.append([prev["x"], prev["y"], pt["x"], pt["y"]])
        labels.append(pt["type"])
        prev = pt
    last_pt = path_points[-1] if path_points else qi
    arrows.append([last_pt["x"], last_pt["y"], he["x"], he["y"]])
    labels.append("合")
    labels.insert(0, "起")

    material_type = llm_result.get("material_types", llm_result.get("material_type", "未知"))
    growth_direction = llm_result.get("growth_direction", "未知")
    has_inscription = llm_result.get("has_inscription", True)
    inscription_edge = llm_result.get("inscription_edge", "未知")
    seal_positions = llm_result.get("seal_positions", [])
    path_shape = llm_result.get("path_shape", "未知")

    analysis = llm_result.get("analysis", "")
    narrative = (
        f"画材：{material_type}，{growth_direction}。\n"
        f"题跋：{'有' if has_inscription else '无'}（{inscription_edge}）。\n"
        f"路径：{path_shape}。\n"
        f"{analysis}"
    )

    return {
        "is_valid": llm_result.get("is_valid", True),
        "validation_reason": llm_result.get("validation_reason", ""),
        "arrows": arrows,
        "arrow_labels": labels,
        "points": {
            "qi": qi,
            "cheng_list": cheng_list,
            "zhuan_list": zhuan_list,
            "he": he,
        },
        "llm_analysis": narrative,
        "path_type": path_shape,
        "material_type": material_type,
        "growth_direction": growth_direction,
        "has_inscription": has_inscription,
        "inscription_edge": inscription_edge,
        "seal_positions": seal_positions,
        "qi_he_swapped": qi_he_swapped,
    }


QWEN_QCZH_PRE_PROMPT = """你是中国画构图分析专家。请基于以下知识，用简洁的自然语言分析这幅画作的起承转合关系。

【写意知识库原文（潘天寿《关于构图问题》+《中国写意花鸟画教程》相关原文）】
{knowledge_context}

【用户自定义起承转合知识】
{user_markdown}

请根据以上知识规则，分析：
1. **起**：视觉从哪里进入画面？在画面什么位置（如左下角、右上边缘等）？所对应物象是什么？
2. **承**：视线如何承接发展？在中途经过了哪些关键物象？
3. **转**：画面何处发生了方向或节奏的转折？什么元素造成了变化？
4. **合**：画面在何处收束？收束点与题款、印章有什么关系？
5. **整体走势形态**：之字形、对角线、三段式、边角、中心辐射等？

请直接描述，不要输出JSON。控制在400字以内。"""


def _fetch_qczh_knowledge_context() -> str:
    """从 Qdrant 写意知识库搜索起承转合相关的原文。"""
    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        from app.modules.pantianshou_composition import qdrant_client as qc
        search_query = "起承转合 构图 视线 气韵 虚实 疏密 留白 穿插 边角 题款"
        service = EmbeddingService()
        emb_result = service.embed_text_sync(search_query)
        if not emb_result or not emb_result.embedding:
            logger.warning("QCZH knowledge search: embedding failed")
            return "暂无知识库原文"
        hits = qc.search_collection(
            qc.KNOWLEDGE_TEXTS_COLLECTION,
            emb_result.embedding,
            limit=5,
        )
        chunks = [h.get("payload", {}).get("content", "") for h in (hits or [])]
        valid = [c.strip()[:100] for c in chunks if c and c.strip()]
        if not valid:
            return "暂无知识库原文"
        lines = [f"[{i+1}] {c}" for i, c in enumerate(valid[:5])]
        total = 0
        for i, ln in enumerate(lines):
            if total + len(ln) > 800:
                break
            total += len(ln)
        result = "\n".join(lines[:i+1]) if i > 0 else lines[0]
        logger.info("QCZH knowledge search: %d chunks (%d chars)", len(valid), len(result))
        return result
    except Exception as e:
        logger.warning("QCZH knowledge search failed: %s", e)
        return "暂无知识库原文"


def _glm_qczh_pre_analysis(img_bgr: np.ndarray) -> str | None:
    """调用 GLM-5V-Turbo 对图像做初步起承转合文字分析（含写意知识库+用户自定义知识注入）。"""
    import time as _time
    try:
        if not (settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL):
            return None
    except Exception:
        return None

    from app.modules.pantianshou_composition.user_markdown import load_user_qczh_markdowns, build_user_markdown_context
    user_markdowns = load_user_qczh_markdowns()
    user_md_context = build_user_markdown_context(user_markdowns, max_total=1200)
    knowledge_context = _fetch_qczh_knowledge_context()
    logger.info("QCZH pre-analysis: loaded %d user markdown files (%d chars), knowledge=%d chars",
                len(user_markdowns), len(user_md_context), len(knowledge_context))

    prompt = QWEN_QCZH_PRE_PROMPT.format(
        knowledge_context=knowledge_context,
        user_markdown=user_md_context,
    )

    b64 = encode_bgr_to_base64(img_bgr, max_side=1024)
    glm_model = settings.ZHIPU_MODEL.strip() or "glm-5v-turbo"
    glm_url = _build_chat_url(settings.ZHIPU_BASE_URL)
    payload = {
        "model": glm_model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        "stream": False, "max_tokens": 1024, "temperature": 0.15,
    }
    headers = {"Authorization": f"Bearer {settings.ZHIPU_API_KEY}", "Content-Type": "application/json"}
    for attempt in range(2):
        try:
            with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                r = client.post(glm_url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                text = (data["choices"][0]["message"].get("content") or "").strip()
                if text:
                    logger.info("GLM QCZH pre-analysis OK: %d chars, model=%s", len(text), glm_model)
                    return text
        except Exception as e:
            logger.warning("GLM QCZH pre-analysis attempt %d failed: %s", attempt + 1, e)
            if attempt < 1:
                _time.sleep(1)
    return None


def analyze_qichengzhuanhe(img_bgr: np.ndarray, *, llm_analysis_text: str | None = None) -> Dict[str, Any]:
    """
    核心起承转合分析函数（同步）— 统一入口。

    接收 BGR 图像，可选接收已有的构图分析文本作为引导。
    返回分析结果 dict（含 arrows/arrow_labels/points/llm_analysis/path_type/arrow_canvas 等）。

    两模式：
    - 引导模式：传入 llm_analysis_text → GLM 基于已有分析精确定位坐标
    - 自主模式：不传 llm_analysis_text → GLM 使用完整学术 prompt 自主分析

    此函数被：
    - qichengzhuanhe_api.py（独立 QCZH HTTP API）
    - stages.py（composition Celery 管线）
    共同调用，规则统一于本文件。
    """
    h, w = img_bgr.shape[:2]

    if not (settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL):
        raise RuntimeError("ZhipuAI GLM not configured")

    lineart = generate_lineart(img_bgr)
    b64 = encode_bgr_to_base64(img_bgr)

    model = settings.ZHIPU_MODEL.strip() or "glm-5v-turbo"
    url = _build_chat_url(settings.ZHIPU_BASE_URL)

    if llm_analysis_text:
        prompt = GUIDED_QCZH_PROMPT_TEMPLATE.format(
            llm_analysis=llm_analysis_text[:2000]
        )
        guided_text = llm_analysis_text
        logger.info("QCZH guided mode: using LLM analysis text (%d chars)", len(llm_analysis_text))
    else:
        glm_text = _glm_qczh_pre_analysis(img_bgr)
        if glm_text:
            prompt = GUIDED_QCZH_PROMPT_TEMPLATE.format(
                llm_analysis=glm_text[:2000]
            )
            guided_text = glm_text
            logger.info("QCZH standalone → guided: GLM pre-analysis (%d chars)", len(glm_text))
        else:
            prompt = QICHENGZHUANHE_PROMPT
            guided_text = ""
            logger.info("QCZH standalone fallback: using full comprehensive prompt (Qwen unavailable)")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "stream": False,
        "max_tokens": 8192,
        "temperature": 0.15,
    }

    headers = {
        "Authorization": f"Bearer {settings.ZHIPU_API_KEY}",
        "Content-Type": "application/json",
    }

    import re

    # ---- 5b. 调用 LLM（带重试）----
    max_retries = 2
    last_error = None
    for attempt in range(1, max_retries + 2):
        try:
            with httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0, read=150.0)) as client:
                r = client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()

            # 调试：打印原始响应
            logger.info("LLM raw response: model=%s, finish_reason=%s, usage=%s",
                        model,
                        data["choices"][0].get("finish_reason"),
                        data.get("usage"))

            message = data["choices"][0]["message"]
            raw_content = message.get("content") or ""

            # glm-5v-turbo 是推理模型：content 可能为空，所有内容在 reasoning_content 中
            finish_reason = data["choices"][0].get("finish_reason", "")
            if (not raw_content or not raw_content.strip()) and finish_reason == "length":
                # finish_reason=length 意味着输出被截断，content 一定为空
                # 尝试从 reasoning_content 中提取 JSON
                reasoning = message.get("reasoning_content") or ""
                if reasoning:
                    logger.info("content 为空 (finish_reason=length)，尝试从 reasoning_content 提取 JSON, reasoning_len=%d", len(reasoning))
                    # 从 reasoning_content 中提取 JSON 块
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', reasoning)
                    if json_match:
                        raw_content = json_match.group(1)
                        logger.info("从 reasoning_content 提取到 JSON 块, len=%d", len(raw_content))
                    else:
                        # 尝试找到最后一个 { ... } 块
                        brace_match = re.search(r'\{[\s\S]*\}', reasoning)
                        if brace_match:
                            raw_content = brace_match.group(0)
                            logger.info("从 reasoning_content 提取到 JSON 对象, len=%d", len(raw_content))

            if not raw_content or not raw_content.strip():
                logger.error("LLM 返回空内容, finish_reason=%s, reasoning_len=%d",
                             finish_reason, len(message.get("reasoning_content", "")))
                raise ValueError("LLM 返回空内容")

            # 清洗中文引号，避免 JSON 解析失败
            raw_content = raw_content.replace('"', '"').replace('"', '"')

            logger.info("起承转合 LLM response OK, model=%s, len=%d, attempt=%d",
                        model, len(raw_content), attempt)
            break
        except Exception as e:
            last_error = e
            logger.warning("LLM 调用失败 (attempt %d/%d): %s", attempt, max_retries + 1, e)
            if attempt <= max_retries:
                import time
                time.sleep(2 * attempt)  # 递增等待
    else:
        raise RuntimeError(f"LLM 调用连续 {max_retries + 1} 次失败: {last_error}") from last_error

    # ---- 6. 解析 JSON（容错）----
    llm_result = None
    parse_error = None

    # 策略1: 尝试提取 ```json ... ``` 块
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_content)
    if json_match:
        try:
            llm_result = _json.loads(json_match.group(1))
        except _json.JSONDecodeError as e:
            parse_error = e
            logger.warning("JSON 块解析失败: %s", e)

    # 策略2: 尝试直接解析整个内容
    if llm_result is None:
        try:
            llm_result = _json.loads(raw_content)
        except _json.JSONDecodeError as e:
            parse_error = e
            logger.warning("直接 JSON 解析失败: %s", e)

    # 策略3: 尝试提取第一个 { ... } 块
    if llm_result is None:
        brace_match = re.search(r'\{[\s\S]*\}', raw_content)
        if brace_match:
            try:
                llm_result = _json.loads(brace_match.group(0))
                logger.info("通过花括号提取成功解析 JSON")
            except _json.JSONDecodeError:
                pass

    if llm_result is None:
        raise RuntimeError(
            f"无法解析 LLM 返回的 JSON。原始内容前 500 字符: {raw_content[:500]}"
        ) from parse_error

    logger.debug("LLM result keys: %s", list(llm_result.keys()))

    # ---- 6. 解析并构建结果 ----
    parsed = _parse_llm_result(llm_result, w, h, guided_analysis_text=guided_text)

    # ---- 7. 构建箭头 + 绘制 ----
    display_labels = ["起", "承", "转", "合"] if parsed.get("curve_points") else parsed["arrow_labels"]
    arrow_canvas = draw_arrows_on_lineart(lineart, parsed["arrows"], display_labels,
                                           curve_points=parsed.get("curve_points"))

    parsed["arrow_canvas"] = arrow_canvas
    parsed["model"] = model
    parsed["raw_response"] = raw_content
    parsed["qwen_analysis"] = guided_text

    return parsed
