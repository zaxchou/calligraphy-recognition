"""
qwen-vl-ocr 三路路由模块 (v9)
将 test_qwen_vl_ocr_v9.py 的逻辑封装为生产级模块

三路 OCR + 每路2遍并集 + 列感知去重
- 主路：全图 OCR
- 补路1：右半 x>75%，2遍并集
- 补路2：右三 x>65%，2遍并集
- 补路3：左三 x<35%，2遍并集
"""

import os, sys, cv2, time, math, base64, io, tempfile
import numpy as np
import httpx
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 禁用解压炸弹检查
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# ── 依赖导入 ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"


# ── 编码 ──────────────────────────────────────────────────────────────────
def encode_image(image_path: str, max_side: int = 2048, quality: int = 85) -> Tuple[str, float]:
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


def qwen_vl_ocr_from_b64(b64: str, scale_ratio: float) -> Tuple[List[Dict], float]:
    """直接用 base64 调用 qwen-vl-ocr（scale_ratio 已计算好）"""
    payload = {
        "model": "qwen-vl-ocr",
        "input": {"messages": [{"role": "user", "content": [{
            "image": f"data:image/jpeg;base64,{b64}",
            "min_pixels": 32 * 28 * 28,
            "max_pixels": 32 * 28 * 28 * 10,
        }]}]},
        "parameters": {"ocr_options": {"task": "advanced_recognition"}, "result_format": "message"}
    }
    url = f"{DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        result = resp.json()
    elapsed = time.time() - t0

    words_info = []
    try:
        choices = result.get("output", {}).get("choices", [])
        if choices:
            for item in choices[0].get("message", {}).get("content", []):
                if "ocr_result" in item:
                    words_info = item["ocr_result"].get("words_info", [])
                    break
    except Exception:
        pass

    pixel_words = []
    for w_info in words_info:
        text = w_info.get("text", "")
        location = w_info.get("location", [])
        rotate_rect = w_info.get("rotate_rect", [])
        if len(location) == 8:
            orig_pts = []
            for i in range(0, 8, 2):
                orig_pts.append(int(round(location[i] / scale_ratio)))
                orig_pts.append(int(round(location[i+1] / scale_ratio)))
            xs = orig_pts[0::2]; ys = orig_pts[1::2]
            pixel_words.append({
                "text": text,
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "location": orig_pts,
            })
        elif len(rotate_rect) == 5:
            cx, cy, bw, bh, angle = [v / scale_ratio for v in rotate_rect]
            cos_a, sin_a = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            hw, hh = bw / 2, bh / 2
            corners = []
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
                corners.extend([cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a])
            xs = [corners[i] for i in range(0, 8, 2)]
            ys = [corners[i] for i in range(1, 8, 2)]
            pixel_words.append({
                "text": text,
                "bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                "location": [int(round(c)) for c in corners],
                "rotate_rect": [cx, cy, bw, bh, angle],
                "angle": angle,
            })
    return pixel_words, elapsed


def encode_image_to_b64(img_bgr: np.ndarray, max_side: int = 2048) -> Tuple[str, float]:
    """直接用 numpy array 编码为 base64"""
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_rgb)
    w, h = img_pil.size
    scale_ratio = 1.0
    longest = max(w, h)
    if longest > max_side:
        scale_ratio = max_side / float(longest)
        img_pil = img_pil.resize((int(w * scale_ratio), int(h * scale_ratio)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img_pil.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode(), scale_ratio


# ── qwen-vl-ocr ────────────────────────────────────────────────────────────
def qwen_vl_ocr(image_path: str, max_side: int = 2048) -> Tuple[List[Dict], float]:
    """调用 qwen-vl-ocr，返回 (words, elapsed_time)"""
    b64, scale_ratio = encode_image(image_path, max_side=max_side)
    payload = {
        "model": "qwen-vl-ocr",
        "input": {"messages": [{"role": "user", "content": [{
            "image": f"data:image/jpeg;base64,{b64}",
            "min_pixels": 32 * 28 * 28,
            "max_pixels": 32 * 28 * 28 * 10,
        }]}]},
        "parameters": {"ocr_options": {"task": "advanced_recognition"}, "result_format": "message"}
    }
    url = f"{DASHSCOPE_BASE_URL}/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
    t0 = time.time()
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        result = resp.json()
    elapsed = time.time() - t0

    words_info = []
    try:
        choices = result.get("output", {}).get("choices", [])
        if choices:
            for item in choices[0].get("message", {}).get("content", []):
                if "ocr_result" in item:
                    words_info = item["ocr_result"].get("words_info", [])
                    break
    except Exception:
        pass

    pixel_words = []
    for w_info in words_info:
        text = w_info.get("text", "")
        location = w_info.get("location", [])
        rotate_rect = w_info.get("rotate_rect", [])
        if len(location) == 8:
            orig_pts = []
            for i in range(0, 8, 2):
                orig_pts.append(int(round(location[i] / scale_ratio)))
                orig_pts.append(int(round(location[i+1] / scale_ratio)))
            xs = orig_pts[0::2]; ys = orig_pts[1::2]
            pixel_words.append({
                "text": text,
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "location": orig_pts,
            })
        elif len(rotate_rect) == 5:
            cx, cy, bw, bh, angle = [v / scale_ratio for v in rotate_rect]
            cos_a, sin_a = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            hw, hh = bw / 2, bh / 2
            corners = []
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
                corners.extend([cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a])
            xs = [corners[i] for i in range(0, 8, 2)]
            ys = [corners[i] for i in range(1, 8, 2)]
            pixel_words.append({
                "text": text,
                "bbox": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
                "location": [int(round(c)) for c in corners],
                "rotate_rect": [cx, cy, bw, bh, angle],
                "angle": angle,
            })
    return pixel_words, elapsed


def qwen_vl_ocr_2pass_from_array(crop_img: np.ndarray, max_side: int = 2048) -> Tuple[List[Dict], float]:
    """同一张图跑2遍，取并集（直接用 numpy array，不写磁盘）"""
    b64, scale_ratio = encode_image_to_b64(crop_img, max_side=max_side)
    results, times = [], []
    for _ in range(2):
        words, t = qwen_vl_ocr_from_b64(b64, scale_ratio)
        results.append(words)
        times.append(t)
    all_words = results[0] + results[1]
    seen = {}
    for w in all_words:
        key = (w["text"], int(w["bbox"][0] / 50))
        if key not in seen:
            seen[key] = w
    return list(seen.values()), sum(times)


def qwen_vl_ocr_2pass(crop_path: str, max_side: int = 2048) -> Tuple[List[Dict], float]:
    """同一张图跑2遍，取并集"""
    results, times = [], []
    for _ in range(2):
        words, t = qwen_vl_ocr(crop_path, max_side=max_side)
        results.append(words)
        times.append(t)
    all_words = results[0] + results[1]
    seen = {}
    for w in all_words:
        key = (w["text"], int(w["bbox"][0] / 50))
        if key not in seen:
            seen[key] = w
    return list(seen.values()), sum(times)


# ── 去重 v6 ───────────────────────────────────────────────────────────────
def should_merge_v6(a: Dict, b: Dict) -> bool:
    ax1, ay1, ax2, ay2 = a["bbox"]
    bx1, by1, bx2, by2 = b["bbox"]
    a_w, a_h = ax2 - ax1, ay2 - ay1
    b_w, b_h = bx2 - bx1, by2 - by1
    a_vert = a_h > a_w * 1.5
    b_vert = b_h > b_w * 1.5
    if a_vert and b_vert:
        a_cx = (ax1 + ax2) / 2
        b_cx = (bx1 + bx2) / 2
        col_dist = abs(a_cx - b_cx)
        max_w = max(a_w, b_w)
        if col_dist < max_w * 0.7:
            overlap_y = max(0, min(ay2, by2) - max(ay1, by1))
            if overlap_y / max(a_h, b_h) > 0.6:
                return True
        return False
    elif not a_vert and not b_vert:
        a_cy = (ay1 + ay2) / 2
        b_cy = (by1 + by2) / 2
        row_dist = abs(a_cy - b_cy)
        max_h = max(a_h, b_h)
        if row_dist < max_h * 0.7:
            overlap_x = max(0, min(ax2, bx2) - max(ax1, bx1))
            if overlap_x / max(a_w, b_w) > 0.6:
                return True
        return False
    else:
        inter = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
        union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
        return (inter / union) > 0.5 if union > 0 else False


def dedup_v6(words: List[Dict]) -> List[Dict]:
    result = list(words)
    merged = True
    while merged:
        merged = False
        best_i, best_j = -1, -1
        for i in range(len(result)):
            for j in range(i + 1, len(result)):
                if should_merge_v6(result[i], result[j]):
                    best_i, best_j = i, j
        if best_i >= 0:
            a = result[best_i]; b = result[best_j]
            merged_text = a["text"] + "+" + b["text"]
            new_bbox = [min(a["bbox"][0], b["bbox"][0]), min(a["bbox"][1], b["bbox"][1]),
                        max(a["bbox"][2], b["bbox"][2]), max(a["bbox"][3], b["bbox"][3])]
            result[best_i] = {"text": merged_text, "bbox": new_bbox}
            del result[best_j]
            merged = True
    return result


# ── 辅助 ──────────────────────────────────────────────────────────────────
def x_center(bbox) -> float:
    return (bbox[0] + bbox[2]) / 2

def col_width(bbox) -> float:
    return bbox[2] - bbox[0]

def y_overlap_pct(a_bbox, b_bbox) -> float:
    a_top, a_bot = a_bbox[1], a_bbox[3]
    b_top, b_bot = b_bbox[1], b_bbox[3]
    overlap_top = max(a_top, b_top)
    overlap_bot = min(a_bot, b_bot)
    if overlap_bot <= overlap_top:
        return 0.0
    overlap_h = overlap_bot - overlap_top
    min_h = min(a_bot - a_top, b_bot - b_top)
    return overlap_h / min_h if min_h > 0 else 0.0

def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    set_a = set(a); set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    return intersection / max(len(set_a), len(set_b))


# ── 主流程 ────────────────────────────────────────────────────────────────
class OCRRouter:
    """
    三路 OCR 路由：主路全图 + 补路（右半/右三/左三），各2遍并集

    使用方式：
        router = OCRRouter()
        result = router.process(image_path, image_width, image_height)
        # result = {
        #   "inscription_content": "...",  # 所有识别文字合并文本
        #   "ocr_items": [...],             # 每条检测的详细信息
        #   "full_count": 4,               # 主路检测数
        #   "crop_count": 7,                # 补路追加数
        #   "deduped_count": 8,            # 去重后总数
        #   "crop_details": {"右半": 2, "右三": 4, "左三": 1},
        # }
    """

    def __init__(
        self,
        min_text_sim: float = 0.30,
        col_width_ratio: float = 0.7,
        pad_base: float = 0.12,
    ):
        self.MIN_TEXT_SIM = min_text_sim
        self.COL_WIDTH_RATIO = col_width_ratio
        self.PAD_BASE = pad_base
        # 三条补路配置：[名称, 起始比例, 结束比例, 是否从右边截取]
        self.crop_configs = [
            ("右半", 0.75, 1.00, True),
            ("右三", 0.65, 1.00, True),
            ("左三", 0.00, 0.35, False),
        ]

    def process(self, img_path: str, image_width: int, image_height: int) -> Dict:
        """
        处理单张图，返回 OCR 结果
        """
        img_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return {"success": False, "error": "cannot read image"}
        h, w = image_height, image_width

        # ── 主路：全图 OCR ───────────────────────────────────────────────
        full_words, full_time = qwen_vl_ocr(img_path, max_side=2048)

        full_col_centers = [(fw, x_center(fw["bbox"]), col_width(fw["bbox"])) for fw in full_words]
        full_max_x2 = max((wp["bbox"][2] for wp in full_words), default=0)
        full_min_x1 = min((wp["bbox"][0] for wp in full_words), default=0)

        # ── 补路 ────────────────────────────────────────────────────────
        all_filtered_crop = []
        crop_times = {name: 0.0 for name, *_ in self.crop_configs}
        crop_counts = {name: 0 for name, *_ in self.crop_configs}

        for crop_name, x_start_ratio, x_end_ratio, from_right in self.crop_configs:
            if from_right:
                x_start = int(w * x_start_ratio)
                crop_img = img_bgr[:, x_start:]
            else:
                x_end = int(w * x_end_ratio)
                crop_img = img_bgr[:, :x_end]

            crop_h, crop_w = crop_img.shape[:2]

            crop_words, crop_time = qwen_vl_ocr_2pass_from_array(crop_img, max_side=2048)
            crop_times[crop_name] = crop_time

            # 坐标转回原图
            offset_x = x_start if from_right else 0
            for cw in crop_words:
                orig_bbox = cw["bbox"]
                cw["bbox"] = [
                    orig_bbox[0] + offset_x,
                    orig_bbox[1],
                    orig_bbox[2] + offset_x,
                    orig_bbox[3],
                ]
                cw["_from_crop"] = True
                cw["_crop_name"] = crop_name

            # 列感知追加过滤
            for cw in crop_words:
                cw_xc = x_center(cw["bbox"])
                cw_cw = col_width(cw["bbox"])
                cw_bbox = cw["bbox"]
                max_sim = 0.0
                same_col_fw = None
                for fw, fx_c, fw_cw in full_col_centers:
                    sim = text_similarity(fw["text"], cw["text"])
                    if sim > max_sim:
                        max_sim = sim
                    col_dist = abs(cw_xc - fx_c)
                    same_col_width = max(cw_cw, fw_cw)
                    y_olap = y_overlap_pct(cw_bbox, fw["bbox"])
                    if col_dist < same_col_width * self.COL_WIDTH_RATIO and y_olap > 0.20:
                        same_col_fw = fw
                        break

                is_new_col = (same_col_fw is None)
                is_different_text = (max_sim < self.MIN_TEXT_SIM)
                char_overlap = len(set(cw["text"]) & set(same_col_fw["text"])) if same_col_fw else 0
                is_totally_different = (char_overlap == 0)
                if is_different_text and (is_new_col or is_totally_different):
                    all_filtered_crop.append(cw)
                    crop_counts[crop_name] += 1

        # ── 合并去重 ──────────────────────────────────────────────────
        deduped_full = dedup_v6(full_words)
        deduped = dedup_v6(deduped_full + all_filtered_crop)

        # ── 动态 padding ─────────────────────────────────────────────
        pad_infos = []
        for w_info in deduped:
            bbox = w_info["bbox"]
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            aspect = bw / bh if bh > 0 else 1
            pad_x = max(2, int(bw * self.PAD_BASE))
            pad_y = max(2, int(bh * self.PAD_BASE))
            pad_infos.append({
                "text": w_info["text"],
                "bbox": bbox,
                "aspect": aspect,
                "pad_x": pad_x,
                "pad_y": pad_y,
                "from_crop": w_info.get("_from_crop", False),
                "crop_name": w_info.get("_crop_name", ""),
            })

        # 合并文字内容
        content_parts = []
        for pi in pad_infos:
            tag = f"[{pi['crop_name']}]" if pi.get("from_crop") else ""
            content_parts.append(f"{tag}{pi['text']}")

        return {
            "success": True,
            "inscription_content": " | ".join(content_parts),
            "ocr_items": pad_infos,
            "full_count": len(deduped_full),
            "crop_count": len(all_filtered_crop),
            "deduped_count": len(deduped),
            "crop_details": crop_counts,
            "full_time": full_time,
            "crop_times": crop_times,
            "total_time": full_time + sum(crop_times.values()),
        }
