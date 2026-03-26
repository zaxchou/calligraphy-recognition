from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw

import redis
from app.core.config import get_settings
from app.core.database import get_db
from app.core.path_utils import get_static_url, get_full_file_path, normalize_path
from app.models.tubi_analysis import TubiAnalysis

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter()

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
from app.services.siliconflow_service import (
    analyze_image_regions,
    calculate_area_stats,
    generate_heatmap_data
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
    """
    try:
        with Image.open(image_path) as img:
            # 转换为RGB模式（处理RGBA等模式）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 计算缩略图尺寸，保持宽高比
            width, height = img.size
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            
            # 生成缩略图
            img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 保存缩略图
            img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
            return thumbnail_path
    except Exception as e:
        logger.error("生成缩略图失败: %s", e)
        return None


class RegionData(BaseModel):
    type: str
    x1: float
    y1: float
    x2: float
    y2: float


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
    inscription_percent: Optional[float] = None
    painting_percent: Optional[float] = None
    blank_percent: Optional[float] = None


def draw_annotated_image(original_path: str, regions: dict, output_path: str):
    """
    绘制区域标注图片（优化版本）
    题跋区域 - 红色填充+边框
    绘画区域 - 绿色填充+边框
    留白区域 - 蓝色填充+边框
    支持多边形和矩形两种格式
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
            
            # 定义颜色和透明度
            colors = {
                'inscription': (255, 0, 0, 60),      # 红色半透明
                'painting': (0, 255, 0, 60),         # 绿色半透明
                'blank': (0, 0, 255, 60)             # 蓝色半透明
            }
            border_colors = {
                'inscription': (255, 0, 0, 200),
                'painting': (0, 255, 0, 200),
                'blank': (0, 0, 255, 200)
            }
            
            def draw_region_fast(region, fill_color, border_color):
                """快速绘制单个区域"""
                try:
                    if "points" in region and isinstance(region["points"], list):
                        points = region["points"]
                        if len(points) >= 3:
                            # 调整坐标以匹配调整后的图片大小
                            scale_x = new_width / width if 'new_width' in locals() else 1
                            scale_y = new_height / height if 'new_height' in locals() else 1
                            poly_points = [(int(p["x"] * scale_x), int(p["y"] * scale_y)) for p in points]
                            # 填充
                            draw.polygon(poly_points, fill=fill_color)
                            # 边框
                            draw.polygon(poly_points, outline=border_color, width=2)
                    elif "x1" in region:
                        # 调整坐标以匹配调整后的图片大小
                        scale_x = new_width / width if 'new_width' in locals() else 1
                        scale_y = new_height / height if 'new_height' in locals() else 1
                        x1, y1 = int(region["x1"] * scale_x), int(region["y1"] * scale_y)
                        x2, y2 = int(region["x2"] * scale_x), int(region["y2"] * scale_y)
                        draw.rectangle([x1, y1, x2, y2], fill=fill_color)
                        draw.rectangle([x1, y1, x2, y2], outline=border_color, width=2)
                except Exception as e:
                    logger.error("绘制区域时出错: %s", e)
            
            # 按优先级绘制：留白 -> 绘画 -> 题跋（题跋在最上层）
            # 限制区域数量，避免处理过多区域导致崩溃
            max_regions = 100  # 最多处理100个区域
            
            for region in regions.get("blank_regions", [])[:max_regions]:
                draw_region_fast(region, colors['blank'], border_colors['blank'])
            
            for region in regions.get("painting_regions", [])[:max_regions]:
                draw_region_fast(region, colors['painting'], border_colors['painting'])
            
            for region in regions.get("inscription_regions", [])[:max_regions]:
                draw_region_fast(region, colors['inscription'], border_colors['inscription'])
            
            # 合并图层
            result = Image.alpha_composite(img, overlay)
            
            # 转换为RGB保存（减小文件大小）
            if result.mode == 'RGBA':
                result = result.convert('RGB')
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用优化参数保存
            result.save(output_path, 'JPEG', quality=75, optimize=True)
            return output_path
    except Exception as e:
        logger.error("生成标注图片失败: %s", e)
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

        # 先限制读取大小，防止大文件 OOM
        MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
        content = await file.read(MAX_UPLOAD_SIZE + 1)
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
            
        with open(filepath, "wb") as f:
            f.write(content)

        try:
            with Image.open(filepath) as img:
                width, height = img.size
            logger.info("图像尺寸: %dx%d", width, height)
        except Exception as e:
            logger.error("读取图像尺寸失败: %s", e)
            width, height = 0, 0

        # 生成缩略图
        logger.info("生成缩略图...")
        create_thumbnail(filepath, thumbnail_path)

        # 保存到数据库
        logger.info("保存到数据库...")
        db_analysis = TubiAnalysis(
            image_id=file_id,
            filename=file.filename,
            filepath=normalize_path(filepath),
            thumbnail_path=normalize_path(thumbnail_path) if thumbnail_path else None,
            title=title,
            artist=artist,
            year=year,
            period=period,
            notes=notes,
            image_width=width,
            image_height=height,
            status="uploaded"
        )
        db.add(db_analysis)
        db.commit()
        db.refresh(db_analysis)

        logger.info("上传成功: %s", file_id)
        return {
            "success": True,
            "data": {
                "id": file_id,
                "filename": file.filename,
                "title": title,
                "artist": artist,
                "url": get_static_url(f"uploads/{filename}"),
                "thumbnail_url": get_static_url(f"thumbnails/{thumbnail_filename}"),
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

            # 先限制读取大小，防止大文件 OOM
            MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
            content = await file.read(MAX_UPLOAD_SIZE + 1)
            if len(content) > MAX_UPLOAD_SIZE:
                failed.append({
                    "filename": file.filename,
                    "error": "文件大小超过50MB限制"
                })
                continue
                
            with open(filepath, "wb") as f:
                f.write(content)

            try:
                with Image.open(filepath) as img:
                    width, height = img.size
            except Exception as e:
                logger.error("读取图像尺寸失败: %s", e)
                width, height = 0, 0

            # 生成缩略图
            try:
                create_thumbnail(filepath, thumbnail_path)
            except Exception as e:
                logger.error("生成缩略图失败: %s", e)

            # 保存到数据库 - 使用标准化路径
            try:
                db_analysis = TubiAnalysis(
                    image_id=file_id,
                    filename=file.filename,
                    filepath=normalize_path(filepath),
                    thumbnail_path=normalize_path(thumbnail_path) if thumbnail_path else None,
                    image_width=width,
                    image_height=height,
                    status="uploaded"
                )
                db.add(db_analysis)
                db.commit()
                db.refresh(db_analysis)

                uploaded.append({
                    "id": file_id,
                    "filename": file.filename,
                    "url": get_static_url(f"uploads/{filename}"),
                    "thumbnail_url": get_static_url(f"thumbnails/{thumbnail_filename}") if thumbnail_path else None,
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
    """
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    if db_analysis.status in ["queued", "analyzing"]:
        return JSONResponse(
            status_code=202,
            content={"success": True, "data": {"id": image_id, "status": db_analysis.status}}
        )

    db_analysis.status = "queued"
    db.commit()

    job = db.query(TubiJob).filter(TubiJob.image_id == image_id).first()
    if job:
        job.status = "queued"
        job.last_error = None
    else:
        job = TubiJob(image_id=image_id, status="queued")
        db.add(job)
    db.commit()

    try:
        conn = _get_redis()
        conn.lpush(_QUEUE_KEY_PENDING, image_id)
    except Exception:
        pass

    return JSONResponse(
        status_code=202,
        content={"success": True, "data": {"id": image_id, "status": "queued"}}
    )


@router.post("/analyze")
async def analyze_regions(request: AnalysisRequest, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == request.image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    total_area = (request.image_width or 1) * (request.image_height or 1)
    inscription_area = 0.0
    painting_area = 0.0
    blank_area = 0.0

    for region in request.regions:
        area = (region.x2 - region.x1) * (region.y2 - region.y1)
        if region.type == "inscription":
            inscription_area += area
        elif region.type == "painting":
            painting_area += area
        elif region.type == "blank":
            blank_area += area

    inscription_percent = (inscription_area / total_area * 100) if total_area > 0 else 0
    painting_percent = (painting_area / total_area * 100) if total_area > 0 else 0
    blank_percent = (blank_area / total_area * 100) if total_area > 0 else 0

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
        thumbnail_path_local = get_full_file_path(db_analysis.thumbnail_path, "")
        if os.path.exists(thumbnail_path_local):
            thumbnail_filename = os.path.basename(db_analysis.thumbnail_path.replace('/', os.sep))
            thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
    elif image_url:
        thumbnail_url = image_url

    return {
        "success": True,
        "data": {
            "id": db_analysis.image_id,
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
            "position_analysis": db_analysis.position_analysis,
            "analysis_note": db_analysis.analysis_note,
            "inscription_content": db_analysis.inscription_content,
            "status": db_analysis.status,
            "created_at": db_analysis.created_at.isoformat() if db_analysis.created_at else None,
            "annotated_image_url": get_static_url(f"annotated/annotated_{image_id}.jpg") if db_analysis.annotated_image_path else None
        }
    }


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

    if status != "queued":
        return {
            "success": True,
            "data": {
                "id": image_id,
                "status": status,
                "position": 0,
                "pending_count": 0,
                "processing_count": 0,
                "estimated_wait_seconds": 0
            }
        }

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
                "estimated_wait_seconds": None
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
    estimated_wait_seconds = before_count * avg_seconds_per_job

    return {
        "success": True,
        "data": {
            "id": image_id,
            "status": status,
            "position": position,
            "pending_count": pending_count,
            "processing_count": processing_count,
            "estimated_wait_seconds": estimated_wait_seconds
        }
    }


@router.post("/year")
async def save_year_data(request: YearDataRequest, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == request.image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    db_analysis.year = request.year
    db_analysis.period = request.period
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
    if request.inscription_percent is not None:
        db_analysis.inscription_percent = request.inscription_percent
    if request.painting_percent is not None:
        db_analysis.painting_percent = request.painting_percent
    if request.blank_percent is not None:
        db_analysis.blank_percent = request.blank_percent

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
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent
        }
    }


@router.get("/results")
async def get_all_results(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有分析结果列表"""
    analyses = db.query(TubiAnalysis).order_by(TubiAnalysis.created_at.desc()).offset(skip).limit(limit).all()
    
    results = []
    for analysis in analyses:
        # 从 filepath 提取文件名 - 使用跨平台路径处理
        if analysis.filepath:
            actual_filename = os.path.basename(analysis.filepath.replace('/', os.sep))
            # 检查文件是否实际存在
            file_path_local = get_full_file_path(analysis.filepath, PROJECT_ROOT)
            file_exists = os.path.exists(file_path_local)
        elif analysis.filename:
            actual_filename = analysis.filename
            # 检查文件是否存在于 uploads 目录
            file_exists = os.path.exists(os.path.join(UPLOAD_DIR, analysis.filename))
        else:
            actual_filename = None
            file_exists = False

        # 处理缩略图
        thumbnail_url = None
        if analysis.thumbnail_path:
            thumbnail_path_local = get_full_file_path(analysis.thumbnail_path, PROJECT_ROOT)
            if os.path.exists(thumbnail_path_local):
                thumbnail_filename = os.path.basename(analysis.thumbnail_path.replace('/', os.sep))
                thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
        elif actual_filename and file_exists:
            # 如果没有缩略图，使用原图（但这样会影响性能）
            thumbnail_url = get_static_url(f"uploads/{actual_filename}")

        # 检查标注图片是否存在
        annotated_exists = False
        if analysis.annotated_image_path:
            annotated_path_local = get_full_file_path(analysis.annotated_image_path, PROJECT_ROOT)
            annotated_exists = os.path.exists(annotated_path_local)

        results.append({
            "id": analysis.image_id,
            "filename": analysis.filename,
            "title": analysis.title,
            "artist": analysis.artist,
            "year": analysis.year,
            "period": analysis.period,
            "image_width": analysis.image_width,
            "image_height": analysis.image_height,
            "inscription_percent": analysis.inscription_percent,
            "painting_percent": analysis.painting_percent,
            "blank_percent": analysis.blank_percent,
            "regions": analysis.regions,
            "position_analysis": analysis.position_analysis,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "url": get_static_url(f"uploads/{actual_filename}") if actual_filename and file_exists else None,
            "thumbnail_url": thumbnail_url,
            "annotated_image_url": get_static_url(f"annotated/annotated_{analysis.image_id}.jpg") if annotated_exists else None,
            "analysis_note": analysis.analysis_note,
            "inscription_content": analysis.inscription_content
        })

    return {
        "success": True,
        "data": results,
        "total": db.query(TubiAnalysis).count()
    }


@router.get("/search")
async def search_images(
    keyword: str = None,
    db: Session = Depends(get_db)
):
    """
    搜索画作

    - **keyword**: 搜索关键词（支持标题、作者、年代、备注模糊搜索）
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

        # 关键词搜索（标题、作者、年代、备注）
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            (TubiAnalysis.title.ilike(keyword_filter)) |
            (TubiAnalysis.artist.ilike(keyword_filter)) |
            (TubiAnalysis.period.ilike(keyword_filter)) |
            (TubiAnalysis.notes.ilike(keyword_filter)) |
            (TubiAnalysis.analysis_note.ilike(keyword_filter))
        )

        # 按创建时间倒序
        analyses = query.order_by(TubiAnalysis.created_at.desc()).all()

        # 组装结果
        results = []
        for analysis in analyses:
            # 从 filepath 提取文件名
            if analysis.filepath:
                actual_filename = os.path.basename(analysis.filepath.replace('/', os.sep))
                file_path_local = get_full_file_path(analysis.filepath, PROJECT_ROOT)
                file_exists = os.path.exists(file_path_local)
            elif analysis.filename:
                actual_filename = analysis.filename
                file_exists = os.path.exists(os.path.join(UPLOAD_DIR, analysis.filename))
            else:
                actual_filename = None
                file_exists = False

            # 处理缩略图
            thumbnail_url = None
            if analysis.thumbnail_path:
                thumbnail_path_local = get_full_file_path(analysis.thumbnail_path, PROJECT_ROOT)
                if os.path.exists(thumbnail_path_local):
                    thumbnail_filename = os.path.basename(analysis.thumbnail_path.replace('/', os.sep))
                    thumbnail_url = get_static_url(f"thumbnails/{thumbnail_filename}")
            elif actual_filename and file_exists:
                thumbnail_url = get_static_url(f"uploads/{actual_filename}")

            # 检查标注图片是否存在
            annotated_exists = False
            if analysis.annotated_image_path:
                annotated_path_local = get_full_file_path(analysis.annotated_image_path, PROJECT_ROOT)
                annotated_exists = os.path.exists(annotated_path_local)

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
                "position_analysis": analysis.position_analysis,
                "status": analysis.status,
                "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
                "url": get_static_url(f"uploads/{actual_filename}") if actual_filename and file_exists else None,
                "thumbnail_url": thumbnail_url,
                "annotated_image_url": get_static_url(f"annotated/annotated_{analysis.image_id}.jpg") if annotated_exists else None,
                "analysis_note": analysis.analysis_note,
                "inscription_content": analysis.inscription_content
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
        if os.path.exists(file_path_local):
            os.remove(file_path_local)
    if db_analysis.annotated_image_path:
        annotated_path_local = get_full_file_path(db_analysis.annotated_image_path, PROJECT_ROOT)
        if os.path.exists(annotated_path_local):
            os.remove(annotated_path_local)

    # 删除数据库记录
    db.delete(db_analysis)
    db.commit()

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
