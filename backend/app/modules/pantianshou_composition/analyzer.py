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
    dominant_orientation_angle: float = -1.0  # degrees [0, 180), -1 = unknown


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


def to_feature_vector_1024(image_path_or_array) -> List[float]:
    """生成 1024 维图像特征向量（DashScope multimodal-embedding-v1）。

    优先使用 DashScope API，失败时降级到灰度像素展平（补零到 1024 维）。
    输出维度固定 1024，与 knowledge_images collection 兼容。

    Args:
        image_path_or_array: 图片文件路径（str）或 BGR numpy 数组。

    Returns:
        1024 维向量列表。
    """
    import tempfile
    import os

    image_path: str | None = None
    temp_path: str | None = None

    if isinstance(image_path_or_array, str):
        image_path = image_path_or_array
    elif isinstance(image_path_or_array, np.ndarray):
        # numpy 数组 → 临时文件（DashScope API 需要 base64 文件）
        img_bgr = image_path_or_array
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(rgb)
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        pil_img.save(temp_path)
        image_path = temp_path
    else:
        # 降级
        fallback = _pixel_fallback_vector(np.zeros((16, 32), dtype=np.uint8)) if isinstance(image_path_or_array, np.ndarray) else [0.0] * 512
        return fallback + [0.0] * (1024 - len(fallback))

    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        service = EmbeddingService()
        result = service.embed_image_sync(image_path)
        if result and result.embedding and len(result.embedding) == 1024:
            return result.embedding
        else:
            logger.warning("DashScope embedding 返回维度异常: %d，降级到零向量", len(result.embedding) if result else 0)
            return [0.0] * 1024
    except Exception as e:
        logger.error("DashScope multimodal embedding 失败: %s，降级到零向量", e)
        return [0.0] * 1024
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


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


def _adaptive_threshold_for_painting(img_bgr: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """二值化：区分墨迹（前景）与纸张/留白（背景）。
    
    核心思路：
    1. 采样四边像素检测纸张基色亮度
    2. 灰度 Otsu 得到初始二值化
    3. 对泛黄纸张：纸张基色偏低，Otsu 阈值也偏低，
       用 ink_threshold = paper_brightness * 0.55 做更严格的墨迹判定
    4. 高饱和度像素（颜料/印章）强制标记为前景
    5. 形态学开运算去除小噪点
    
    返回：黑白图，0=墨迹/前景，255=纸张/留白/背景
    """
    h, w = gray.shape
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # --- Step 1: 检测纸张基色亮度 ---
    edge_px = np.concatenate([img_bgr[0, :], img_bgr[-1, :], img_bgr[:, 0], img_bgr[:, -1]], axis=0)
    edge_gray = 0.299 * edge_px[:, 2] + 0.587 * edge_px[:, 1] + 0.114 * edge_px[:, 0]
    # 取边缘较亮的像素的中位数作为纸张基色
    bright_mask = edge_gray > np.percentile(edge_gray, 40)
    paper_brightness = float(np.median(edge_gray[bright_mask])) if bright_mask.sum() > 10 else 200.0
    
    # --- Step 2: 灰度 Otsu ---
    _, bw = cv2.threshold(gray_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # --- Step 3: 对泛黄纸张做修正 ---
    # 泛黄纸张的亮度通常在 130-200 之间（白纸 200+）
    if paper_brightness < 210:
        # 泛黄纸张：只有比纸张暗很多的才是真正的墨迹
        # 比如纸张亮度 167，墨迹阈值约 167*0.55 = 92
        ink_threshold = max(60, int(paper_brightness * 0.55))
        _, bw_ink = cv2.threshold(gray_blur, ink_threshold, 255, cv2.THRESH_BINARY)
        # bw_ink: 0=墨迹, 255=非墨迹
        # 合并策略：Otsu 说"墨迹"的保留，但必须是 bw_ink 也说"墨迹"的才保留
        # 即：取 bw 和 bw_ink 的前景（黑色=0）的交集
        ink_intersection = cv2.bitwise_or(bw, bw_ink)  # 任一说不是墨迹，就不是墨迹
        bw = ink_intersection
    
    # --- Step 4: 高饱和度低明度像素（颜料/印章）→ 强制前景 ---
    # 注意：泛黄宣纸饱和度高但明度也高，不能把纸张当颜料
    # 只有 S>45 AND V<160 才是真正的颜料/印章
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    s_ch = hsv[:, :, 1]
    v_ch = hsv[:, :, 2]
    pigment_mask = (s_ch > 45) & (v_ch < 160)
    bw[pigment_mask] = 0  # 设为前景（黑色）
    
    # --- Step 5: 形态学清理 ---
    kernel = np.ones((2, 2), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    # 再闭运算填补墨迹内部小孔
    kernel_close = np.ones((3, 3), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel_close, iterations=1)
    
    return bw


def compute_metrics(img_bgr: np.ndarray, bucket: str) -> Tuple[ImageMetrics, np.ndarray, np.ndarray]:
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    # 使用 HSV 自适应二值化替代简单 Otsu
    bw = _adaptive_threshold_for_painting(img_bgr, gray)
    total_pixels = int(bw.size)
    total_blank = int(np.count_nonzero(bw == 255))
    blank_ratio = float(total_blank / max(total_pixels, 1))

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
    dom_idx = int(np.argmax(hist)) if hist.sum() > 0 else -1
    dom_angle = float((dom_idx * (180.0 / bins) + 90.0 / bins) % 180.0) if dom_idx >= 0 else -1.0

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
        dominant_orientation_angle=dom_angle,
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
    """检测已有题跋区域。

    题跋特征：
    1. 位于画面边缘角落（左上/右上/左下/右下）
    2. 小尺度密集纹理（文字）
    3. 边缘密度高但纹理尺度小

    返回: (x, y, width, height) 或 (0, 0, 0, 0) 表示未检测到
    """
    h, w = edges.shape[:2]

    # 划分为 4 个角落区域进行检测
    grid = 4
    cell_h = max(h // grid, 1)
    cell_w = max(w // grid, 1)

    corners = [
        ('top-left', 0, 0),
        ('top-right', w - cell_w, 0),
        ('bottom-left', 0, h - cell_h),
        ('bottom-right', w - cell_w, h - cell_h),
    ]

    best_corner = None
    best_score = 0

    for name, cx, cy in corners:
        # 取角落 2x2 cells 区域
        region = edges[cy:cy + cell_h * 2, cx:cx + cell_w * 2]
        if region.size == 0:
            continue

        # 计算边缘密度
        edge_density = np.mean(region > 0)

        # 计算纹理密度（使用小尺度结构元素）
        kernel_small = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(region, kernel_small, iterations=1)
        eroded = cv2.erode(region, kernel_small, iterations=1)
        texture_score = np.mean(dilated > 0) - np.mean(eroded > 0)

        # 综合得分：边缘密度高 + 纹理细腻
        score = edge_density * 0.6 + abs(texture_score) * 0.4

        if score > best_score and edge_density > 0.05:
            best_score = score
            best_corner = (cx, cy, cell_w * 2, cell_h * 2)

    if best_corner is None:
        # 未检测到题跋，返回留白建议区域
        return _suggest_blank_area(edges, orig_w, orig_h)

    # 转换回原始尺寸
    sx = orig_w / max(w, 1)
    sy = orig_h / max(h, 1)
    x, y, bw, bh = best_corner
    return (int(x * sx), int(y * sy), int(bw * sx), int(bh * sy))


def _suggest_blank_area(edges: np.ndarray, orig_w: int, orig_h: int) -> Tuple[int, int, int, int]:
    """原始的留白区域建议（未检测到题跋时使用）。"""
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
    return (int(x * sx), int(y * sy), int(bw * sx), int(bh * sy))


def make_heatmap_png(edges: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(edges.astype(np.float32), (0, 0), sigmaX=7, sigmaY=7)
    norm = cv2.normalize(blur, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heat = cv2.applyColorMap(norm, cv2.COLORMAP_OCEAN)
    return heat


def _generate_direction_arrows(w: int, h: int, metrics: ImageMetrics, edges=None) -> Tuple[List[List[int]], List[str]]:
    """Generate arrows showing the composition flow (起承转合).

    核心规则（基于潘天寿教学图案例总结）:
    - 起: 绝不在画面中央；在画面边缘（甚至画面外），可以是任何角落/边缘
         常见位置: 左下、右下、右上（图7、8）、左上
         支持"主起+副起"多起点
    - 承: 从起自然延伸，可以有多个承，沿主体枝干分布
    - 转: 大体气势的转折，情节高潮（方向变化最大、密度最高），通常在画面中上部
    - 合/结: 题款位置附近，或与起对侧呼应的收束
    - 整体路径：S形、上升式、弧线，关键是顺着墨迹主体走向

    Returns: (arrows, labels)
        arrows: list of [sx, sy, ex, ey] — straight line arrows
        labels: list of label strings — placed at the START of each arrow
    """
    import math

    if edges is None:
        return _fallback_arrow(w, h, metrics)

    import numpy as np

    if edges.size == 0:
        return _fallback_arrow(w, h, metrics)

    # --- Step 1: Fine grid density analysis (10×10 for better resolution) ---
    grid_n = 10
    grid = np.zeros((grid_n, grid_n), dtype=np.float32)
    gh = edges.shape[0] // grid_n
    gw = edges.shape[1] // grid_n
    for gy in range(grid_n):
        for gx in range(grid_n):
            cell = edges[gy * gh:(gy + 1) * gh, gx * gw:(gx + 1) * gw]
            grid[gy, gx] = cell.sum()

    if grid.max() < 1:
        return _fallback_arrow(w, h, metrics)

    # --- Helper functions ---
    def _cell_center(gx, gy):
        return int((gx + 0.5) * w / grid_n), int((gy + 0.5) * h / grid_n)

    def _cell_angle(gx1, gy1, gx2, gy2):
        dx, dy = gx2 - gx1, gy2 - gy1
        if dx == 0 and dy == 0:
            return 0
        return math.degrees(math.atan2(dy, dx)) % 360

    def _angle_diff(a1, a2):
        d = abs(a1 - a2) % 360
        return min(d, 360 - d)

    def _clamp(val, lo=10, hi=None):
        if hi is None:
            hi = max(lo, val)
        return int(max(lo, min(hi, val)))

    def _dist(x1, y1, x2, y2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # --- Step 2: Border cell analysis (占边检测) ---
    edge_threshold = grid.max() * 0.08  # 稍微降低阈值，捕捉更多边缘
    border_cells = {
        'top': [(gx, 0, grid[0, gx]) for gx in range(grid_n) if grid[0, gx] > edge_threshold],
        'bottom': [(gx, grid_n - 1, grid[grid_n - 1, gx]) for gx in range(grid_n) if grid[grid_n - 1, gx] > edge_threshold],
        'left': [(0, gy, grid[gy, 0]) for gy in range(1, grid_n - 1) if grid[gy, 0] > edge_threshold],
        'right': [(grid_n - 1, gy, grid[gy, grid_n - 1]) for gy in range(1, grid_n - 1) if grid[gy, grid_n - 1] > edge_threshold],
    }

    all_border = []
    for side, cells in border_cells.items():
        for gx, gy, density in cells:
            px, py = _cell_center(gx, gy)
            all_border.append({
                'gx': gx, 'gy': gy, 'density': density, 'side': side,
                'px': px, 'py': py,
                'edge_score': 1.0,  # 边缘位置得分
            })

    # --- Step 3: Find 题 (inscription) position for 合 ---
    # 题跋区域需要特殊处理：合可以在这里，但起/承/转要避开
    inscr = metrics.inscription_box  # (x, y, bw, bh)
    inscr_cx, inscr_cy = w / 2, 0
    inscr_found = False
    inscr_grid = None  # 题跋在grid中的范围
    
    if inscr and inscr[2] > 0 and inscr[3] > 0:
        inscr_cx = inscr[0] + inscr[2] / 2
        inscr_cy = inscr[1] + inscr[3] / 2
        inscr_found = True
        # 计算题跋在grid中的范围
        inscr_gx1 = max(0, int(inscr[0] * grid_n / w))
        inscr_gx2 = min(grid_n - 1, int((inscr[0] + inscr[2]) * grid_n / w))
        inscr_gy1 = max(0, int(inscr[1] * grid_n / h))
        inscr_gy2 = min(grid_n - 1, int((inscr[1] + inscr[3]) * grid_n / h))
        inscr_grid = (inscr_gx1, inscr_gy1, inscr_gx2, inscr_gy2)
    
    def _is_in_inscription(gx, gy):
        """检查grid cell是否在题跋区域内"""
        if not inscr_grid:
            return False
        gx1, gy1, gx2, gy2 = inscr_grid
        return gx1 <= gx <= gx2 and gy1 <= gy <= gy2

    # --- Step 4: Find 起 (opening / starting point) ---
    # 规则更新: 起在画面边缘任何位置，排除题跋区域
    # 起 = 边缘密度最高的区域，排除中央区域和题跋
    
    center_margin = grid_n // 4  # 排除中央 40%
    cx_img, cy_img = w / 2, h / 2

    # 从所有边缘候选中找起
    def _is_center(gx, gy):
        return (center_margin <= gx <= grid_n - 1 - center_margin and
                center_margin <= gy <= grid_n - 1 - center_margin)

    # 边缘候选（非中央、非题跋）
    edge_candidates = [
        c for c in all_border 
        if not _is_center(c['gx'], c['gy']) and not _is_in_inscription(c['gx'], c['gy'])
    ]
    
    qi = None
    qi_secondary = None  # 副起

    if edge_candidates:
        # 按密度排序，选前两个作为起和副起
        edge_candidates.sort(key=lambda c: -c['density'])
        qi = edge_candidates[0]
        if len(edge_candidates) > 1 and edge_candidates[1]['density'] > edge_candidates[0]['density'] * 0.5:
            # 副起条件：密度至少为主起的50%，且与主起有一定距离
            d = _dist(qi['px'], qi['py'], edge_candidates[1]['px'], edge_candidates[1]['py'])
            if d > min(w, h) * 0.15:  # 距离足够远
                qi_secondary = edge_candidates[1]

    if not qi:
        # 最后手段：内部最密但非中央区域
        flat = np.argsort(grid.ravel())[::-1]
        for idx in flat[:12]:
            gy, gx = divmod(idx, grid_n)
            if not _is_center(gx, gy):
                qi = {
                    'gx': gx, 'gy': gy, 'density': grid[gy, gx],
                    'side': 'interior', 'px': _cell_center(gx, gy)[0], 'py': _cell_center(gx, gy)[1],
                }
                break
    
    if not qi:
        return _fallback_arrow(w, h, metrics)

    qi_px, qi_py = _cell_center(qi['gx'], qi['gy'])

    # --- Step 5: Find 合 (closing / resolution) ---
    # 规则更新: 合在题款附近，或者在起对侧的边缘位置
    # 不一定在画面上部，而是与起形成对角/对侧呼应
    
    he_candidates = []
    for side, cells in border_cells.items():
        for gx, gy, density in cells:
            if gx == qi['gx'] and gy == qi['gy']:
                continue
            px, py = _cell_center(gx, gy)
            
            # 与题款的距离（如果有题款）
            inscr_dist = _dist(px, py, inscr_cx, inscr_cy) if inscr_found else 9999
            inscr_bonus = max(0, 1 - inscr_dist / (min(w, h) * 0.4)) if inscr_found else 0
            
            # 与起的对角/对侧关系（关键指标）
            qi_vec_x, qi_vec_y = qi_px - cx_img, qi_py - cy_img
            he_vec_x, he_vec_y = px - cx_img, py - cy_img
            qi_norm = math.sqrt(qi_vec_x ** 2 + qi_vec_y ** 2) + 1e-9
            he_norm = math.sqrt(he_vec_x ** 2 + he_vec_y ** 2) + 1e-9
            dot = (qi_vec_x * he_vec_x + qi_vec_y * he_vec_y) / (qi_norm * he_norm + 1e-9)
            opposite_score = max(0, -dot)  # 对角方向得分
            
            # 合应该远离起（距离奖励）
            dist_to_qi = _dist(px, py, qi_px, qi_py)
            dist_bonus = min(dist_to_qi / (min(w, h) * 0.5), 1.0)
            
            score = inscr_bonus * 0.40 + opposite_score * 0.35 + dist_bonus * 0.15 + (density / (grid.max() + 1e-9)) * 0.10
            he_candidates.append({
                'gx': gx, 'gy': gy, 'density': density, 'side': side,
                'px': px, 'py': py, 'score': score,
            })

    # 检查题款附近的内部区域
    if inscr_found:
        for gy in range(grid_n):
            for gx in range(grid_n):
                if gx == qi['gx'] and gy == qi['gy']:
                    continue
                px, py = _cell_center(gx, gy)
                density = grid[gy, gx]
                if density < grid.max() * 0.05:
                    continue
                inscr_dist = _dist(px, py, inscr_cx, inscr_cy)
                inscr_bonus = max(0, 1 - inscr_dist / (min(w, h) * 0.25))
                if inscr_bonus < 0.4:
                    continue
                score = inscr_bonus * 0.60 + (density / (grid.max() + 1e-9)) * 0.40
                exists = any(c['gx'] == gx and c['gy'] == gy for c in he_candidates)
                if not exists:
                    he_candidates.append({
                        'gx': gx, 'gy': gy, 'density': density, 'side': 'inscription_area',
                        'px': px, 'py': py, 'score': score,
                    })

    if not he_candidates:
        # 极端情况：直接用起的对角位置
        opp_gx = min(grid_n - 1, max(0, grid_n - 1 - qi['gx']))
        opp_gy = min(grid_n - 1, max(0, grid_n - 1 - qi['gy']))
        he = {
            'gx': opp_gx, 'gy': opp_gy, 'density': grid[opp_gy, opp_gx],
            'side': 'opposite', 'px': _cell_center(opp_gx, opp_gy)[0],
            'py': _cell_center(opp_gx, opp_gy)[1],
        }
    else:
        he_candidates.sort(key=lambda c: -c['score'])
        he = he_candidates[0]

    # --- Step 6: Find 转 (climax / turning point) ---
    # 规则: 转是方向变化最大的位置，画面情节的高潮
    # 转 应该在起和合之间但偏离直线路径（S形的拐点）
    # 重要：转要避开题跋区域，应该在画面主体中
    
    zhuan_candidates = []
    qi_angle = _cell_angle(qi['gx'], qi['gy'], he['gx'], he['gy'])
    
    for gy in range(grid_n):
        for gx in range(grid_n):
            if gx == qi['gx'] and gy == qi['gy']:
                continue
            if gx == he['gx'] and gy == he['gy']:
                continue
            # 转要避开题跋区域（除非题跋就是画面主体的一部分）
            if _is_in_inscription(gx, gy):
                continue
            density = grid[gy, gx]
            if density < grid.max() * 0.10:
                continue

            px, py = _cell_center(gx, gy)

            # 垂直于起→合连线的距离（S形的拐点特征）
            line_len = _dist(qi_px, qi_py, he['px'], he['py']) + 1e-9
            cross = abs((he['px'] - qi_px) * (py - qi_py) - (he['py'] - qi_py) * (px - qi_px))
            perp_dist = cross / line_len

            # 沿路径的进度 (0=起, 1=合)
            param = max(0, min(1, ((px - qi_px) * (he['px'] - qi_px) + (py - qi_py) * (he['py'] - qi_py))
                                / (line_len * line_len)))

            # 转 偏好在 0.35~0.75 之间（中偏后）
            mid_bonus = 1.0 - abs(param - 0.55) * 2.5
            mid_bonus = max(0, mid_bonus)
            
            # S形偏移奖励
            deviation_bonus = min(perp_dist / (min(w, h) * 0.15), 1.0)

            score = (density / (grid.max() + 1e-9)) * 0.35 + mid_bonus * 0.35 + deviation_bonus * 0.30

            zhuan_candidates.append({
                'gx': gx, 'gy': gy, 'density': density,
                'px': px, 'py': py, 'score': score,
                'param': param,
            })

    zhuan = None
    if zhuan_candidates:
        zhuan_candidates.sort(key=lambda c: -c['score'])
        zhuan = zhuan_candidates[0]

    # --- Step 7: Find 承 (transition / continuation) ---
    # 规则更新: 承在起和转之间，可以有多个承
    # 承沿墨迹主体分布，朝画面中心推进
    # 重要：承要避开题跋区域
    
    cheng_list = []  # 支持多个承
    if zhuan:
        cheng_target_angle = _cell_angle(qi['gx'], qi['gy'], zhuan['gx'], zhuan['gy'])
        cheng_candidates = []
        for gy in range(grid_n):
            for gx in range(grid_n):
                if gx == qi['gx'] and gy == qi['gy']:
                    continue
                if gx == zhuan['gx'] and gy == zhuan['gy']:
                    continue
                if gx == he['gx'] and gy == he['gy']:
                    continue
                # 承要避开题跋区域
                if _is_in_inscription(gx, gy):
                    continue
                density = grid[gy, gx]
                if density < grid.max() * 0.08:
                    continue
                px, py = _cell_center(gx, gy)
                
                # 承 应该在起和转之间
                dist_qi = _dist(qi_px, qi_py, px, py)
                dist_zhuan = _dist(zhuan['px'], zhuan['py'], px, py)
                
                # 计算在起→转路径上的位置
                qi_zhuan_len = _dist(qi_px, qi_py, zhuan['px'], zhuan['py']) + 1e-9
                param_qi_zhuan = ((px - qi_px) * (zhuan['px'] - qi_px) + (py - qi_py) * (zhuan['py'] - qi_py)) / (qi_zhuan_len ** 2)
                
                # 承应该在 0.1~0.8 之间（不要离起太近，也不要离转太近）
                if param_qi_zhuan < 0.1 or param_qi_zhuan > 0.8:
                    continue
                
                cell_angle_from_qi = _cell_angle(qi['gx'], qi['gy'], gx, gy)
                angle_diff = _angle_diff(cell_angle_from_qi, cheng_target_angle)
                
                # 承 朝向画面中心推进
                to_center_dist = _dist(px, py, cx_img, cy_img)
                center_bonus = max(0, 1 - to_center_dist / (min(w, h) * 0.5))
                
                score = (density / (grid.max() + 1e-9)) * 0.35 + \
                        (1 - min(angle_diff / 60, 1.0)) * 0.30 + \
                        (1 - min(dist_qi / (min(w, h) * 0.6), 1.0)) * 0.15 + \
                        center_bonus * 0.20
                
                cheng_candidates.append({
                    'gx': gx, 'gy': gy, 'density': density,
                    'px': px, 'py': py, 'score': score,
                    'param': param_qi_zhuan,
                })

        if cheng_candidates:
            cheng_candidates.sort(key=lambda c: -c['score'])
            # 取前1-2个承（间距要足够远）
            for c in cheng_candidates[:3]:
                if c['score'] > cheng_candidates[0]['score'] * 0.5:  # 得分至少是最高的一半
                    too_close = False
                    for existing in cheng_list:
                        if _dist(c['px'], c['py'], existing['px'], existing['py']) < min(w, h) * 0.12:
                            too_close = True
                            break
                    if not too_close:
                        cheng_list.append(c)

    # --- Step 8: Build path and determine shape ---
    # 支持多起点(主起+副起) + 多承点
    
    nodes = [qi]
    labels_out = ["起"]
    
    min_gap = min(w, h) * 0.10  # 最小节点间距

    # 如果有副起，添加到路径
    if qi_secondary:
        nodes.append(qi_secondary)
        labels_out.append("起")  # 副起也标记为"起"

    # 添加承点（按路径顺序）
    if cheng_list:
        # 按离起点的距离排序
        cheng_sorted = sorted(cheng_list, key=lambda c: _dist(qi_px, qi_py, c['px'], c['py']))
        for c in cheng_sorted:
            if _dist(nodes[-1]['px'], nodes[-1]['py'], c['px'], c['py']) > min_gap:
                nodes.append(c)
                labels_out.append("承")

    # 添加转点
    if zhuan and _dist(nodes[-1]['px'], nodes[-1]['py'], zhuan['px'], zhuan['py']) > min_gap:
        nodes.append(zhuan)
        labels_out.append("转")

    # 添加合点
    if _dist(nodes[-1]['px'], nodes[-1]['py'], he['px'], he['py']) > min_gap:
        nodes.append(he)
        labels_out.append("合")

    if len(nodes) < 2:
        return _fallback_arrow(w, h, metrics)

    # 检测是否可以形成闭环（合的终点靠近主起）
    is_loop = False
    if len(nodes) >= 3:
        last = nodes[-1]
        loop_dist = _dist(last['px'], last['py'], qi_px, qi_py)
        max_loop = math.sqrt(w ** 2 + h ** 2) * 0.45
        if loop_dist < max_loop and loop_dist > min_gap:
            is_loop = True

    # --- Step 9: Generate arrows ---
    arrows = []
    margin = 10
    for i in range(len(nodes) - 1):
        sx = _clamp(nodes[i]['px'], margin, w - margin)
        sy = _clamp(nodes[i]['py'], margin, h - margin)
        ex = _clamp(nodes[i + 1]['px'], margin, w - margin)
        ey = _clamp(nodes[i + 1]['py'], margin, h - margin)
        arrows.append([sx, sy, ex, ey])

    if is_loop:
        last = nodes[-1]
        sx = _clamp(last['px'], margin, w - margin)
        sy = _clamp(last['py'], margin, h - margin)
        ex = _clamp(qi_px, margin, w - margin)
        ey = _clamp(qi_py, margin, h - margin)
        arrows.append([sx, sy, ex, ey])
        labels_out.append("回")

    return arrows, labels_out


def _fallback_arrow(w: int, h: int, metrics: ImageMetrics) -> Tuple[List[List[int]], List[str]]:
    """Fallback: single straight arrow from dominant orientation."""
    import math
    dom_angle = metrics.dominant_orientation_angle
    dom_strength = metrics.dominant_orientation_ratio
    if dom_angle < 0 or dom_strength < 0.15:
        return [], []
    cx, cy = w * 0.5, h * 0.5
    arrow_len = min(w, h) * 0.30
    rad = math.radians(dom_angle)
    dx = math.cos(rad)
    dy = math.sin(rad)
    sx = int(cx - dx * arrow_len * 0.5)
    sy = int(cy - dy * arrow_len * 0.5)
    ex = int(cx + dx * arrow_len * 0.5)
    ey = int(cy + dy * arrow_len * 0.5)
    margin = 10
    sx = max(margin, min(w - margin, sx))
    sy = max(margin, min(h - margin, sy))
    ex = max(margin, min(w - margin, ex))
    ey = max(margin, min(h - margin, ey))
    return [[sx, sy, ex, ey]], ["起"]


def make_basic_annotations(metrics: ImageMetrics, edges=None) -> Dict[str, Any]:
    w = metrics.width
    h = metrics.height
    arrows, arrow_labels = _generate_direction_arrows(w, h, metrics, edges)
    warnings: List[str] = []
    if metrics.parallel_warning:
        warnings.append("line_parallel")
    return {
        "arrows": arrows,
        "arrow_labels": arrow_labels,
        "heatmap": None,
        "warnings": warnings,
        "good_crosses": [],
        "bad_crosses": [],
        "inscription_suggestion_box": [*metrics.inscription_box],
    }
