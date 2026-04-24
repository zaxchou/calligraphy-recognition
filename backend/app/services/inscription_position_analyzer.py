"""
题跋位置分析模块 v2
支持8种非排他形式类型分类：规则初筛 + Qwen VL Plus 视觉精判
"""

import os, io, time, base64, json
from typing import List, Dict, Tuple, Optional
from PIL import Image
import httpx

# ── 8种形式类型定义 ──────────────────────────────────────────────────────────
FORM_TYPES = [
    {
        "code": 1,
        "name": "边角规整式",
        "description": "题款位于画面边角，形状规整，不侵入主体画面，保持了画面的主体空间，是传统文人画常见的题跋方式。",
        "method": "rule",
        "vl_status": None,
    },
    {
        "code": 2,
        "name": "拦边封角式",
        "description": "题款沿画面边缘或角落布置，形成对画面边角的封锁，与绘画主体相互呼应，凝聚画面气势。",
        "method": "rule",
        "vl_status": None,
    },
    {
        "code": 3,
        "name": "化虚为实/填充式",
        "description": "题款填补画面大面积留白，将虚无的空间转化为实在的书法存在，使留白与文字形成虚实对比。",
        "method": "vl",
        "vl_status": None,
    },
    {
        "code": 4,
        "name": "重力平衡式",
        "description": "画面重心偏向某一侧，题款压阵于另一侧，通过文字的视觉重量平衡画面重心偏移，形成稳定的视觉构图。",
        "method": "vl",
        "vl_status": None,
    },
    {
        "code": 5,
        "name": "因势随形/穿插式",
        "description": "题款穿插于物象之间，顺应画面走势，与花鸟、山石等绘画内容相互穿插你退我让，体现书画同源的艺术追求。",
        "method": "rule",
        "vl_status": None,
    },
    {
        "code": 6,
        "name": "侵入画位/喧宾夺主式",
        "description": "题款极度扩张，占据画面核心位置，成为视觉焦点，书法反而成为画面的主角，绘画退居辅助地位。",
        "method": "vl",
        "vl_status": None,
    },
    {
        "code": 7,
        "name": "长篇排布/画材填空式",
        "description": "题跋长篇密布，专门填补在画材（松干、山石、建筑等）的空隙处，将自然物象的空隙转化为书法空间。",
        "method": "vl",
        "vl_status": None,
    },
    {
        "code": 8,
        "name": "从左起笔式",
        "description": "打破传统从右向左的书画习惯，题款从画面左旁起笔向右延伸，构图形式新颖独特。",
        "method": "rule",
        "vl_status": None,
    },
]

# ── VL配置 ───────────────────────────────────────────────────────────────────
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashcope.aliyuncs.com/api/v1"
VL_TIMEOUT = 180.0


# ── 图像编码 ─────────────────────────────────────────────────────────────────
def _encode_image(image_path: str, max_side: int = 2048, quality: int = 85) -> Tuple[str, float]:
    """将图像编码为base64，返回(base64字符串, 缩放比例)"""
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
        return base64.b64encode(buf.getvalue()).decode("utf-8"), scale_ratio


# ── 几何计算工具 ─────────────────────────────────────────────────────────────
def _get_text_line_start_x(inscription_regions: List[Dict], image_width: int) -> float:
    """
    估算题跋文字列起始x坐标（归一化）。
    取所有文字块最左边的x中心位置。
    """
    min_start_x = 1.0
    for region in inscription_regions:
        points = region.get("points", [])
        if not points:
            x1 = region.get("x1", 0)
            x2 = region.get("x2", 0)
        else:
            xs = [p["x"] for p in points]
            x1, x2 = min(xs), max(xs)
        line_center_x = (x1 + x2) / 2
        norm_x = line_center_x / image_width
        if norm_x < min_start_x:
            min_start_x = norm_x
    return min_start_x


def _classify_by_rules(
    inscription_regions: List[Dict],
    painting_regions: List[Dict],
    edge_distance: Dict[str, float],
    coverage_ratio: float,
    overlap_ratio: float,
    image_width: int,
    image_height: int,
) -> Dict[int, Dict]:
    """
    纯几何规则判断8种类型。
    返回 {code: {"matched": bool, "method": "rule", "vl_status": None}} 的子集（仅规则可判的类型）。
    """
    results = {}

    # ── 类型1：边角规整式 ──────────────────────────────────────────────
    # 贴近边角 + 区域少 + 不侵入主体
    min_edge = min(edge_distance.values()) if edge_distance else 1.0
    region_count = len(inscription_regions)
    matched_1 = (min_edge < 0.12) and (region_count <= 2) and (overlap_ratio < 0.10)
    results[1] = {"matched": bool(matched_1), "method": "rule", "vl_status": None}

    # ── 类型2：拦边封角式 ──────────────────────────────────────────────
    # 双边靠边缘 + 角落汇聚
    close_edges = sum(1 for d in edge_distance.values() if d < 0.15)
    matched_2 = close_edges >= 2
    results[2] = {"matched": bool(matched_2), "method": "rule", "vl_status": None}

    # ── 类型5：因势随形/穿插式 ────────────────────────────────────────
    # overlap_ratio > 0.3
    matched_5 = overlap_ratio > 0.30
    results[5] = {"matched": bool(matched_5), "method": "rule", "vl_status": None}

    # ── 类型8：从左起笔式 ──────────────────────────────────────────────
    # 文字列起始x < 画面宽度33%
    if inscription_regions:
        start_x = _get_text_line_start_x(inscription_regions, image_width)
        matched_8 = start_x < 0.33
    else:
        matched_8 = False
    results[8] = {"matched": bool(matched_8), "method": "rule", "vl_status": None}

    return results


# ── VL分类 ───────────────────────────────────────────────────────────────────
def _classify_by_vl(
    image_path: str,
    coverage_ratio: float,
    overlap_ratio: float,
    edge_distance: Dict[str, float],
    region_count: int,
) -> Tuple[Dict[int, Dict], str]:
    """
    调用 Qwen VL Plus 一次性判断类型3/4/6/7。
    返回 ({code: {"matched": bool, "method": "vl", "vl_status": "ok"|"timeout"}}, vl_overall_status)
    """
    b64, _ = _encode_image(image_path)
    min_pixels = 28 * 28 * 32
    max_pixels = min_pixels * 10

    prompt = f"""你是一位中国书画构图分析专家。请分析这幅花鸟/山水/人物画中的题跋（书法文字）布局，判断它是否符合以下4种形式类型：

【类型3：化虚为实/填充式】
定义：题款填补画面大面积留白，将虚无的空间转化为实在的书法存在，使留白与文字形成虚实对比。
判断要点：画面是否有大面积留白（超过画面30%以上），题跋正好填补在这些留白区域。

【类型4：重力平衡式】
定义：画面重心偏向某一侧，题款压阵于另一侧，通过文字的视觉重量平衡画面重心偏移，形成稳定的视觉构图。
判断要点：画面重心是否明显偏向某一侧（如画面偏下、偏左或偏右），题跋是否恰好压在对侧形成平衡。

【类型6：侵入画位/喧宾夺主式】
定义：题款极度扩张，占据画面核心位置，成为视觉焦点，书法反而成为画面的主角，绘画退居辅助地位。
判断要点：题跋面积是否非常大（覆盖画面15%以上）且位于画面中央或视觉核心区。

【类型7：长篇排布/画材填空式】
定义：题跋长篇密布，专门填补在画材（松干、山石、建筑等）的空隙处，将自然物象的空隙转化为书法空间。
判断要点：画面中是否存在明显的画材空隙（如松干间、山石间、屋檐下），题跋是否正好填补在这些空隙中。

已知几何指标（仅供参考辅助判断）：
- coverage_ratio（题跋覆盖率）: {coverage_ratio:.4f}
- overlap_ratio（题跋与绘画重叠率）: {overlap_ratio:.4f}
- 题跋区域数量: {region_count}
- 左边缘距离（归一化）: {edge_distance.get('left', 0):.4f}
- 右边缘距离（归一化）: {edge_distance.get('right', 0):.4f}
- 上边缘距离（归一化）: {edge_distance.get('top', 0):.4f}
- 下边缘距离（归一化）: {edge_distance.get('bottom', 0):.4f}

请仔细观察图像，综合几何指标和视觉语义，判断每种类型是否成立。
返回JSON格式（必须是可以被python/json解析的纯JSON，不要有markdown标记）：
{{
  "results": [
    {{"code": 3, "matched": true或false, "reason": "判断理由，1-2句话"}},
    {{"code": 4, "matched": true或false, "reason": "判断理由，1-2句话"}},
    {{"code": 6, "matched": true或false, "reason": "判断理由，1-2句话"}},
    {{"code": 7, "matched": true或false, "reason": "判断理由，1-2句话"}}
  ]
}}"""

    payload = {
        "model": "qwen-vl-plus",
        "input": {
            "messages": [{
                "role": "user",
                "content": [
                    {"image": f"data:image/jpeg;base64,{b64}", "min_pixels": min_pixels, "max_pixels": max_pixels},
                    {"text": prompt}
                ]
            }]
        },
        "parameters": {"result_format": "message"}
    }
    url = f"{DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}

    results = {}
    vl_status = "timeout"
    t0 = time.time()

    try:
        with httpx.Client(timeout=httpx.Timeout(VL_TIMEOUT, connect=10.0)) as client:
            resp = client.post(url, headers=headers, json=payload)
            elapsed = time.time() - t0
            result = resp.json()
        vl_status = "ok"

        try:
            choices = result.get("output", {}).get("choices", [])
            if choices:
                content_text = ""
                for item in choices[0].get("message", {}).get("content", []):
                    if isinstance(item, dict):
                        content_text += item.get("text", "")
                    elif isinstance(item, str):
                        content_text += item

                # 提取JSON
                json_start = content_text.find("{")
                json_end = content_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content_text[json_start:json_end]
                    parsed = json.loads(json_str)
                    for r in parsed.get("results", []):
                        code = r.get("code")
                        matched = bool(r.get("matched", False))
                        if code in (3, 4, 6, 7):
                            results[code] = {"matched": matched, "method": "vl", "vl_status": "ok"}
        except Exception as e:
            vl_status = "timeout"

    except httpx.TimeoutException:
        vl_status = "timeout"
    except Exception:
        vl_status = "timeout"

    # 填充默认值（超时或解析失败时）
    for code in (3, 4, 6, 7):
        if code not in results:
            results[code] = {"matched": False, "method": "vl", "vl_status": vl_status}

    return results, vl_status


# ── 主函数 ───────────────────────────────────────────────────────────────────
def analyze_inscription_position(
    regions: Dict,
    image_width: int,
    image_height: int,
    image_path: Optional[str] = None,
) -> Dict:
    """
    分析题跋在画面中的位置和布局形式（非排他8类型）。

    Args:
        regions: 区域数据，包含 inscription_regions / painting_regions
        image_width: 图像宽度
        image_height: 图像高度
        image_path: 图像路径（用于VL分类，可选）

    Returns:
        {
            "position": "左上/...",
            "coverage_ratio": 0.12,
            "overlap_ratio": 0.05,
            "edge_distance": {...},
            "vl_overall_status": "ok",
            "form_types": [
                {"code": 1, "name": "...", "matched": true, "method": "rule", "vl_status": null, "description": "..."},
                ...
            ]
        }
    """
    inscription_regions = regions.get("inscription_regions", [])
    painting_regions = regions.get("painting_regions", [])

    # ── 无题跋 ──────────────────────────────────────────────────────────
    if not inscription_regions:
        return {
            "position": "无题跋",
            "coverage_ratio": 0.0,
            "overlap_ratio": 0.0,
            "edge_distance": {},
            "vl_overall_status": "ok",
            "form_types": [
                {**FORM_TYPES[0], "matched": False},
                {**FORM_TYPES[1], "matched": False},
                {**FORM_TYPES[2], "matched": False},
                {**FORM_TYPES[3], "matched": False},
                {**FORM_TYPES[4], "matched": False},
                {**FORM_TYPES[5], "matched": False},
                {**FORM_TYPES[6], "matched": False},
                {**FORM_TYPES[7], "matched": False},
            ]
        }

    # ── 计算几何指标 ───────────────────────────────────────────────────
    all_points = []
    for region in inscription_regions:
        if "points" in region and isinstance(region["points"], list):
            all_points.extend(region["points"])

    if not all_points:
        return {
            "position": "未知",
            "coverage_ratio": 0.0,
            "overlap_ratio": 0.0,
            "edge_distance": {},
            "vl_overall_status": "ok",
            "form_types": [
                {**FORM_TYPES[0], "matched": False},
                {**FORM_TYPES[1], "matched": False},
                {**FORM_TYPES[2], "matched": False},
                {**FORM_TYPES[3], "matched": False},
                {**FORM_TYPES[4], "matched": False},
                {**FORM_TYPES[5], "matched": False},
                {**FORM_TYPES[6], "matched": False},
                {**FORM_TYPES[7], "matched": False},
            ]
        }

    min_x = min(p["x"] for p in all_points)
    max_x = max(p["x"] for p in all_points)
    min_y = min(p["y"] for p in all_points)
    max_y = max(p["y"] for p in all_points)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # 位置判断
    position = _determine_position(center_x, center_y, image_width, image_height)

    # 边缘距离
    edge_distance = {
        "left": min_x / image_width,
        "right": (image_width - max_x) / image_width,
        "top": min_y / image_height,
        "bottom": (image_height - max_y) / image_height,
    }

    # 覆盖率
    inscription_area = _calculate_regions_area(inscription_regions)
    total_area = image_width * image_height
    coverage_ratio = inscription_area / total_area if total_area > 0 else 0.0

    # 重叠率
    overlap_ratio = _calculate_overlap_ratio(inscription_regions, painting_regions)

    # ── 规则初筛（类型1/2/5/8）────────────────────────────────────────
    rule_results = _classify_by_rules(
        inscription_regions, painting_regions,
        edge_distance, coverage_ratio, overlap_ratio,
        image_width, image_height
    )

    # ── VL精判（类型3/4/6/7）──────────────────────────────────────────
    vl_results = {}
    vl_overall_status = "ok"
    if image_path and os.path.exists(image_path):
        vl_results, vl_status = _classify_by_vl(
            image_path, coverage_ratio, overlap_ratio,
            edge_distance, len(inscription_regions)
        )
        if vl_status == "timeout":
            vl_overall_status = "partial_timeout"
    else:
        # 无image_path时，类型3/4/6/7 保守置false
        for code in (3, 4, 6, 7):
            vl_results[code] = {"matched": False, "method": "vl", "vl_status": "timeout"}
        vl_overall_status = "all_timeout"

    # ── 合并所有类型结果 ───────────────────────────────────────────────
    all_results = {}
    all_results.update(rule_results)     # 1, 2, 5, 8
    all_results.update(vl_results)       # 3, 4, 6, 7

    # 特殊：coverage_ratio极高时，类型6自动成立（喧宾夺主）
    if coverage_ratio > 0.25:
        all_results[6] = {"matched": True, "method": "rule", "vl_status": None}

    # 构建 form_types 数组
    form_types = []
    for ft in FORM_TYPES:
        code = ft["code"]
        if code in all_results:
            r = all_results[code]
            form_types.append({
                "code": code,
                "name": ft["name"],
                "description": ft["description"],
                "matched": r["matched"],
                "method": r["method"],
                "vl_status": r.get("vl_status"),
            })
        else:
            form_types.append({**ft, "matched": False})

    return {
        "position": position,
        "coverage_ratio": round(coverage_ratio, 4),
        "overlap_ratio": round(overlap_ratio, 4),
        "edge_distance": {k: round(v, 4) for k, v in edge_distance.items()},
        "vl_overall_status": vl_overall_status,
        "form_types": form_types,
    }


# ── 工具函数 ─────────────────────────────────────────────────────────────────
def _determine_position(center_x: float, center_y: float, image_width: int, image_height: int) -> str:
    nx = center_x / image_width
    ny = center_y / image_height
    lt, rt, tp, bt = 0.33, 0.67, 0.33, 0.67
    if nx < lt and ny < tp: return "左上"
    elif nx > rt and ny < tp: return "右上"
    elif nx < lt and ny > bt: return "左下"
    elif nx > rt and ny > bt: return "右下"
    elif nx < lt: return "左侧"
    elif nx > rt: return "右侧"
    elif ny < tp: return "上方"
    elif ny > bt: return "下方"
    return "中间"


def _calculate_regions_area(regions: List[Dict]) -> float:
    total = 0.0
    for r in regions:
        if "points" in r and len(r["points"]) >= 3:
            total += _polygon_area(r["points"])
        elif "x1" in r and "y1" in r and "x2" in r and "y2" in r:
            total += (r["x2"] - r["x1"]) * (r["y2"] - r["y1"])
    return total


def _polygon_area(points: List[Dict]) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i]["x"] * points[j]["y"]
        area -= points[j]["x"] * points[i]["y"]
    return abs(area) / 2.0


def _point_in_polygon(point: Dict, polygon: List[Dict]) -> bool:
    x, y = point["x"], point["y"]
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["x"], polygon[i]["y"]
        xj, yj = polygon[j]["x"], polygon[j]["y"]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _calculate_overlap_ratio(inscription_regions: List[Dict], painting_regions: List[Dict]) -> float:
    if not inscription_regions or not painting_regions:
        return 0.0
    overlap_count = 0
    total_count = 0
    for ins_r in inscription_regions:
        pts = ins_r.get("points", [])
        if len(pts) < 3:
            continue
        cx = sum(p["x"] for p in pts) / len(pts)
        cy = sum(p["y"] for p in pts) / len(pts)
        total_count += 1
        for paint_r in painting_regions:
            if "points" in paint_r and len(paint_r["points"]) >= 3:
                if _point_in_polygon({"x": cx, "y": cy}, paint_r["points"]):
                    overlap_count += 1
                    break
    return overlap_count / total_count if total_count > 0 else 0.0


# ── 简化版分析函数（仅规则，不调用VL）──────────────────────────────────────────
def analyze_inscription_position_simple(
    regions: Dict,
    image_width: int,
    image_height: int,
) -> Dict:
    """
    简化版题跋位置分析（仅使用规则，不调用VL）。
    用于手动标注后的快速分析。

    Args:
        regions: 区域数据，包含 inscription_regions / painting_regions
        image_width: 图像宽度
        image_height: 图像高度

    Returns:
        {
            "position": "左上/...",
            "coverage_ratio": 0.12,
            "overlap_ratio": 0.05,
            "edge_distance": {...},
            "margin_left": 0.1,
            "margin_right": 0.2,
            "margin_top": 0.1,
            "margin_bottom": 0.3,
            "vl_overall_status": "ok",
            "form_types": [...]
        }
    """
    inscription_regions = regions.get("inscription_regions", [])
    painting_regions = regions.get("painting_regions", [])

    # 无题跋
    if not inscription_regions:
        return {
            "position": "无题跋",
            "coverage_ratio": 0.0,
            "overlap_ratio": 0.0,
            "edge_distance": {},
            "margin_left": 0,
            "margin_right": 0,
            "margin_top": 0,
            "margin_bottom": 0,
            "vl_overall_status": "ok",
            "form_types": [{**ft, "matched": False} for ft in FORM_TYPES]
        }

    # 计算几何指标
    all_points = []
    for region in inscription_regions:
        if "points" in region and isinstance(region["points"], list):
            all_points.extend(region["points"])

    if not all_points:
        return {
            "position": "未知",
            "coverage_ratio": 0.0,
            "overlap_ratio": 0.0,
            "edge_distance": {},
            "margin_left": 0,
            "margin_right": 0,
            "margin_top": 0,
            "margin_bottom": 0,
            "vl_overall_status": "ok",
            "form_types": [{**ft, "matched": False} for ft in FORM_TYPES]
        }

    min_x = min(p["x"] for p in all_points)
    max_x = max(p["x"] for p in all_points)
    min_y = min(p["y"] for p in all_points)
    max_y = max(p["y"] for p in all_points)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # 位置判断
    position = _determine_position(center_x, center_y, image_width, image_height)

    # 边缘距离（归一化）
    edge_distance = {
        "left": min_x / image_width,
        "right": (image_width - max_x) / image_width,
        "top": min_y / image_height,
        "bottom": (image_height - max_y) / image_height,
    }

    # 边距（像素）
    margin_left = min_x
    margin_right = image_width - max_x
    margin_top = min_y
    margin_bottom = image_height - max_y

    # 覆盖率
    inscription_area = _calculate_regions_area(inscription_regions)
    total_area = image_width * image_height
    coverage_ratio = inscription_area / total_area if total_area > 0 else 0.0

    # 重叠率
    overlap_ratio = _calculate_overlap_ratio(inscription_regions, painting_regions)

    # 规则初筛（类型1/2/5/8）
    rule_results = _classify_by_rules(
        inscription_regions, painting_regions,
        edge_distance, coverage_ratio, overlap_ratio,
        image_width, image_height
    )

    # 类型3/4/6/7（需要VL的）保守置false
    vl_results = {}
    for code in (3, 4, 6, 7):
        vl_results[code] = {"matched": False, "method": "vl", "vl_status": "skipped"}

    # 特殊：coverage_ratio极高时，类型6自动成立（喧宾夺主）
    if coverage_ratio > 0.25:
        vl_results[6] = {"matched": True, "method": "rule", "vl_status": None}

    # 合并所有类型结果
    all_results = {}
    all_results.update(rule_results)     # 1, 2, 5, 8
    all_results.update(vl_results)       # 3, 4, 6, 7

    # 构建 form_types 数组
    form_types = []
    for ft in FORM_TYPES:
        code = ft["code"]
        if code in all_results:
            r = all_results[code]
            form_types.append({
                "code": code,
                "name": ft["name"],
                "description": ft["description"],
                "matched": r["matched"],
                "method": r["method"],
                "vl_status": r.get("vl_status"),
            })
        else:
            form_types.append({**ft, "matched": False})

    return {
        "position": position,
        "coverage_ratio": round(coverage_ratio, 4),
        "overlap_ratio": round(overlap_ratio, 4),
        "edge_distance": {k: round(v, 4) for k, v in edge_distance.items()},
        "margin_left": round(margin_left),
        "margin_right": round(margin_right),
        "margin_top": round(margin_top),
        "margin_bottom": round(margin_bottom),
        "vl_overall_status": "ok",
        "form_types": form_types,
    }
