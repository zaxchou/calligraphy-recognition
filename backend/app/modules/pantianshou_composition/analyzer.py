from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CLIP embedding singleton (lazy-loaded)
# ---------------------------------------------------------------------------
_clip_model = None
_clip_preprocess = None
_clip_device = None


def _load_clip():
    """延迟加载 CLIP 模型，只初始化一次。"""
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_device
    try:
        import torch
        import open_clip
        _clip_device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = "ViT-B-32-quickgelu"
        pretrained = "openai"
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        _clip_model = _clip_model.to(_clip_device).eval()
        logger.info("CLIP model (%s/%s) loaded on %s", model_name, pretrained, _clip_device)
    except ImportError:
        logger.warning("open_clip 未安装，回退到像素展平 embedding。请运行: pip install open-clip-torch")
        _clip_model = None
    except Exception as e:
        logger.error("CLIP 模型加载失败: %s，回退到像素展平 embedding", e)
        _clip_model = None
    return _clip_model, _clip_preprocess, _clip_device


@dataclass
class ImageMetrics:
    width: int
    height: int
    megapixels_bucket: str
    blank_ratio: float
    edge_density: float
    edge_density_std: float
    dominant_orientation_ratio: float
    parallel_warning: bool
    inscription_box: Tuple[int, int, int, int]


def decode_image_bytes(content: bytes) -> np.ndarray:
    data = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("invalid_image")
    return img


def _pixel_fallback_vector(img_bgr: np.ndarray) -> List[float]:
    """原始像素展平 embedding（CLIP 不可用时的降级方案）。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 16), interpolation=cv2.INTER_AREA)
    vec = (small.astype(np.float32) / 255.0).reshape(-1)
    return vec.tolist()


def to_feature_vector_512(img_bgr: np.ndarray) -> List[float]:
    """生成 512 维图像特征向量。

    优先使用 CLIP (ViT-B-32) 语义 embedding，失败时降级到灰度像素展平。
    输出维度固定 512，与现有 Qdrant collection 兼容，无需迁移。
    """
    model, preprocess, device = _load_clip()
    if model is None:
        return _pixel_fallback_vector(img_bgr)

    try:
        import torch
        from PIL import Image

        # BGR -> RGB for PIL
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        # CLIP preprocess & inference
        tensor = preprocess(pil_img).unsqueeze(0).to(device)
        with torch.no_grad():
            features = model.encode_image(tensor)
        # 归一化到单位向量
        features = features / features.norm(dim=-1, keepdim=True)

        vec = features.squeeze(0).cpu().float().tolist()
        # ViT-B-32 输出 512 维，恰好匹配
        if len(vec) != 512:
            logger.warning("CLIP 输出维度 %d ≠ 512，回退到像素展平", len(vec))
            return _pixel_fallback_vector(img_bgr)
        return vec
    except Exception as e:
        logger.error("CLIP 推理失败: %s，回退到像素展平", e)
        return _pixel_fallback_vector(img_bgr)


def compute_metrics(img_bgr: np.ndarray, bucket: str) -> Tuple[ImageMetrics, np.ndarray, np.ndarray]:
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, bw = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    total_pixels = int(bw.size)
    total_blank = int(np.count_nonzero(bw == 255))
    fg = (bw == 0).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    nz = cv2.findNonZero(fg)
    if nz is None or total_pixels <= 0:
        blank_ratio = float(total_blank / max(total_pixels, 1))
    else:
        x, y, ww, hh = cv2.boundingRect(nz)
        pad = int(max(ww, hh) * 0.03) + 6
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + ww + pad)
        y1 = min(h, y + hh + pad)
        inside_blank = int(np.count_nonzero(bw[y0:y1, x0:x1] == 255))
        outside_blank = max(0, total_blank - inside_blank)
        blank_ratio = float(outside_blank / max(total_pixels, 1))

    work_w = 768
    scale = work_w / max(w, 1)
    work_h = max(int(h * scale), 1)
    work = cv2.resize(gray, (work_w, work_h), interpolation=cv2.INTER_AREA)

    edges = cv2.Canny(work, 80, 160)
    edge_density = float(np.mean(edges > 0))

    grid = 8
    cell_h = max(work_h // grid, 1)
    cell_w = max(work_w // grid, 1)
    densities = []
    for i in range(grid):
        for j in range(grid):
            cell = edges[i * cell_h : (i + 1) * cell_h, j * cell_w : (j + 1) * cell_w]
            densities.append(float(np.mean(cell > 0)))
    edge_density_std = float(np.std(densities))

    gx = cv2.Sobel(work, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(work, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=False)
    bins = 12
    hist = np.zeros(bins, dtype=np.float64)
    mask = mag > np.percentile(mag, 70)
    ang_m = ang[mask]
    mag_m = mag[mask]
    if ang_m.size > 0:
        idx = np.floor((ang_m % np.pi) / (np.pi / bins)).astype(int)
        idx = np.clip(idx, 0, bins - 1)
        for i, m in zip(idx, mag_m):
            hist[i] += float(m)
    dom_ratio = float((hist.max() / (hist.sum() + 1e-9)) if hist.sum() > 0 else 0.0)

    parallel_warning = detect_parallel_warning(edges, min_len_ratio=0.35)
    inscription_box = suggest_inscription_box(edges, orig_w=w, orig_h=h)

    metrics = ImageMetrics(
        width=w,
        height=h,
        megapixels_bucket=bucket,
        blank_ratio=blank_ratio,
        edge_density=edge_density,
        edge_density_std=edge_density_std,
        dominant_orientation_ratio=dom_ratio,
        parallel_warning=parallel_warning,
        inscription_box=inscription_box,
    )
    return metrics, edges, work


def detect_parallel_warning(edges: np.ndarray, min_len_ratio: float = 0.35) -> bool:
    h, w = edges.shape[:2]
    min_len = int(min_len_ratio * max(w, h))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=min_len, maxLineGap=10)
    if lines is None:
        return False
    cnt = 0
    for (x1, y1, x2, y2) in lines[:, 0, :]:
        dx = x2 - x1
        dy = y2 - y1
        ang = abs(np.degrees(np.arctan2(dy, dx)))
        ang = min(ang, 180 - ang)
        if ang < 6 or abs(ang - 90) < 6:
            cnt += 1
    return cnt >= 2


def suggest_inscription_box(edges: np.ndarray, orig_w: int, orig_h: int) -> Tuple[int, int, int, int]:
    h, w = edges.shape[:2]
    grid = 8
    cell_h = max(h // grid, 1)
    cell_w = max(w // grid, 1)
    best = (0, 0, cell_w, cell_h)
    best_score = 1e9
    for i in range(grid):
        for j in range(grid):
            cell = edges[i * cell_h : (i + 1) * cell_h, j * cell_w : (j + 1) * cell_w]
            score = float(np.mean(cell > 0))
            if score < best_score:
                best_score = score
                best = (j * cell_w, i * cell_h, cell_w, cell_h)

    sx = orig_w / max(w, 1)
    sy = orig_h / max(h, 1)
    x, y, bw, bh = best
    x0 = int(x * sx)
    y0 = int(y * sy)
    ww = int(bw * sx)
    hh = int(bh * sy)
    return x0, y0, ww, hh


def make_heatmap_png(edges: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(edges.astype(np.float32), (0, 0), sigmaX=7, sigmaY=7)
    norm = cv2.normalize(blur, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heat = cv2.applyColorMap(norm, cv2.COLORMAP_OCEAN)
    return heat


def make_basic_annotations(metrics: ImageMetrics) -> Dict[str, Any]:
    w = metrics.width
    h = metrics.height
    arrows = [[int(0.2 * w), int(0.8 * h), int(0.82 * w), int(0.22 * h)]]
    warnings: List[str] = []
    if metrics.parallel_warning:
        warnings.append("line_parallel")
    return {
        "arrows": arrows,
        "heatmap": None,
        "warnings": warnings,
        "good_crosses": [],
        "bad_crosses": [],
        "inscription_suggestion_box": [*metrics.inscription_box],
    }
