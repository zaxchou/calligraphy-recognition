from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Request, Query
from fastapi.responses import JSONResponse
import json
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import logging
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw
import time
from starlette.concurrency import run_in_threadpool

import redis
from app.core.config import get_settings
from app.core.database import get_db
from app.core.path_utils import get_static_url, get_full_file_path, normalize_path
from app.models.tubi_analysis import TubiAnalysis
from app.services.auto_tags import compute_tags_cached
from app.services.inscription_content_analyzer import get_period_phase

settings = get_settings()
logger = logging.getLogger(__name__)

# 作者默认印章内容映射
AUTHOR_DEFAULT_SEAL = {
    "李鱓": "作者印：复堂，李鱓，李鱓印、鱓印、宗杨、懊道人",
    "刘海勇": "作者印：刘氏、海勇、紫苑小学堂、东欧刘氏、海勇之玺、长乐",
}


def _get_default_seal_content(artist: str) -> str:
    """根据作者返回默认印章内容，未知作者返回李鱓的默认值"""
    if not artist:
        return AUTHOR_DEFAULT_SEAL.get("李鱓")
    # 精确匹配优先
    if artist in AUTHOR_DEFAULT_SEAL:
        return AUTHOR_DEFAULT_SEAL[artist]
    # 模糊匹配（包含）
    for key in AUTHOR_DEFAULT_SEAL:
        if key in artist or artist in key:
            return AUTHOR_DEFAULT_SEAL[key]
    return AUTHOR_DEFAULT_SEAL.get("李鱓")


def _parse_calligraphy_filename(filename: str) -> dict:
    """
    解析书法/绘画文件名，格式：清_李鱓_兰竹图册七开之四_1750.jpg
    支持 _年代不详 后缀（year=None, period="年代不详"）
    返回 {title, artist, year, period}
    """
    import re
    # 去掉扩展名
    name = os.path.splitext(filename)[0]
    # 用下划线分割
    parts = name.split('_')
    if len(parts) < 3:
        return {"title": name, "artist": "李鱓", "year": None, "period": None}

    # 第二部分是作者（默认李鱓）
    artist = parts[1] if parts[1] else "李鱓"
    # 最后一部分如果是4位数字则是年份，如果是"年代不详"则 year=None
    year = None
    period = None
    title_parts = []
    for i, part in enumerate(parts):
        if re.match(r"^\d{4}$", part):
            year = int(part)
            # 根据年份判断分期（李鱓：早期1714-1722/中期1723-1745/晚期1746-1760）
            if artist in ("李鱓",):
                if year and year <= 1722:
                    period = "早期"
                elif year <= 1745:
                    period = "中期"
                else:
                    period = "晚期"
            break
        elif part == "年代不详":
            year = None
            period = "年代不详"
            break
        else:
            if i > 1:  # 跳过第一个（朝代）和第二个（作者）
                title_parts.append(part)
    title = "_".join(title_parts) if title_parts else name
    return {"title": title, "artist": artist, "year": year, "period": period}
UPLOAD_DIR = settings.UPLOAD_DIR
THUMBNAIL_DIR = settings.TUBI_THUMBNAIL_DIR
ANNOTATED_DIR = settings.TUBI_ANNOTATED_DIR
DEBUG_DIR = settings.TUBI_DEBUG_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)
os.makedirs(ANNOTATED_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

# --- API Key 认证 ---


def _require_admin_api_key(request: Request) -> None:
    """验证管理员 API Key，用于危险操作（删除/清空）"""
    expected = getattr(settings, "COMPOSITION_API_KEY", "")
    key = request.headers.get("X-API-Key")
    if expected and key != expected:
        raise HTTPException(status_code=403, detail="invalid_api_key")


from app.models.tubi_job import TubiJob

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _to_local_path(p: str) -> str:
    if not p:
        return ""
    p2 = p.replace("/", os.sep)
    if os.path.isabs(p2) or (len(p2) >= 2 and p2[1] == ":"):
        return os.path.normpath(p2)
    p2 = p2.lstrip("\\/")
    return os.path.normpath(os.path.join(PROJECT_ROOT, p2))


# ── 文件存在性缓存（避免重复 stat 调用） ──
_file_exists_cache = {}
_FILE_CACHE_TTL = 60  # 秒


def _cached_exists(path: str) -> bool:
    """带 TTL 的 os.path.exists 缓存，减少重复 stat 系统调用"""
    if not path:
        return False
    now = time.monotonic()
    cached = _file_exists_cache.get(path)
    if cached is not None and now - cached["t"] < _FILE_CACHE_TTL:
        return cached["v"]
    v = os.path.exists(path)
    _file_exists_cache[path] = {"v": v, "t": now}
    return v


def _cached_isfile(path: str) -> bool:
    """带 TTL 的 os.path.isfile 缓存"""
    if not path:
        return False
    now = time.monotonic()
    cached = _file_exists_cache.get(path)
    if cached is not None and now - cached["t"] < _FILE_CACHE_TTL:
        return cached["v"]
    v = os.path.isfile(path)
    _file_exists_cache[path] = {"v": v, "t": now}
    return v


# ── 全量作品列表缓存（服务端持久化，所有用户共享） ──
# 当有新作品上传/分析完成/删除时自动失效
# 项目根目录（同 PROJECT_ROOT），Docker 内为 /app，本地为 repo 根目录
_PROJECT_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_RESULTS_CACHE_FILE = os.path.join(_PROJECT_BASE, "data", "cache", "tubi_results_all.json")

def _get_results_cache():
    """读取全量作品列表缓存，不存在返回 None"""
    try:
        if os.path.exists(_RESULTS_CACHE_FILE):
            with open(_RESULTS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def _set_results_cache(data):
    """写入全量作品列表缓存"""
    try:
        os.makedirs(os.path.dirname(_RESULTS_CACHE_FILE), exist_ok=True)
        with open(_RESULTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("写入作品列表缓存失败: %s", e)

def _clear_results_cache():
    """清除全量作品列表缓存 — 有新作品上传/分析完成/删除时调用"""
    try:
        if os.path.exists(_RESULTS_CACHE_FILE):
            os.remove(_RESULTS_CACHE_FILE)
    except Exception as e:
        logger.warning("清除作品列表缓存失败: %s", e)


from app.services.siliconflow_service import (
    analyze_image_regions,
    calculate_area_stats
)
from app.services.inscription_position_analyzer import analyze_inscription_position
from app.services.keyword_extractor import extract_wordcloud_keywords, load_wordcloud_config, get_artist_aliases

router = APIRouter(prefix="/tubi", tags=["题跋分析"])
_QUEUE_KEY_PENDING = "tubi:queue:pending"
_QUEUE_KEY_PROCESSING = "tubi:queue:processing"


class WordCloudKeywordItem(BaseModel):
    word: str
    count: int
    score: float


class WordCloudResponse(BaseModel):
    success: bool
    data: List[WordCloudKeywordItem]
    total_keywords: int
    total_count: int


class WordCloudArtistItem(BaseModel):
    name: str
    aliases: List[str]


class WordCloudArtistsResponse(BaseModel):
    success: bool
    data: List[WordCloudArtistItem]


@router.get("/wordcloud/artists", response_model=WordCloudArtistsResponse)
def get_wordcloud_artists():
    cfg = load_wordcloud_config()
    artists = []
    for a in cfg.get("artists", []) or []:
        name = a.get("name")
        if isinstance(name, str) and name:
            artists.append({"name": name, "aliases": get_artist_aliases(name)})
    return {"success": True, "data": artists}


@router.get("/wordcloud", response_model=WordCloudResponse)
def get_wordcloud_keywords(
    artist: Optional[str] = None,
    top_k: int = 40,
    db: Session = Depends(get_db),
):
    q = db.query(TubiAnalysis)
    if artist and artist != "all":
        q = q.filter(TubiAnalysis.artist.in_(get_artist_aliases(artist)))
    items = q.order_by(TubiAnalysis.created_at.desc()).limit(2000).all()

    docs = [
        {
            "title": i.title,
            "notes": i.notes,
            "analysis_note": i.analysis_note,
            "inscription_content": i.inscription_content,
        }
        for i in items
    ]
    result = extract_wordcloud_keywords(docs, artist=artist, top_k=top_k)
    return {
        "success": True,
        "data": result["keywords"],
        "total_keywords": result["total_keywords"],
        "total_count": result["total_count"],
    }


def _get_redis():
    conn = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
        retry_on_timeout=False
    )
    conn.ping()
    return conn


def create_thumbnail(image_path: str, thumbnail_path: str, max_size: int = 300):
    """
    生成缩略图
    max_size: 缩略图最大宽高（默认300px）
    超宽图片（宽高比 > 2）：先缩放高度到 max_size，再从中间裁切 max_size × max_size
    超高图片（宽高比 < 0.5，如条屏）：先缩放宽度到 max_size，再从中间裁切 max_size × max_size
    普通图片：整体缩放
    """
    try:
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        from PIL import Image, ImageOps

        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            w, h = img.size
            ratio = w / h if h > 0 else 1
            
            if ratio > 2:
                # 超宽图片：先缩放高度到 max_size，再从中间裁切 max_size × max_size
                scale = max_size / h
                scaled_w = int(w * scale)
                img_scaled = img.resize((scaled_w, max_size), Image.Resampling.LANCZOS)
                left = max(0, (scaled_w - max_size) // 2)
                top = 0
                right = left + max_size
                bottom = max_size
                img_cropped = img_scaled.crop((left, top, right, bottom))
                img_scaled.close()
                img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=True)
            elif ratio < 0.5:
                # 超高图片（条屏类）：先缩放宽度到 max_size，再从中间裁切 max_size × max_size
                scale = max_size / w
                scaled_h = int(h * scale)
                img_scaled = img.resize((max_size, scaled_h), Image.Resampling.LANCZOS)
                left = 0
                top = max(0, (scaled_h - max_size) // 2)
                right = max_size
                bottom = top + max_size
                img_cropped = img_scaled.crop((left, top, right, bottom))
                img_scaled.close()
                img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=True)
            else:
                # 普通图片：整体缩放
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                img.save(thumbnail_path, "JPEG", quality=85, optimize=True)

        if os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0:
            return thumbnail_path
        return None
    except Exception as e:
        logger.error("生成缩略图失败: %s", e)
        try:
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception:
            pass
        return None


class PointData(BaseModel):
    x: float
    y: float


class RegionData(BaseModel):
    type: str = "inscription"  # 默认为 inscription
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    points: Optional[List[PointData]] = None  # 多边形顶点（优先使用）


class AnalysisRequest(BaseModel):
    image_id: str
    regions: List[RegionData]
    image_width: Optional[int] = None
    image_height: Optional[int] = None


class YearDataRequest(BaseModel):
    image_id: str
    year: Optional[int] = None
    period: Optional[str] = None
    notes: Optional[str] = None


class ImageInfoRequest(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    year: Optional[int] = None
    age: Optional[int] = None
    period: Optional[str] = None
    notes: Optional[str] = None
    analysis_note: Optional[str] = None
    inscription_content: Optional[str] = None
    seal_content: Optional[str] = None
    inscription_percent: Optional[float] = None
    painting_percent: Optional[float] = None
    blank_percent: Optional[float] = None


def draw_annotated_image(original_path: str, regions: dict, output_path: str):
    """
    绘制区域标注图片 — 只标注题跋区域（红色），不标注绘画和留白
    """
    try:
        from PIL import Image, ImageDraw
        import os
        
        # 检查文件是否存在
        if not os.path.exists(original_path):
            logger.warning("原始文件不存在: %s", original_path)
            return None
        
        # 打开原图并调整大小以减少内存使用
        max_size = 1024  # 限制最大边长为1024像素
        with Image.open(original_path) as img:
            # 调整图片大小
            width, height = img.size
            if width > max_size or height > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为RGBA模式以支持透明叠加
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 创建透明叠加层
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            # 只画题跋区域 - 红色
            insc_fill = (220, 50, 50, 80)
            insc_border = (220, 50, 50, 220)
            
            max_regions = 100
            
            for region in regions.get("inscription_regions", [])[:max_regions]:
                try:
                    if "points" in region and isinstance(region["points"], list):
                        points = region["points"]
                        if len(points) >= 3:
                            scale_x = new_width / width if 'new_width' in locals() else 1
                            scale_y = new_height / height if 'new_height' in locals() else 1
                            poly_points = [(int(p["x"] * scale_x), int(p["y"] * scale_y)) for p in points]
                            draw.polygon(poly_points, fill=insc_fill)
                            draw.polygon(poly_points, outline=insc_border, width=2)
                    elif "x1" in region:
                        scale_x = new_width / width if 'new_width' in locals() else 1
                        scale_y = new_height / height if 'new_height' in locals() else 1
                        x1, y1 = int(region["x1"] * scale_x), int(region["y1"] * scale_y)
                        x2, y2 = int(region["x2"] * scale_x), int(region["y2"] * scale_y)
                        draw.rectangle([x1, y1, x2, y2], fill=insc_fill)
                        draw.rectangle([x1, y1, x2, y2], outline=insc_border, width=2)
                except Exception as e:
                    logger.error("绘制区域时出错: %s", e)
            
            # 合并图层
            result = Image.alpha_composite(img, overlay)
            
            # 转换为RGB保存
            if result.mode == 'RGBA':
                result = result.convert('RGB')
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            result.save(output_path, 'JPEG', quality=75, optimize=True)
            return output_path
    except Exception as e:
        logger.error("生成标注图片失败: %s", e)
        import traceback
        traceback.print_exc()
        return None


def draw_all_regions_image(original_path: str, regions: dict, output_path: str, original_width: int = None, original_height: int = None):
    """
    绘制三色区域标注图 — 题跋（红色）、绘画（蓝色）、留白（灰色）
    使用 OpenCV 实现，支持半透明叠加
    
    Args:
        original_width: 原始图片宽度（用于坐标缩放）
        original_height: 原始图片高度（用于坐标缩放）
    """
    try:
        import cv2
        import numpy as np
        
        # 检查文件是否存在
        if not os.path.exists(original_path):
            logger.warning("原始文件不存在: %s", original_path)
            return None
        
        # 读取原图
        img = cv2.imread(original_path)
        if img is None:
            logger.warning("无法读取图片: %s", original_path)
            return None
        
        height, width = img.shape[:2]
        original_width = original_width or width
        original_height = original_height or height
        
        # 调整大小以减少内存使用
        max_size = 1024
        scale_x = 1.0
        scale_y = 1.0
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            img = cv2.resize(img, (new_width, new_height))
            scale_x = new_width / original_width
            scale_y = new_height / original_height
            height, width = img.shape[:2]
        
        # 创建三个 mask
        inscription_mask = np.zeros((height, width), dtype=np.uint8)
        painting_mask = np.zeros((height, width), dtype=np.uint8)
        blank_mask = np.zeros((height, width), dtype=np.uint8)
        
        # 填充题跋区域
        for region in regions.get("inscription_regions", []):
            try:
                if "points" in region and isinstance(region["points"], list):
                    points = region["points"]
                    if len(points) >= 3:
                        pts = np.array([[int(p["x"] * scale_x), int(p["y"] * scale_y)] for p in points], dtype=np.int32)
                        cv2.fillPoly(inscription_mask, [pts], 255)
                elif "x1" in region:
                    x1 = int(region["x1"] * scale_x)
                    y1 = int(region["y1"] * scale_y)
                    x2 = int(region["x2"] * scale_x)
                    y2 = int(region["y2"] * scale_y)
                    cv2.rectangle(inscription_mask, (x1, y1), (x2, y2), 255, -1)
            except Exception as e:
                logger.error("填充题跋区域时出错: %s", e)
        
        # 填充绘画区域
        for region in regions.get("painting_regions", []):
            try:
                if "points" in region and isinstance(region["points"], list):
                    points = region["points"]
                    if len(points) >= 3:
                        pts = np.array([[int(p["x"] * scale_x), int(p["y"] * scale_y)] for p in points], dtype=np.int32)
                        cv2.fillPoly(painting_mask, [pts], 255)
                elif "x1" in region:
                    x1 = int(region["x1"] * scale_x)
                    y1 = int(region["y1"] * scale_y)
                    x2 = int(region["x2"] * scale_x)
                    y2 = int(region["y2"] * scale_y)
                    cv2.rectangle(painting_mask, (x1, y1), (x2, y2), 255, -1)
            except Exception as e:
                logger.error("填充绘画区域时出错: %s", e)
        
        # 留白区域 = 总面积 - 题跋 - 绘画
        # 先计算未被题跋和绘画覆盖的区域
        covered_mask = cv2.bitwise_or(inscription_mask, painting_mask)
        blank_mask = cv2.bitwise_not(covered_mask)
        
        # 创建颜色叠加层
        # 题跋 - 红色 (BGR: 60, 60, 220)，透明度 50%
        red_overlay = np.zeros_like(img)
        red_overlay[:, :] = [60, 60, 220]
        
        # 绘画 - 蓝色 (BGR: 220, 100, 50)，透明度 50%
        blue_overlay = np.zeros_like(img)
        blue_overlay[:, :] = [220, 100, 50]
        
        # 留白 - 灰色 (BGR: 180, 180, 180)，透明度 30%
        gray_overlay = np.zeros_like(img)
        gray_overlay[:, :] = [180, 180, 180]
        
        # 应用 mask 叠加颜色
        # 先应用留白（灰色）
        gray_blend = cv2.addWeighted(img, 0.70, gray_overlay, 0.30, 0)
        cv2.copyTo(gray_blend, blank_mask, img)
        
        # 再应用绘画（蓝色）
        blue_blend = cv2.addWeighted(img, 0.50, blue_overlay, 0.50, 0)
        cv2.copyTo(blue_blend, painting_mask, img)
        
        # 最后应用题跋（红色），优先级最高
        red_blend = cv2.addWeighted(img, 0.50, red_overlay, 0.50, 0)
        cv2.copyTo(red_blend, inscription_mask, img)
        
        # 保存结果
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        
        return output_path
    except Exception as e:
        logger.error("生成三色标注图失败: %s", e)
        import traceback
        traceback.print_exc()
        return None


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    artist: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    period: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        logger.info("开始上传文件: %s", file.filename)
        logger.info("文件类型: %s", file.content_type)
        
        if file.content_type not in ["image/jpeg", "image/png", "image/bmp"]:
            raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP 格式")

        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        filename = f"{file_id}{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        thumbnail_filename = f"{file_id}_thumb.jpg"
        thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)

        MAX_UPLOAD_SIZE = 50 * 1024 * 1024

        def _save_streaming() -> int:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            size = 0
            with open(filepath, "wb") as f:
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_SIZE:
                        raise ValueError("too_large")
                    f.write(chunk)
            return size

        t0 = time.perf_counter()
        try:
            await run_in_threadpool(_save_streaming)
        except ValueError:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass
            raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
        finally:
            try:
                await file.close()
            except Exception:
                pass
        logger.info("写入完成，用时: %.3fs", time.perf_counter() - t0)

        t1 = time.perf_counter()
        try:
            def _size_and_thumb():
                from PIL import ImageOps

                with Image.open(filepath) as img:
                    img = ImageOps.exif_transpose(img)
                    width, height = img.size
                    if thumbnail_path:
                        thumb = img
                        if thumb.mode != "RGB":
                            thumb = thumb.convert("RGB")
                        ratio = width / height if height > 0 else 1
                        max_size = 300
                        if ratio > 2:
                            # 超宽图片：先缩放高度到 300，再从中间裁切 300x300
                            scale = max_size / height
                            scaled_w = int(width * scale)
                            img_scaled = thumb.resize((scaled_w, max_size), Image.Resampling.LANCZOS)
                            left = max(0, (scaled_w - max_size) // 2)
                            top = 0
                            right = left + max_size
                            bottom = max_size
                            img_cropped = img_scaled.crop((left, top, right, bottom))
                            img_scaled.close()
                            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                            img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                            ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                        elif ratio < 0.5:
                            # 超高图片（条屏类）：先缩放宽度到 300，再从中间裁切 300x300
                            scale = max_size / width
                            scaled_h = int(height * scale)
                            img_scaled = thumb.resize((max_size, scaled_h), Image.Resampling.LANCZOS)
                            left = 0
                            top = max(0, (scaled_h - max_size) // 2)
                            right = max_size
                            bottom = top + max_size
                            img_cropped = img_scaled.crop((left, top, right, bottom))
                            img_scaled.close()
                            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                            img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                            ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                        else:
                            # 普通图片：整体缩放
                            thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                            os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                            thumb.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                            ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                    else:
                        ok = False
                return width, height, ok

            width, height, thumb_ok = await run_in_threadpool(_size_and_thumb)
            logger.info("图像尺寸: %dx%d", width, height)
        except Exception as e:
            logger.error("读取图像尺寸失败: %s", e)
            width, height = 0, 0
            thumb_ok = False

        # 生成缩略图
        logger.info("生成缩略图...")
        if not thumb_ok:
            thumbnail_path = None
            thumbnail_filename = None
        logger.info("图像处理完成，用时: %.3fs", time.perf_counter() - t1)

        # 如果前端没传 title 或 year，尝试从文件名解析
        # 注意：title 和 year 都要解析，因为两者都依赖文件名分割逻辑
        if not title or not year:
            parsed = _parse_calligraphy_filename(file.filename)
            # 只有当前端确实没传（None/空）时才用解析值，不要用文件名覆盖用户编辑过的值
            title = title if title else parsed["title"]
            artist = artist if artist else parsed["artist"]
            year = year if year else parsed["year"]
            period = period if period else parsed["period"]

        # 保存到数据库
        logger.info("保存到数据库...")
        # 自动计算分期（period_phase）
        period_phase = get_period_phase(year, artist)
        
        db_analysis = TubiAnalysis(
            image_id=file_id,
            filename=file.filename,
            filepath=normalize_path(filepath),
            thumbnail_path=normalize_path(thumbnail_path) if thumbnail_path else None,
            title=title,
            artist=artist,
            year=year,
            period=period,
            period_phase=period_phase,
            notes=notes,
            image_width=width,
            image_height=height,
            seal_content=_get_default_seal_content(artist),
            status="uploaded"
        )
        db.add(db_analysis)
        db.commit()
        db.refresh(db_analysis)

        # 清除作品列表缓存（有新作品即失效）
        _clear_results_cache()

        # 自动追加到图像搜索索引
        try:
            from app.services.image_search import get_search_engine
            engine = get_search_engine()
            tp = normalize_path(thumbnail_path) if thumbnail_path else None
            if tp and engine.total_indexed > 0:
                engine.add_to_index(db_analysis.id, tp)
                logger.info("已追加到图像搜索索引: id=%d", db_analysis.id)
        except Exception as e:
            logger.warning("追加索引失败(不影响上传): %s", e)

        logger.info("上传成功: %s", file_id)
        return {
            "success": True,
            "data": {
                "id": file_id,
                "filename": file.filename,
                "title": title,
                "artist": artist,
                "year": year,
                "period": period,
                "url": get_static_url(f"uploads/{filename}"),
                "thumbnail_url": get_static_url(f"thumbnails/{thumbnail_filename}") if thumbnail_filename else None,
                "width": width,
                "height": height
            }
        }
    except Exception as e:
        logger.error("上传失败: %s", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/upload-multiple")
async def upload_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    uploaded = []
    failed = []
    total_files = len(files)
    
    for i, file in enumerate(files):
        try:
            logger.info("处理文件 %d/%d: %s", i+1, total_files, file.filename)
            
            if file.content_type not in ["image/jpeg", "image/png", "image/bmp"]:
                failed.append({
                    "filename": file.filename,
                    "error": "只支持 JPG、PNG、BMP 格式"
                })
                continue

            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            filename = f"{file_id}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            thumbnail_filename = f"{file_id}_thumb.jpg"
            thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)

            MAX_UPLOAD_SIZE = 50 * 1024 * 1024

            def _save_streaming_multi() -> int:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                size = 0
                with open(filepath, "wb") as f:
                    while True:
                        chunk = file.file.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_UPLOAD_SIZE:
                            raise ValueError("too_large")
                        f.write(chunk)
                return size

            try:
                await run_in_threadpool(_save_streaming_multi)
            except ValueError:
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                except Exception:
                    pass
                failed.append({"filename": file.filename, "error": "文件大小超过50MB限制"})
                continue
            finally:
                try:
                    await file.close()
                except Exception:
                    pass

            try:
                def _size_and_thumb():
                    from PIL import ImageOps

                    with Image.open(filepath) as img:
                        img = ImageOps.exif_transpose(img)
                        width, height = img.size
                        if thumbnail_path:
                            thumb = img
                            if thumb.mode != "RGB":
                                thumb = thumb.convert("RGB")
                            ratio = width / height if height > 0 else 1
                            max_size = 300
                            if ratio > 2:
                                # 超宽图片：先缩放高度到 300，再从中间裁切 300x300
                                scale = max_size / height
                                scaled_w = int(width * scale)
                                img_scaled = thumb.resize((scaled_w, max_size), Image.Resampling.LANCZOS)
                                left = max(0, (scaled_w - max_size) // 2)
                                top = 0
                                right = left + max_size
                                bottom = max_size
                                img_cropped = img_scaled.crop((left, top, right, bottom))
                                img_scaled.close()
                                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                                img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                                ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                            elif ratio < 0.5:
                                # 超高图片（条屏类）：先缩放宽度到 300，再从中间裁切 300x300
                                scale = max_size / width
                                scaled_h = int(height * scale)
                                img_scaled = thumb.resize((max_size, scaled_h), Image.Resampling.LANCZOS)
                                left = 0
                                top = max(0, (scaled_h - max_size) // 2)
                                right = max_size
                                bottom = top + max_size
                                img_cropped = img_scaled.crop((left, top, right, bottom))
                                img_scaled.close()
                                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                                img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                                ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                            else:
                                # 普通图片：整体缩放
                                thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                                thumb.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                                ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                        else:
                            ok = False
                    return width, height, ok

                width, height, thumb_ok = await run_in_threadpool(_size_and_thumb)
            except Exception as e:
                logger.error("读取图像尺寸失败: %s", e)
                width, height = 0, 0
                thumb_ok = False

            # 生成缩略图
            try:
                if not thumb_ok:
                    thumbnail_path = None
                    thumbnail_filename = None
            except Exception as e:
                logger.error("生成缩略图失败: %s", e)
                thumbnail_path = None
                thumbnail_filename = None

            # 保存到数据库 - 使用标准化路径
            # 解析文件名提取 title/artist/year/period
            parsed = _parse_calligraphy_filename(file.filename)
            try:
                db_analysis = TubiAnalysis(
                    image_id=file_id,
                    filename=file.filename,
                    filepath=normalize_path(filepath),
                    thumbnail_path=normalize_path(thumbnail_path) if thumbnail_path else None,
                    image_width=width,
                    image_height=height,
                    title=parsed["title"],
                    artist=parsed["artist"],
                    year=parsed["year"],
                    period=parsed["period"],
                    seal_content=_get_default_seal_content(parsed["artist"]),
                    status="uploaded"
                )
                db.add(db_analysis)
                db.commit()
                db.refresh(db_analysis)

                uploaded.append({
                    "id": file_id,
                    "filename": file.filename,
                    "url": get_static_url(f"uploads/{filename}"),
                    "thumbnail_url": get_static_url(f"thumbnails/{thumbnail_filename}") if thumbnail_filename else None,
                    "width": width,
                    "height": height
                })
            except Exception as e:
                logger.error("保存到数据库失败: %s", e)
                failed.append({
                    "filename": file.filename,
                    "error": f"保存到数据库失败: {str(e)}"
                })
                # 尝试删除已创建的文件
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    if os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                except:
                    pass
        except Exception as e:
            logger.error("处理文件 %s 时出错: %s", file.filename, e)
            failed.append({
                "filename": file.filename,
                "error": f"处理失败: {str(e)}"
            })

    return {
        "success": len(failed) == 0,
        "data": uploaded,
        "failed": failed,
        "total": total_files,
        "uploaded_count": len(uploaded),
        "failed_count": len(failed)
    }


@router.post("/auto-analyze/{image_id}")
async def auto_analyze(image_id: str, db: Session = Depends(get_db)):
    """
    使用 AI 自动分析图像中的题跋、绘画、留白区域
    Redis 不可用时自动降级到 DB 队列（tubi_worker 的 DB 轮询模式会处理）
    """
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    if db_analysis.status == "analyzing":
        return JSONResponse(status_code=202, content={"success": True, "data": {"id": image_id, "status": "analyzing", "via": "already_processing"}})

    db_analysis.status = "queued"
    db.commit()

    job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
    if job:
        job.status = "queued"
        job.last_error = None
        job.error_code = None
    else:
        job = TubiJob(image_id=image_id, status="queued")
        db.add(job)
    db.commit()

    # 尝试 Redis 入队；失败则依赖 DB 轮询模式（tubi_worker 的 else 分支）
    via = "db"
    try:
        conn = _get_redis()
        conn.lpush(_QUEUE_KEY_PENDING, image_id)
        via = "redis"
    except Exception as redis_err:
        logger.warning("Redis 不可用，已降级到 DB 队列: %s", redis_err)
        try:
            db_analysis.analysis_note = "Redis不可用，已降级到DB队列模式"
            db.commit()
        except Exception:
            pass

    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "data": {
                "id": image_id,
                "status": "queued",
                "via": via,
                "enqueued": True,  # 总是成功入队（Redis 或 DB）
            }
        }
    )


@router.post("/analyze")
async def analyze_regions(request: AnalysisRequest, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == request.image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    # 使用 fillpoly 像素级精确计算，自动处理重叠和优先级
    img_w = request.image_width or 1
    img_h = request.image_height or 1
    total_area = img_w * img_h

    # 将 RegionData 转为 area_calculator 格式
    regions_dict = {"inscription_regions": [], "painting_regions": [], "blank_regions": []}
    type_map = {"inscription": "inscription_regions", "painting": "painting_regions", "blank": "blank_regions"}
    for region in request.regions:
        key = type_map.get(region.type)
        if key is not None:
            regions_dict[key].append({"x1": region.x1, "y1": region.y1, "x2": region.x2, "y2": region.y2})

    from ..services.area_calculator import calculate_area_stats_fillpoly
    area_stats = calculate_area_stats_fillpoly(regions_dict, img_w, img_h)
    inscription_percent = area_stats["inscription_percent"]
    painting_percent = area_stats["painting_percent"]
    blank_percent = area_stats["blank_percent"]

    # 更新数据库
    db_analysis.inscription_percent = round(inscription_percent, 1)
    db_analysis.painting_percent = round(painting_percent, 1)
    db_analysis.blank_percent = round(blank_percent, 1)
    db.commit()

    return {
        "success": True,
        "data": {
            "inscription_percent": round(inscription_percent, 1),
            "painting_percent": round(painting_percent, 1),
            "blank_percent": round(blank_percent, 1),
            "total_area": total_area
        }
    }


@router.get("/result/{image_id}")
async def get_result(image_id: str, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    # 构建图片URL - 使用跨平台路径处理
    if db_analysis.filepath:
        actual_filename = os.path.basename(db_analysis.filepath.replace('/', os.sep))
        image_url = get_static_url(f"uploads/{actual_filename}")
    elif db_analysis.filename:
        image_url = get_static_url(f"uploads/{db_analysis.filename}")
    else:
        image_url = None

    # 构建缩略图URL
    thumbnail_url = None
    if db_analysis.thumbnail_path:
        thumbnail_path_local = _to_local_path(db_analysis.thumbnail_path)
        if _cached_exists(thumbnail_path_local):
            thumbnail_filename = os.path.basename(db_analysis.thumbnail_path.replace('/', os.sep))
            thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
    elif image_url:
        thumbnail_url = image_url

    # 解析 position_analysis JSON
    position_analysis_data = None
    if db_analysis.position_analysis:
        try:
            position_analysis_data = json.loads(db_analysis.position_analysis) if isinstance(db_analysis.position_analysis, str) else db_analysis.position_analysis
        except Exception:
            position_analysis_data = None

    return {
        "success": True,
        "data": {
            "id": db_analysis.image_id,
            "db_id": db_analysis.id,
            "image_id": db_analysis.image_id,
            "filename": db_analysis.filename,
            "title": db_analysis.title,
            "artist": db_analysis.artist,
            "year": db_analysis.year,
            "period": db_analysis.period,
            "notes": db_analysis.notes,
            "filepath": db_analysis.filepath,
            "url": image_url,
            "thumbnail_url": thumbnail_url,
            "image_width": db_analysis.image_width,
            "image_height": db_analysis.image_height,
            "width": db_analysis.image_width,
            "height": db_analysis.image_height,
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent,
            "regions": db_analysis.regions,
            "position_analysis": position_analysis_data,
            "analysis_note": db_analysis.analysis_note,
            "inscription_content": db_analysis.inscription_content,
            "inscription_modern": db_analysis.inscription_modern,
            "seal_content": db_analysis.seal_content,
            "content_analysis": json.loads(db_analysis.content_analysis) if db_analysis.content_analysis else None,
            "status": db_analysis.status,
            "error_code": db_analysis.error_code,
            "created_at": db_analysis.created_at.isoformat() if db_analysis.created_at else None,
            "annotated_image_url": get_static_url(f"annotated/annotated_{image_id}.jpg") if db_analysis.annotated_image_path else None,
            "is_manual_annotated": bool(db_analysis.is_manual_annotated) if db_analysis.is_manual_annotated is not None else False,
            "artwork_width_cm": db_analysis.artwork_width_cm,
            "artwork_height_cm": db_analysis.artwork_height_cm,
            "album_name": db_analysis.album_name,
            "album_index": db_analysis.album_index,
            "tags": db_analysis.tags,
            "material_tags": db_analysis.material_tags,
            "period_phase": db_analysis.period_phase,
            "computed_tags": compute_tags_cached({
                "title": db_analysis.title,
                "period_phase": db_analysis.period_phase,
                "artwork_height_cm": db_analysis.artwork_height_cm,
                "artwork_width_cm": db_analysis.artwork_width_cm,
                "content_analysis": db_analysis.content_analysis,
                "material_tags": db_analysis.material_tags,
            })
        }
    }


@router.post("/batch-auto-analyze")
async def batch_auto_analyze(request: dict, db: Session = Depends(get_db)):
    """
    批量入队分析 — 两阶段上传模式第二步
    接收 image_id 列表，逐个入队（Redis 或 DB fallback）

    mode=manual 时：只将 status 改为 uploaded，不入队，用于"仅录入"模式
    """
    image_ids = request.get("image_ids", [])
    mode = request.get("mode", "analyze")  # "analyze" | "manual"

    if not image_ids:
        raise HTTPException(status_code=400, detail="image_ids 不能为空")

    # 仅录入模式：只更新 status，不入队
    if mode == "manual":
        results = []
        for image_id in image_ids:
            db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
            if not db_analysis:
                results.append({"id": image_id, "status": "not_found"})
                continue
            db_analysis.status = "uploaded"
            db.commit()
            results.append({"id": image_id, "status": "uploaded", "mode": "manual"})
        return {"success": True, "data": results, "mode": "manual"}

    # AI 分析模式：正常入队
    results = []
    for image_id in image_ids:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
        if not db_analysis:
            results.append({"id": image_id, "status": "not_found", "via": None})
            continue
        if db_analysis.status in ("analyzing", "queued"):
            results.append({"id": image_id, "status": db_analysis.status, "via": "already_queued"})
            continue

        db_analysis.status = "queued"
        db.commit()

        job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
        if job:
            job.status = "queued"
            job.mode = mode
            job.last_error = None
            job.error_code = None
        else:
            job = TubiJob(image_id=image_id, status="queued", mode=mode)
            db.add(job)
        db.commit()

        via = "db"
        try:
            conn = _get_redis()
            conn.lpush(_QUEUE_KEY_PENDING, image_id)
            via = "redis"
        except Exception:
            logger.warning("Redis 不可用，批量入队降级到 DB: %s", image_id)

        results.append({"id": image_id, "status": "queued", "via": via})

    return {"success": True, "data": results}


class BatchStatusRequest(BaseModel):
    image_ids: List[str]


@router.post("/batch-status")
async def batch_get_status(request: BatchStatusRequest, db: Session = Depends(get_db)):
    """
    批量查询分析状态 — 前端轮询用
    返回每个 image_id 的 status + error_code + analysis_note
    """
    if not request.image_ids:
        return {"success": True, "data": []}

    results = []
    for image_id in request.image_ids:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
        if db_analysis:
            results.append({
                "id": image_id,
                "status": db_analysis.status,
                "error_code": db_analysis.error_code,
                "analysis_note": db_analysis.analysis_note,
                "inscription_percent": db_analysis.inscription_percent,
            })
        else:
            results.append({"id": image_id, "status": "not_found"})

    return {"success": True, "data": results}


@router.get("/analyze-status/{image_id}")
async def get_analyze_status(image_id: str, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    return {
        "success": True,
        "data": {
            "id": image_id,
            "status": db_analysis.status,
            "analysis_note": db_analysis.analysis_note,
            "error_code": db_analysis.error_code,
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent
        }
    }


@router.get("/queue-info/{image_id}")
async def get_queue_info(image_id: str, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    avg_seconds_per_job = 150
    status = db_analysis.status

    if status not in ("queued", "analyzing"):
        return {
            "success": True,
            "data": {
                "id": image_id,
                "status": status,
                "position": 0,
                "pending_count": 0,
                "processing_count": 0,
                "estimated_wait_seconds": 0,
                "via": "done"
            }
        }

    # 尝试从 Redis 获取实时队列位置（更准确）
    redis_available = False
    try:
        conn = _get_redis()
        redis_available = True
        # 尝试在 pending 列表中查找位置
        pending_list = conn.lrange(_QUEUE_KEY_PENDING, 0, -1)
        if image_id in pending_list:
            # Redis 列表是 lpush 的，最新在头部，所以反转索引
            idx_from_head = pending_list.index(image_id)
            position = len(pending_list) - idx_from_head  # 排队位置（1-based，队尾=1）
        else:
            position = None  # 可能已被 worker 取走
        pending_count = len(pending_list)
        processing_count = conn.llen(_QUEUE_KEY_PROCESSING) or 0
    except Exception:
        pass

    # 降级到 DB 查询
    if not redis_available:
        job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
        if not job or not job.created_at:
            return {
                "success": True,
                "data": {
                    "id": image_id,
                    "status": status,
                    "position": None,
                    "pending_count": None,
                    "processing_count": None,
                    "estimated_wait_seconds": None,
                    "via": "db"
                }
            }

        before_count = (
            db.query(TubiJob)
            .filter(TubiJob.status == "queued")
            .filter(TubiJob.created_at < job.created_at)
            .count()
        )
        pending_count = db.query(TubiJob).filter(TubiJob.status == "queued").count()
        processing_count = db.query(TubiJob).filter(TubiJob.status == "processing").count()
        position = before_count + 1

    # 计算预估等待时间
    if position and position > 0:
        estimated_wait_seconds = (position - 1) * avg_seconds_per_job
    else:
        estimated_wait_seconds = 0

    return {
        "success": True,
        "data": {
            "id": image_id,
            "status": status,
            "position": position,
            "pending_count": pending_count,
            "processing_count": processing_count,
            "estimated_wait_seconds": estimated_wait_seconds,
            "via": "redis" if redis_available else "db"
        }
    }


@router.post("/year")
async def save_year_data(request: YearDataRequest, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == request.image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    db_analysis.year = request.year
    db_analysis.period = request.period
    # 自动计算分期（period_phase）
    db_analysis.period_phase = get_period_phase(db_analysis.year, db_analysis.artist)
    db.commit()

    return {
        "success": True,
        "message": "年代信息已保存"
    }


@router.put("/image-info/{image_id}")
async def update_image_info(
    image_id: str,
    request: ImageInfoRequest,
    db: Session = Depends(get_db)
):
    """更新图片信息（标题、作者等）"""
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    if request.title is not None:
        db_analysis.title = request.title
    if request.artist is not None:
        db_analysis.artist = request.artist
    if request.year is not None:
        db_analysis.year = request.year
    if request.age is not None:
        db_analysis.period = str(request.age)
    if request.period is not None:
        db_analysis.period = request.period
    if request.notes is not None:
        db_analysis.notes = request.notes
    if request.analysis_note is not None:
        db_analysis.analysis_note = request.analysis_note
    if request.inscription_content is not None:
        db_analysis.inscription_content = request.inscription_content
    if request.seal_content is not None:
        db_analysis.seal_content = request.seal_content
    if request.inscription_percent is not None:
        db_analysis.inscription_percent = request.inscription_percent
    if request.painting_percent is not None:
        db_analysis.painting_percent = request.painting_percent
    if request.blank_percent is not None:
        db_analysis.blank_percent = request.blank_percent

    # 自动重新计算分期（period_phase）
    db_analysis.period_phase = get_period_phase(db_analysis.year, db_analysis.artist)

    db.commit()
    db.refresh(db_analysis)

    return {
        "success": True,
        "message": "图片信息已更新",
        "data": {
            "id": db_analysis.image_id,
            "title": db_analysis.title,
            "artist": db_analysis.artist,
            "year": db_analysis.year,
            "period": db_analysis.period,
            "notes": db_analysis.notes,
            "inscription_content": db_analysis.inscription_content,
            "seal_content": db_analysis.seal_content,
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent
        }
    }


@router.post("/image/{image_id}/replace-image")
async def replace_image(
    image_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """替换图片（保留元数据和面积数据，只更新文件+缩略图）
    - 保留：title/artist/year/period/notes/analysis_note/inscription_content/seal_content/inscription_percent/painting_percent/blank_percent/regions/position_analysis/content_analysis/theme_tags/material_tags/artwork_width_cm/artwork_height_cm/album_name/album_index
    - 更新：filepath/thumbnail_path/image_width/image_height/filename/annotated_image_path（设为None）
    """
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    if file.content_type not in ["image/jpeg", "image/png", "image/bmp"]:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP 格式")

    # 复用原 image_id，生成新文件名（扩展名根据上传文件确定）
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{image_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    thumbnail_filename = f"{image_id}_thumb.jpg"
    thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)

    MAX_UPLOAD_SIZE = 50 * 1024 * 1024

    def _save_streaming() -> int:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        size = 0
        with open(filepath, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise ValueError("too_large")
                f.write(chunk)
        return size

    t0 = time.perf_counter()
    try:
        await run_in_threadpool(_save_streaming)
    except ValueError:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
        raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
    finally:
        try:
            await file.close()
        except Exception:
            pass
    logger.info("替换图片写入完成，用时: %.3fs", time.perf_counter() - t0)

    t1 = time.perf_counter()
    try:
        def _size_and_thumb():
            from PIL import ImageOps
            with Image.open(filepath) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                if thumbnail_path:
                    thumb = img
                    if thumb.mode != "RGB":
                        thumb = thumb.convert("RGB")
                    ratio = width / height if height > 0 else 1
                    if ratio > 2:
                        # 超宽图片：先缩放高度到 300，再从中间裁切 300x300
                        max_size = 300
                        scale = max_size / height
                        scaled_w = int(width * scale)
                        img_scaled = thumb.resize((scaled_w, max_size), Image.Resampling.LANCZOS)
                        left = max(0, (scaled_w - max_size) // 2)
                        top = 0
                        right = left + max_size
                        bottom = max_size
                        img_cropped = img_scaled.crop((left, top, right, bottom))
                        img_scaled.close()
                        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                        img_cropped.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                        ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                    else:
                        # 普通图片：整体缩放
                        thumb.thumbnail((300, 300), Image.Resampling.LANCZOS)
                        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                        thumb.save(thumbnail_path, "JPEG", quality=85, optimize=False)
                        ok = os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0
                else:
                    ok = False
            return width, height, ok
        width, height, thumb_ok = await run_in_threadpool(_size_and_thumb)
        logger.info("替换图像尺寸: %dx%d", width, height)
    except Exception as e:
        logger.error("读取替换图像尺寸失败: %s", e)
        width, height = 0, 0
        thumb_ok = False
    if not thumb_ok:
        thumbnail_path = None
        thumbnail_filename = None
    logger.info("缩略图处理完成，用时: %.3fs", time.perf_counter() - t1)

    # 更新数据库：只更新文件路径、尺寸、标注图清空，保留其他所有数据
    db_analysis.filename = file.filename
    db_analysis.filepath = normalize_path(filepath)
    db_analysis.thumbnail_path = normalize_path(thumbnail_path) if thumbnail_path else None
    db_analysis.image_width = width
    db_analysis.image_height = height
    db_analysis.annotated_image_path = None  # 清空标注图，下次标注时重新生成
    db.commit()
    db.refresh(db_analysis)

    logger.info("图片替换成功: %s", image_id)
    return {
        "success": True,
        "data": {
            "id": image_id,
            "filename": file.filename,
            "title": db_analysis.title,
            "artist": db_analysis.artist,
            "url": get_static_url(f"uploads/{filename}"),
            "thumbnail_url": get_static_url(f"thumbnails/{thumbnail_filename}") if thumbnail_filename else None,
            "width": width,
            "height": height
        }
    }


@router.get("/results")
async def get_all_results(
    skip: int = 0,
    limit: int = 16,
    artist: Optional[str] = Query(default=None, description="画家名称筛选"),
    db: Session = Depends(get_db)
):
    """获取所有分析结果列表"""
    # 全量查询（无筛选且 limit 足够大时）走持久缓存，所有用户共享
    if not artist and limit >= 500:
        cached = _get_results_cache()
        if cached:
            return cached

    query = db.query(TubiAnalysis)
    if artist:
        from app.services.keyword_extractor import get_artist_aliases
        aliases = get_artist_aliases(artist)
        query = query.filter(TubiAnalysis.artist.in_(aliases))
    analyses = query.order_by(TubiAnalysis.created_at.desc()).offset(skip).limit(limit).all()

    is_full_list = not artist and limit >= 500  # 全量查询 → 轻量 response + 持久缓存

    results = []
    for analysis in analyses:
        # 从 filepath 提取文件名
        if analysis.filepath:
            actual_filename = os.path.basename(analysis.filepath.replace('/', os.sep))
            file_path_local = _to_local_path(analysis.filepath)
            file_exists = _cached_exists(file_path_local)
        elif analysis.filename:
            actual_filename = analysis.filename
            file_exists = _cached_exists(os.path.join(UPLOAD_DIR, analysis.filename))
        else:
            actual_filename = None
            file_exists = False

        # 处理缩略图
        thumbnail_url = None
        if analysis.thumbnail_path:
            thumbnail_path_local = _to_local_path(analysis.thumbnail_path)
            if _cached_exists(thumbnail_path_local):
                thumbnail_filename = os.path.basename(analysis.thumbnail_path.replace('/', os.sep))
                thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
        elif actual_filename and file_exists:
            thumbnail_url = get_static_url(f"uploads/{actual_filename}")

        # 基础字段（所有查询都需要）
        item = {
            "id": analysis.image_id,
            "db_id": analysis.id,
            "image_id": analysis.image_id,
            "filename": analysis.filename,
            "title": analysis.title,
            "artist": analysis.artist,
            "year": analysis.year,
            "period": analysis.period,
            "inscription_percent": analysis.inscription_percent,
            "painting_percent": analysis.painting_percent,
            "blank_percent": analysis.blank_percent,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "url": get_static_url(f"uploads/{actual_filename}") if actual_filename and file_exists else None,
            "thumbnail_url": thumbnail_url,
            "album_name": analysis.album_name,
            "album_index": analysis.album_index,
            "tags": analysis.tags,
        }

        # 全量查询跳过重字段（regions, 分析文本, JSON解析等），大幅减小缓存体积
        if not is_full_list:
            # 检查标注图片是否存在
            annotated_exists = False
            if analysis.annotated_image_path:
                annotated_path_local = _to_local_path(analysis.annotated_image_path)
                annotated_exists = _cached_exists(annotated_path_local)

            # 解析 position_analysis JSON
            pos_analysis_data = None
            if analysis.position_analysis:
                try:
                    pos_analysis_data = json.loads(analysis.position_analysis) if isinstance(analysis.position_analysis, str) else analysis.position_analysis
                except Exception:
                    pos_analysis_data = None

            item.update({
                "image_width": analysis.image_width,
                "image_height": analysis.image_height,
                "regions": analysis.regions,
                "position_analysis": pos_analysis_data,
                "annotated_image_url": get_static_url(f"annotated/annotated_{analysis.image_id}.jpg") if annotated_exists else None,
                "is_manual_annotated": bool(analysis.is_manual_annotated) if analysis.is_manual_annotated is not None else False,
                "analysis_note": analysis.analysis_note,
                "inscription_content": analysis.inscription_content,
                "inscription_modern": analysis.inscription_modern,
                "seal_content": analysis.seal_content,
                "content_analysis": json.loads(analysis.content_analysis) if analysis.content_analysis else None,
                "artwork_width_cm": analysis.artwork_width_cm,
                "artwork_height_cm": analysis.artwork_height_cm,
                "material_tags": analysis.material_tags,
                "period_phase": analysis.period_phase,
                "computed_tags": compute_tags_cached({
                    "title": analysis.title,
                    "period_phase": analysis.period_phase,
                    "artwork_height_cm": analysis.artwork_height_cm,
                    "artwork_width_cm": analysis.artwork_width_cm,
                    "content_analysis": analysis.content_analysis,
                    "material_tags": analysis.material_tags,
                })
            })

        results.append(item)

    response = {
        "success": True,
        "data": results,
        "total": db.query(TubiAnalysis).count()
    }
    # 全量查询写入持久缓存（轻量版本）
    if is_full_list:
        _set_results_cache(response)
    return response


@router.get("/search")
async def search_images(
    keyword: str = None,
    db: Session = Depends(get_db)
):
    """
    搜索画作

    - **keyword**: 搜索关键词（支持标题、作者、年代、备注、题跋原文、题跋翻译、印章、主题标签、画材标签模糊搜索，年份精确匹配）
    """
    try:
        if not keyword:
            return {
                "success": False,
                "message": "请输入搜索关键词",
                "data": []
            }

        # 构建查询
        query = db.query(TubiAnalysis)

        # 关键词搜索（标题、作者、年代、备注、题跋、印章、标签、年份）
        keyword_filter = f"%{keyword}%"
        filters = [
            TubiAnalysis.title.ilike(keyword_filter),
            TubiAnalysis.artist.ilike(keyword_filter),
            TubiAnalysis.period.ilike(keyword_filter),
            TubiAnalysis.notes.ilike(keyword_filter),
            TubiAnalysis.analysis_note.ilike(keyword_filter),
            TubiAnalysis.inscription_content.ilike(keyword_filter),
            TubiAnalysis.inscription_modern.ilike(keyword_filter),
            TubiAnalysis.seal_content.ilike(keyword_filter),
            TubiAnalysis.theme_tags.ilike(keyword_filter),
            TubiAnalysis.material_tags.ilike(keyword_filter),
        ]
        # 年份精确匹配（keyword 为纯数字时）
        try:
            year_val = int(keyword)
            filters.append(TubiAnalysis.year == year_val)
        except (ValueError, TypeError):
            pass
        query = query.filter(or_(*filters))

        # 按创建时间倒序
        analyses = query.order_by(TubiAnalysis.created_at.desc()).all()

        # 组装结果
        results = []
        for analysis in analyses:
            # 从 filepath 提取文件名
            if analysis.filepath:
                actual_filename = os.path.basename(analysis.filepath.replace('/', os.sep))
                file_path_local = _to_local_path(analysis.filepath)
                file_exists = _cached_exists(file_path_local)
            elif analysis.filename:
                actual_filename = analysis.filename
                file_exists = _cached_exists(os.path.join(UPLOAD_DIR, analysis.filename))
            else:
                actual_filename = None
                file_exists = False

            # 处理缩略图
            thumbnail_url = None
            if analysis.thumbnail_path:
                thumbnail_path_local = _to_local_path(analysis.thumbnail_path)
                if _cached_exists(thumbnail_path_local):
                    thumbnail_filename = os.path.basename(analysis.thumbnail_path.replace('/', os.sep))
                    thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
            elif actual_filename and file_exists:
                thumbnail_url = get_static_url(f"uploads/{actual_filename}")

            # 检查标注图片是否存在
            annotated_exists = False
            if analysis.annotated_image_path:
                annotated_path_local = _to_local_path(analysis.annotated_image_path)
                annotated_exists = _cached_exists(annotated_path_local)

            # 解析 position_analysis JSON
            pos_analysis_data = None
            if analysis.position_analysis:
                try:
                    pos_analysis_data = json.loads(analysis.position_analysis) if isinstance(analysis.position_analysis, str) else analysis.position_analysis
                except Exception:
                    pos_analysis_data = None

            results.append({
                "id": analysis.image_id,
                "filename": analysis.filename,
                "title": analysis.title,
                "artist": analysis.artist,
                "year": analysis.year,
                "period": analysis.period,
                "notes": analysis.notes,
                "image_width": analysis.image_width,
                "image_height": analysis.image_height,
                "inscription_percent": analysis.inscription_percent,
                "painting_percent": analysis.painting_percent,
                "blank_percent": analysis.blank_percent,
                "regions": analysis.regions,
                "position_analysis": pos_analysis_data,
                "status": analysis.status,
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                "url": get_static_url(f"uploads/{actual_filename}") if actual_filename and file_exists else None,
                "thumbnail_url": thumbnail_url,
                "annotated_image_url": get_static_url(f"annotated/annotated_{analysis.image_id}.jpg") if annotated_exists else None,
                "is_manual_annotated": bool(analysis.is_manual_annotated) if analysis.is_manual_annotated is not None else False,
                "analysis_note": analysis.analysis_note,
                "inscription_content": analysis.inscription_content,
                "inscription_modern": analysis.inscription_modern,
                "seal_content": analysis.seal_content
            })

        return {
            "success": True,
            "data": results,
            "total": len(results)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.delete("/image/{image_id}")
async def delete_image(image_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin_api_key(request)
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    # 删除文件 - 使用跨平台路径处理
    if db_analysis.filepath:
        file_path_local = get_full_file_path(db_analysis.filepath, PROJECT_ROOT)
        if _cached_exists(file_path_local):
            os.remove(file_path_local)
    if db_analysis.annotated_image_path:
        annotated_path_local = get_full_file_path(db_analysis.annotated_image_path, PROJECT_ROOT)
        if _cached_exists(annotated_path_local):
            os.remove(annotated_path_local)

    # 删除数据库记录
    db.delete(db_analysis)
    db.commit()
    _clear_results_cache()  # 删除后使缓存失效

    return {
        "success": True,
        "message": "图像已删除"
    }


@router.delete("/clear-all")
async def clear_all_analyses(request: Request, db: Session = Depends(get_db)):
    """清空所有分析数据"""
    _require_admin_api_key(request)
    try:
        # 获取所有记录
        all_analyses = db.query(TubiAnalysis).all()

        # 删除所有关联文件 - 使用跨平台路径处理
        for analysis in all_analyses:
            if analysis.filepath:
                file_path_local = get_full_file_path(analysis.filepath, PROJECT_ROOT)
                if os.path.exists(file_path_local):
                    try:
                        os.remove(file_path_local)
                    except Exception as e:
                        logger.error("删除文件失败 %s: %s", file_path_local, e)

            if analysis.annotated_image_path:
                annotated_path_local = get_full_file_path(analysis.annotated_image_path, PROJECT_ROOT)
                if os.path.exists(annotated_path_local):
                    try:
                        os.remove(annotated_path_local)
                    except Exception as e:
                        logger.error("删除标注图失败 %s: %s", annotated_path_local, e)

        # 删除所有数据库记录
        db.query(TubiAnalysis).delete()
        db.commit()

        return {
            "success": True,
            "message": f"已清空 {len(all_analyses)} 条分析记录",
            "deleted_count": len(all_analyses)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查接口 - 检查 Redis 和队列状态"""
    status = {
        "redis": False,
        "queue_pending": 0,
        "queue_processing": 0,
        "worker_running": False
    }
    
    # 检查 Redis
    try:
        conn = _get_redis()
        status["redis"] = True
        
        # 检查队列
        status["queue_pending"] = conn.llen("tubi:queue:pending") or 0
        status["queue_processing"] = conn.llen("tubi:queue:processing") or 0
        
        # 检查 worker 是否活跃（通过锁检测）
        try:
            lock = conn.lock("tubi:analysis:lock", timeout=10)
            # 如果能立即获取锁，说明没有 worker 在运行
            acquired = lock.acquire(blocking=False)
            if acquired:
                lock.release()
                status["worker_running"] = False
            else:
                status["worker_running"] = True
        except Exception:
            status["worker_running"] = False
            
    except Exception as e:
        status["redis_error"] = str(e)
    
    return {"success": True, "data": status}


# ── 尺寸录入 API ───────────────────────────────────────────────────────────

class DimensionUpdateRequest(BaseModel):
    artwork_width_cm: Optional[float] = None
    artwork_height_cm: Optional[float] = None
    album_name: Optional[str] = None
    album_index: Optional[int] = None


class AlbumDimensionRequest(BaseModel):
    album_name: str
    artwork_width_cm: float
    artwork_height_cm: float


@router.get("/dimensions")
async def get_dimensions(artist: Optional[str] = None, db: Session = Depends(get_db)):
    """
    尺寸录入专用接口：
    - 返回所有记录（默认李鱓）
    - 包含宽高、册页分组信息
    - 按年份分组（供前端按年筛选）
    """
    query = db.query(TubiAnalysis)
    
    if artist:
        # 获取该作者的所有别名
        from app.services.keyword_extractor import get_artist_aliases
        aliases = get_artist_aliases(artist)
        query = query.filter(TubiAnalysis.artist.in_(aliases))
    else:
        # 默认只查李鱓
        query = query.filter(TubiAnalysis.artist.in_(["李鱓", "李复堂", "李鳆"]))
    
    records = query.order_by(TubiAnalysis.year, TubiAnalysis.id).all()

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "image_id": r.image_id,
            "title": r.title,
            "year": r.year,
            "period": r.period or r.period_phase,
            "char_count": r.char_count,
            "artwork_width_cm": r.artwork_width_cm,
            "artwork_height_cm": r.artwork_height_cm,
            "album_name": r.album_name,
            "album_index": r.album_index,
            "tags": r.tags,
            "thumbnail_url": get_static_url(f"thumbnails/{os.path.basename(r.thumbnail_path)}") if r.thumbnail_path else None,
        })

    # 统计
    total = len(items)
    filled = sum(1 for i in items if i["artwork_width_cm"] is not None and i["artwork_height_cm"] is not None)

    # 按年份分组（无年份/年代不详的统一归入"年代不详"）
    from collections import defaultdict
    by_year = defaultdict(list)
    for item in items:
        year = item["year"]
        by_year[year].append(item)

    # 排序年份，"年代不详"放最后
    years = sorted([y for y in by_year.keys() if y is not None])
    if None in by_year:
        by_year["年代不详"] = by_year.pop(None)
        years.append("年代不详")

    return {
        "success": True,
        "data": {
            "items": items,
            "years": years,
            "by_year": dict(by_year),
            "total": total,
            "filled": filled,
            "empty": total - filled,
        }
    }


@router.put("/dimensions/{id}")
async def update_dimension(id: int, request: DimensionUpdateRequest, db: Session = Depends(get_db)):
    """更新单条记录的尺寸和册页信息"""
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.id == id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="记录不存在")

    if request.artwork_width_cm is not None:
        db_analysis.artwork_width_cm = round(request.artwork_width_cm, 1)
    if request.artwork_height_cm is not None:
        db_analysis.artwork_height_cm = round(request.artwork_height_cm, 1)
    if request.album_name is not None:
        db_analysis.album_name = request.album_name if request.album_name.strip() else None
    if request.album_index is not None:
        db_analysis.album_index = request.album_index

    db_analysis.updated_at = datetime.now()
    db.commit()
    db.refresh(db_analysis)

    return {
        "success": True,
        "message": "尺寸已更新",
        "data": {
            "id": db_analysis.id,
            "title": db_analysis.title,
            "artwork_width_cm": db_analysis.artwork_width_cm,
            "artwork_height_cm": db_analysis.artwork_height_cm,
            "album_name": db_analysis.album_name,
            "album_index": db_analysis.album_index,
        }
    }


@router.put("/dimensions/album/batch")
async def batch_update_album_dimensions(request: AlbumDimensionRequest, db: Session = Depends(get_db)):
    """
    批量更新同册页的所有记录尺寸。
    根据 album_name 匹配，为该册页所有记录设置相同宽高。
    """
    updated = (
        db.query(TubiAnalysis)
        .filter(TubiAnalysis.album_name == request.album_name)
        .filter(TubiAnalysis.artist.in_(["李鱓", "李复堂", "李鳆"]))
        .all()
    )

    if not updated:
        raise HTTPException(status_code=404, detail=f"未找到册页：{request.album_name}")

    w = round(request.artwork_width_cm, 1)
    h = round(request.artwork_height_cm, 1)
    now = datetime.now()

    for r in updated:
        r.artwork_width_cm = w
        r.artwork_height_cm = h
        r.updated_at = now

    db.commit()

    return {
        "success": True,
        "message": f"已为「{request.album_name}」{len(updated)}条记录批量设置尺寸",
        "data": {
            "album_name": request.album_name,
            "artwork_width_cm": w,
            "artwork_height_cm": h,
            "updated_count": len(updated),
        }
    }


# ── 册页管理 API ───────────────────────────────────────────────────────────

class AlbumCreateRequest(BaseModel):
    name: str
    record_ids: Optional[List[str]] = None


class AlbumAddItemsRequest(BaseModel):
    record_ids: List[str]


class AlbumReorderRequest(BaseModel):
    item_order: List[str]


class AlbumRenameRequest(BaseModel):
    new_name: str


@router.get("/albums")
async def get_albums(
    artist: Optional[str] = Query(default=None, description="画家名称筛选"),
    db: Session = Depends(get_db)
):
    """获取所有册页列表（含统计）"""
    from collections import defaultdict
    
    query = db.query(TubiAnalysis).filter(TubiAnalysis.album_name.isnot(None))
    if artist:
        from app.services.keyword_extractor import get_artist_aliases
        aliases = get_artist_aliases(artist)
        query = query.filter(TubiAnalysis.artist.in_(aliases))
    records_with_album = query.order_by(TubiAnalysis.album_name, TubiAnalysis.album_index).all()
    
    albums = defaultdict(list)
    for r in records_with_album:
        albums[r.album_name].append(r)
    
    result = []
    for album_name, items in albums.items():
        sorted_items = sorted(items, key=lambda x: x.album_index or 0)
        cover_item = sorted_items[0] if sorted_items else None
        
        result.append({
            "name": album_name,
            "count": len(sorted_items),
            "cover_url": (
                get_static_url(f"thumbnails/{os.path.basename(cover_item.thumbnail_path)}")
                if cover_item and cover_item.thumbnail_path
                else None
            ),
            "cover_title": cover_item.title if cover_item else None,
        })
    
    return {"success": True, "data": result}


@router.get("/albums/{album_name}")
async def get_album(album_name: str, db: Session = Depends(get_db)):
    """获取册页详情（含作品列表）"""
    records = (
        db.query(TubiAnalysis)
        .filter(TubiAnalysis.album_name == album_name)
        .order_by(TubiAnalysis.album_index)
        .all()
    )
    
    if not records:
        raise HTTPException(status_code=404, detail=f"册页不存在: {album_name}")
    
    items = []
    for r in records:
        items.append({
            "id": r.image_id,
            "db_id": r.id,
            "title": r.title,
            "year": r.year,
            "album_index": r.album_index,
            "artwork_height_cm": r.artwork_height_cm,
            "artwork_width_cm": r.artwork_width_cm,
            "thumbnail_url": (
                get_static_url(f"thumbnails/{os.path.basename(r.thumbnail_path)}")
                if r.thumbnail_path
                else None
            ),
        })
    
    return {"success": True, "data": {"name": album_name, "items": items}}


@router.post("/albums")
async def create_album(request: AlbumCreateRequest, db: Session = Depends(get_db)):
    """创建新册页"""
    existing = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == request.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"册页名已存在: {request.name}")
    
    if request.record_ids:
        for idx, record_image_id in enumerate(request.record_ids):
            r = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == record_image_id).first()
            if r:
                r.album_name = request.name
                r.album_index = idx + 1
                r.updated_at = datetime.now()
    
    db.commit()
    return {"success": True, "message": f"册页「{request.name}」已创建"}


@router.put("/albums/{album_name}")
async def rename_album(album_name: str, request: AlbumRenameRequest, db: Session = Depends(get_db)):
    """重命名册页"""
    existing = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == request.new_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"册页名已存在: {request.new_name}")
    
    records = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == album_name).all()
    if not records:
        raise HTTPException(status_code=404, detail=f"册页不存在: {album_name}")
    
    for r in records:
        r.album_name = request.new_name
        r.updated_at = datetime.now()
    
    db.commit()
    return {"success": True, "message": f"册页已重命名为「{request.new_name}」"}


@router.delete("/albums/{album_name}")
async def delete_album(album_name: str, db: Session = Depends(get_db)):
    """删除册页（作品恢复自由态，不删除作品）"""
    records = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == album_name).all()
    
    if not records:
        raise HTTPException(status_code=404, detail=f"册页不存在: {album_name}")
    
    for r in records:
        r.album_name = None
        r.album_index = None
        r.updated_at = datetime.now()
    
    db.commit()
    return {"success": True, "message": f"册页「{album_name}」已删除，{len(records)} 幅作品恢复自由态"}


@router.post("/albums/{album_name}/items")
async def add_items_to_album(album_name: str, request: AlbumAddItemsRequest, db: Session = Depends(get_db)):
    """添加作品到册页"""
    existing = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == album_name).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"册页不存在: {album_name}")
    
    current_max = (
        db.query(func.max(TubiAnalysis.album_index))
        .filter(TubiAnalysis.album_name == album_name)
        .scalar() or 0
    )
    
    added = 0
    for record_image_id in request.record_ids:
        r = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == record_image_id).first()
        if r:
            r.album_name = album_name
            current_max += 1
            r.album_index = current_max
            r.updated_at = datetime.now()
            added += 1
    
    db.commit()
    return {"success": True, "message": f"已添加 {added} 幅作品到册页「{album_name}」"}


@router.delete("/albums/{album_name}/items/{record_id}")
async def remove_item_from_album(album_name: str, record_id: str, db: Session = Depends(get_db)):
    """从册页移除作品（作品恢复自由态）"""
    r = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if r.album_name != album_name:
        raise HTTPException(status_code=400, detail="该记录不属于此册页")
    
    r.album_name = None
    r.album_index = None
    r.updated_at = datetime.now()
    db.commit()
    
    return {"success": True, "message": f"作品「{r.title}」已从册页移除"}


@router.put("/albums/{album_name}/reorder")
async def reorder_album_items(album_name: str, request: AlbumReorderRequest, db: Session = Depends(get_db)):
    """重新排序册页内作品"""
    records = db.query(TubiAnalysis).filter(TubiAnalysis.album_name == album_name).all()
    if not records:
        raise HTTPException(status_code=404, detail=f"册页不存在: {album_name}")
    
    record_image_ids_in_album = {r.image_id for r in records}
    for record_image_id in request.item_order:
        if record_image_id not in record_image_ids_in_album:
            raise HTTPException(status_code=400, detail=f"记录 {record_image_id} 不属于此册页")
    
    for idx, record_image_id in enumerate(request.item_order):
        r = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == record_image_id).first()
        if r:
            r.album_index = idx + 1
            r.updated_at = datetime.now()
    
    db.commit()
    return {"success": True, "message": "册页顺序已更新"}


@router.get("/albums/navigation/{record_id}")
async def get_album_navigation(record_id: str, db: Session = Depends(get_db)):
    """获取指定作品的册页导航信息（返回同册页其他作品列表）"""
    if record_id.isdigit():
        current_record = db.query(TubiAnalysis).filter(TubiAnalysis.id == int(record_id)).first()
    else:
        current_record = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == record_id).first()
    
    if not current_record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    if not current_record.album_name:
        return {"success": True, "data": {"is_in_album": False}}
    
    album_records = (
        db.query(TubiAnalysis)
        .filter(TubiAnalysis.album_name == current_record.album_name)
        .order_by(TubiAnalysis.album_index)
        .all()
    )
    
    items = []
    current_index = None
    for idx, r in enumerate(album_records):
        if r.id == current_record.id:
            current_index = idx
        
        items.append({
            "id": r.image_id,
            "db_id": r.id,
            "title": r.title,
            "album_index": r.album_index,
            "thumbnail_url": (
                get_static_url(f"thumbnails/{os.path.basename(r.thumbnail_path)}")
                if r.thumbnail_path
                else None
            ),
            "is_current": r.id == current_record.id,
        })
    
    return {
        "success": True,
        "data": {
            "is_in_album": True,
            "album_name": current_record.album_name,
            "current_index": current_index,
            "total_count": len(items),
            "items": items,
        }
    }


# ── 标签管理 API ───────────────────────────────────────────────────────────

class TagCreateRequest(BaseModel):
    name: str


class TagUpdateRequest(BaseModel):
    old_name: str
    new_name: str


class TagItemRequest(BaseModel):
    tag_name: str
    record_ids: List[int]


@router.get("/tags")
async def get_tags(
    artist: Optional[str] = Query(default=None, description="画家名称筛选"),
    db: Session = Depends(get_db)
):
    """获取所有标签列表（含统计）"""
    from collections import defaultdict
    
    tag_counts = defaultdict(int)
    
    query = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None))
    if artist:
        from app.services.keyword_extractor import get_artist_aliases
        aliases = get_artist_aliases(artist)
        query = query.filter(TubiAnalysis.artist.in_(aliases))
    records_with_tags = query.all()
    
    for r in records_with_tags:
        try:
            tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
            if isinstance(tags, list):
                for tag in tags:
                    if tag and isinstance(tag, str):
                        tag_counts[tag] += 1
        except Exception:
            pass
    
    result = []
    for tag_name, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
        result.append({"name": tag_name, "count": count})
    
    return {"success": True, "data": result}


@router.get("/tags/{tag_name}")
async def get_tag_items(tag_name: str, db: Session = Depends(get_db)):
    """获取标签下的所有作品"""
    records = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None)).all()
    
    items = []
    for r in records:
        try:
            tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
            if isinstance(tags, list) and tag_name in tags:
                items.append({
                    "id": r.id,
                    "image_id": r.image_id,
                    "title": r.title,
                    "thumbnail_url": (
                        get_static_url(f"thumbnails/{os.path.basename(r.thumbnail_path)}")
                        if r.thumbnail_path
                        else None
                    ),
                })
        except Exception:
            pass
    
    return {"success": True, "data": {"name": tag_name, "items": items}}


@router.post("/tags")
async def create_tag(request: TagCreateRequest, db: Session = Depends(get_db)):
    """创建新标签（实际上标签是动态的，这个接口主要用于验证标签名）"""
    existing = db.query(TubiAnalysis).filter(TubiAnalysis.tags.like(f'%{request.name}%')).first()
    if existing:
        return {"success": True, "message": f"标签「{request.name}」已存在"}
    
    return {"success": True, "message": f"标签「{request.name}」可以使用"}


@router.put("/tags")
async def rename_tag(request: TagUpdateRequest, db: Session = Depends(get_db)):
    """重命名标签"""
    records = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None)).all()
    
    updated_count = 0
    for r in records:
        try:
            tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
            if isinstance(tags, list) and request.old_name in tags:
                tags = [request.new_name if t == request.old_name else t for t in tags]
                r.tags = json.dumps(tags, ensure_ascii=False)
                r.updated_at = datetime.now()
                updated_count += 1
        except Exception:
            pass
    
    db.commit()
    return {"success": True, "message": f"标签已重命名，更新了 {updated_count} 条记录"}


@router.delete("/tags/{tag_name}")
async def delete_tag(tag_name: str, db: Session = Depends(get_db)):
    """删除标签（从所有作品中移除该标签）"""
    records = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None)).all()
    
    updated_count = 0
    for r in records:
        try:
            tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
            if isinstance(tags, list) and tag_name in tags:
                tags = [t for t in tags if t != tag_name]
                r.tags = json.dumps(tags, ensure_ascii=False) if tags else None
                r.updated_at = datetime.now()
                updated_count += 1
        except Exception:
            pass
    
    db.commit()
    return {"success": True, "message": f"标签已删除，更新了 {updated_count} 条记录"}


@router.post("/tags/items")
async def add_items_to_tag(request: TagItemRequest, db: Session = Depends(get_db)):
    """给作品添加标签"""
    added_count = 0
    for record_id in request.record_ids:
        r = db.query(TubiAnalysis).filter(TubiAnalysis.id == record_id).first()
        if r:
            try:
                tags = json.loads(r.tags) if r.tags and isinstance(r.tags, str) else []
                if not isinstance(tags, list):
                    tags = []
                if request.tag_name not in tags:
                    tags.append(request.tag_name)
                    r.tags = json.dumps(tags, ensure_ascii=False)
                    r.updated_at = datetime.now()
                    added_count += 1
            except Exception:
                pass
    
    db.commit()
    return {"success": True, "message": f"已为 {added_count} 幅作品添加标签「{request.tag_name}」"}


@router.delete("/tags/{tag_name}/items/{record_id}")
async def remove_item_from_tag(tag_name: str, record_id: int, db: Session = Depends(get_db)):
    """从作品移除标签"""
    r = db.query(TubiAnalysis).filter(TubiAnalysis.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    try:
        tags = json.loads(r.tags) if r.tags and isinstance(r.tags, str) else []
        if tag_name in tags:
            tags = [t for t in tags if t != tag_name]
            r.tags = json.dumps(tags, ensure_ascii=False) if tags else None
            r.updated_at = datetime.now()
            db.commit()
            return {"success": True, "message": f"标签已从作品移除"}
        else:
            return {"success": True, "message": "作品没有此标签"}
    except Exception:
        raise HTTPException(status_code=500, detail="更新失败")


@router.delete("/tags/all")
async def reset_all_tags(db: Session = Depends(get_db)):
    """清空所有作品的 tags 字段（用于重置自动标签）"""
    updated_count = 0
    records = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None)).all()
    for r in records:
        r.tags = None
        r.updated_at = datetime.now()
        updated_count += 1
    db.commit()
    return {"success": True, "message": f"已清空 {updated_count} 条作品的标签"}


# ── 统计扩展 API ───────────────────────────────────────────────────────────

@router.get("/stats/extended")
async def get_extended_stats(db: Session = Depends(get_db)):
    """获取扩展统计（含册页和标签统计）"""
    from collections import defaultdict
    
    total = db.query(TubiAnalysis).count()
    
    album_records = db.query(TubiAnalysis).filter(TubiAnalysis.album_name.isnot(None)).all()
    album_groups = defaultdict(list)
    for r in album_records:
        album_groups[r.album_name].append(r)
    
    album_count = len(album_groups)
    album_item_count = len(album_records)
    
    tag_counts = defaultdict(int)
    tag_records = db.query(TubiAnalysis).filter(TubiAnalysis.tags.isnot(None)).all()
    for r in tag_records:
        try:
            tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
            if isinstance(tags, list):
                for tag in tags:
                    if tag and isinstance(tag, str):
                        tag_counts[tag] += 1
        except Exception:
            pass
    
    def get_size_category(height_cm):
        if not height_cm:
            return None
        if height_cm < 70:
            return "小幅"
        elif height_cm <= 150:
            return "中幅"
        else:
            return "大幅"
    
    size_stats = defaultdict(int)
    records_with_size = db.query(TubiAnalysis).filter(TubiAnalysis.artwork_height_cm.isnot(None)).all()
    for r in records_with_size:
        cat = get_size_category(r.artwork_height_cm)
        if cat:
            size_stats[cat] += 1
    
    small_size_album_count = 0
    small_size_album_item_count = 0
    for r in records_with_size:
        cat = get_size_category(r.artwork_height_cm)
        if cat == "小幅" and r.album_name:
            small_size_album_item_count += 1
    
    small_album_names = set()
    for r in records_with_size:
        cat = get_size_category(r.artwork_height_cm)
        if cat == "小幅" and r.album_name:
            small_album_names.add(r.album_name)
    small_size_album_count = len(small_album_names)
    
    return {
        "success": True,
        "data": {
            "total": total,
            "albums": {
                "count": album_count,
                "item_count": album_item_count,
            },
            "tags": {
                "count": len(tag_counts),
                "item_count": sum(tag_counts.values()),
                "top_tags": [{"name": k, "count": v} for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])[:10]]
            },
            "sizes": {
                "small": size_stats.get("小幅", 0),
                "medium": size_stats.get("中幅", 0),
                "large": size_stats.get("大幅", 0),
                "small_with_albums": small_size_album_item_count,
                "small_album_count": small_size_album_count,
            },
        }
    }


@router.get("/{id}")
async def get_record_by_id(id: str, db: Session = Depends(get_db)):
    """通过数据库主键或 image_id 获取单条记录（用于标注工具等场景）"""
    # 支持数字主键和 UUID 字符串两种方式
    if id.isdigit():
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.id == int(id)).first()
    else:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 构建图片URL
    if db_analysis.filepath:
        actual_filename = os.path.basename(db_analysis.filepath.replace('/', os.sep))
        image_url = get_static_url(f"uploads/{actual_filename}")
    elif db_analysis.filename:
        image_url = get_static_url(f"uploads/{db_analysis.filename}")
    else:
        image_url = None

    thumbnail_url = None
    if db_analysis.thumbnail_path:
        thumb_local = _to_local_path(db_analysis.thumbnail_path)
        if _cached_exists(thumb_local):
            thumb_fn = os.path.basename(db_analysis.thumbnail_path.replace('/', os.sep))
            thumbnail_url = get_static_url(f"thumbnails/{thumb_fn}")
        else:
            thumbnail_url = image_url
    else:
        thumbnail_url = image_url

    # 解析 regions
    regions = None
    if db_analysis.regions:
        try:
            regions = json.loads(db_analysis.regions) if isinstance(db_analysis.regions, str) else db_analysis.regions
        except Exception:
            regions = None

    return {
        "success": True,
        "data": {
            "id": db_analysis.id,
            "image_id": db_analysis.image_id,
            "title": db_analysis.title,
            "artist": db_analysis.artist,
            "year": db_analysis.year,
            "period": db_analysis.period,
            "url": image_url,
            "thumbnail_url": thumbnail_url,
            "filepath": image_url,
            "width": db_analysis.image_width,
            "height": db_analysis.image_height,
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent,
            "regions": regions,
            "status": db_analysis.status,
            "is_manual_annotated": bool(db_analysis.is_manual_annotated) if db_analysis.is_manual_annotated is not None else False,
            "artwork_width_cm": db_analysis.artwork_width_cm,
            "artwork_height_cm": db_analysis.artwork_height_cm,
        }
    }


class ManualRegionsRequest(BaseModel):
    regions: List[RegionData]  # 全部算作 inscription_regions


@router.patch("/{id}/regions")
async def update_regions_manual(
    id: str,
    request: ManualRegionsRequest,
    db: Session = Depends(get_db)
):
    """
    手动标注区域接口。
    接收矩形区域列表，根据 type 分别归入 inscription_regions 或 painting_regions，
    自动重算 inscription_percent 和 painting_percent（fillpoly 像素级精确），
    blank_percent 由系统根据剩余空间推算。
    保存后生成三色标注图。
    """
    # 支持数字ID或UUID字符串查询
    if id.isdigit():
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.id == int(id)).first()
    else:
        db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 获取图片尺寸 - 优先使用实际图片尺寸，确保坐标系一致
    original_path = get_full_file_path(db_analysis.filepath, PROJECT_ROOT) if db_analysis.filepath else None
    if original_path and os.path.exists(original_path):
        try:
            from PIL import Image
            with Image.open(original_path) as img:
                actual_width, actual_height = img.size
                # 如果数据库尺寸和实际尺寸差异较大，使用实际尺寸
                db_width = db_analysis.image_width or actual_width
                db_height = db_analysis.image_height or actual_height
                if abs(db_width - actual_width) > 10 or abs(db_height - actual_height) > 10:
                    logger.warning(f"[update_regions_manual] 数据库尺寸({db_width}x{db_height})与实际尺寸({actual_width}x{actual_height})不一致，使用实际尺寸")
                    width, height = actual_width, actual_height
                    # 更新数据库中的尺寸
                    db_analysis.image_width = actual_width
                    db_analysis.image_height = actual_height
                else:
                    width, height = db_width, db_height
        except Exception as e:
            logger.error(f"[update_regions_manual] 读取图片尺寸失败: {e}")
            width = db_analysis.image_width or 1
            height = db_analysis.image_height or 1
    else:
        width = db_analysis.image_width or 1
        height = db_analysis.image_height or 1

    # 构建 regions dict（根据 type 分别归入 inscription/painting）
    inscription_list = []
    painting_list = []
    logger.info(f"[update_regions_manual] 接收到 {len(request.regions)} 个区域")
    for i, r in enumerate(request.regions):
        # 优先使用多边形 points，其次使用矩形 x1/y1/x2/y2
        if r.points and len(r.points) >= 3:
            region_data = {
                "type": "polygon",
                "points": [{"x": p.x, "y": p.y} for p in r.points]
            }
            logger.info(f"[update_regions_manual] 区域 {i}: type={r.type}, 多边形点数={len(r.points)}")
        elif r.x1 is not None and r.y1 is not None and r.x2 is not None and r.y2 is not None:
            region_data = {
                "type": "rectangle",
                "x1": r.x1, "y1": r.y1,
                "x2": r.x2, "y2": r.y2
            }
            logger.info(f"[update_regions_manual] 区域 {i}: type={r.type}, 矩形=({r.x1},{r.y1})-({r.x2},{r.y2})")
        else:
            logger.warning(f"[update_regions_manual] 区域 {i}: 无效数据，跳过")
            continue  # 跳过无效区域
        
        # 根据 type 字段分别存储，默认为 inscription
        region_type = r.type if r.type else 'inscription'
        if region_type == 'painting':
            painting_list.append(region_data)
            logger.info(f"[update_regions_manual] 区域 {i}: 归入 painting_list")
        else:
            inscription_list.append(region_data)
            logger.info(f"[update_regions_manual] 区域 {i}: 归入 inscription_list")

    regions_dict = {
        "inscription_regions": inscription_list,
        "painting_regions": painting_list,
        "blank_regions": []
    }

    # 标记为手动编辑，防止后续自动分析覆盖
    regions_dict["_meta"] = {"user_edited": True}

    # 用 fillpoly 重算面积
    from app.services.area_calculator import calculate_area_stats_fillpoly
    stats = calculate_area_stats_fillpoly(regions_dict, width, height)

    db_analysis.regions = json.dumps(regions_dict, ensure_ascii=False)
    db_analysis.inscription_percent = stats["inscription_percent"]
    db_analysis.painting_percent = stats["painting_percent"]
    db_analysis.blank_percent = stats["blank_percent"]
    db_analysis.updated_at = datetime.now()
    db_analysis.status = "analyzed"  # 标记为已分析
    db_analysis.is_manual_annotated = 1  # 标记为手动标注
    _clear_results_cache()  # 分析完成后使缓存失效

    # 自动标签持久化：将 compute_tags 结果追加写入 tags 字段
    try:
        record_for_tags = {
            "title": db_analysis.title,
            "period_phase": db_analysis.period_phase,
            "artwork_height_cm": db_analysis.artwork_height_cm,
            "artwork_width_cm": db_analysis.artwork_width_cm,
            "content_analysis": db_analysis.content_analysis,
            "material_tags": db_analysis.material_tags,
        }
        auto_tags = compute_tags_cached(record_for_tags)
        if auto_tags:
            existing_tags = []
            if db_analysis.tags:
                try:
                    existing_tags = json.loads(db_analysis.tags) if isinstance(db_analysis.tags, str) else db_analysis.tags
                except Exception:
                    existing_tags = []
            if not isinstance(existing_tags, list):
                existing_tags = []
            for tag in auto_tags:
                if tag not in existing_tags:
                    existing_tags.append(tag)
            db_analysis.tags = json.dumps(existing_tags, ensure_ascii=False)
    except Exception as e:
        logger.error("自动标签持久化失败: %s", e)

    db.commit()
    db.refresh(db_analysis)

    # 生成 position_analysis（规则计算，不调用VL）
    try:
        from app.services.inscription_position_analyzer import analyze_inscription_position_simple
        position_analysis = analyze_inscription_position_simple(
            regions_dict, width, height
        )
        db_analysis.position_analysis = json.dumps(position_analysis, ensure_ascii=False)
    except Exception as e:
        logger.error("生成 position_analysis 失败: %s", e)
        position_analysis = None
    
    # 生成三色面积占比示意图（题跋红/绘画蓝/留白灰）
    try:
        annotated_filename = f"annotated_{db_analysis.image_id}.jpg"
        annotated_path = os.path.join(ANNOTATED_DIR, annotated_filename)
        
        # 获取原始图片路径
        original_path = get_full_file_path(db_analysis.filepath, PROJECT_ROOT) if db_analysis.filepath else None
        if original_path and os.path.exists(original_path):
            draw_all_regions_image(original_path, regions_dict, annotated_path, width, height)
            db_analysis.annotated_image_path = f"data/annotated/{annotated_filename}"
            db.commit()
    except Exception as e:
        logger.error("生成标注图失败: %s", e)

    return {
        "success": True,
        "message": "标注已保存",
        "data": {
            "id": db_analysis.id,
            "image_id": db_analysis.image_id,
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent,
            "region_count": len(inscription_list) + len(painting_list),
            "annotated_image_url": get_static_url(f"annotated/annotated_{db_analysis.image_id}.jpg") if db_analysis.annotated_image_path else None,
            "is_manual_annotated": True
        }
    }
