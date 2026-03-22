from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw

from app.core.database import get_db
from app.models.tubi_analysis import TubiAnalysis
from app.services.siliconflow_service import (
    analyze_image_regions,
    calculate_area_stats,
    generate_heatmap_data
)
from app.services.inscription_position_analyzer import analyze_inscription_position

router = APIRouter(prefix="/tubi", tags=["题跋分析"])

UPLOAD_DIR = "data/uploads"
ANNOTATED_DIR = "data/annotated"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(ANNOTATED_DIR, exist_ok=True)


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
    period: Optional[str] = None
    notes: Optional[str] = None
    analysis_note: Optional[str] = None
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
    from PIL import Image
    
    # 打开原图
    with Image.open(original_path) as img:
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
            if "points" in region and isinstance(region["points"], list):
                points = region["points"]
                if len(points) >= 3:
                    poly_points = [(int(p["x"]), int(p["y"])) for p in points]
                    # 填充
                    draw.polygon(poly_points, fill=fill_color)
                    # 边框
                    draw.polygon(poly_points, outline=border_color, width=2)
            elif "x1" in region:
                x1, y1 = int(region["x1"]), int(region["y1"])
                x2, y2 = int(region["x2"]), int(region["y2"])
                draw.rectangle([x1, y1, x2, y2], fill=fill_color)
                draw.rectangle([x1, y1, x2, y2], outline=border_color, width=2)
        
        # 按优先级绘制：留白 -> 绘画 -> 题跋（题跋在最上层）
        for region in regions.get("blank_regions", []):
            draw_region_fast(region, colors['blank'], border_colors['blank'])
        
        for region in regions.get("painting_regions", []):
            draw_region_fast(region, colors['painting'], border_colors['painting'])
        
        for region in regions.get("inscription_regions", []):
            draw_region_fast(region, colors['inscription'], border_colors['inscription'])
        
        # 合并图层
        result = Image.alpha_composite(img, overlay)
        
        # 转换为RGB保存（减小文件大小）
        if result.mode == 'RGBA':
            result = result.convert('RGB')
        
        # 使用优化参数保存
        result.save(output_path, 'JPEG', quality=85, optimize=True)
        return output_path


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
    if file.content_type not in ["image/jpeg", "image/png", "image/bmp"]:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG、BMP 格式")

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{file_id}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        with Image.open(filepath) as img:
            width, height = img.size
    except Exception:
        width, height = 0, 0

    # 保存到数据库
    db_analysis = TubiAnalysis(
        image_id=file_id,
        filename=file.filename,
        filepath=filepath,
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

    return {
        "success": True,
        "data": {
            "id": file_id,
            "filename": file.filename,
            "title": title,
            "artist": artist,
            "url": f"/static/uploads/{filename}",
            "width": width,
            "height": height
        }
    }


@router.post("/upload-multiple")
async def upload_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    uploaded = []
    for file in files:
        if file.content_type in ["image/jpeg", "image/png", "image/bmp"]:
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
            filename = f"{file_id}{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            content = await file.read()
            with open(filepath, "wb") as f:
                f.write(content)

            try:
                with Image.open(filepath) as img:
                    width, height = img.size
            except Exception:
                width, height = 0, 0

            # 保存到数据库
            db_analysis = TubiAnalysis(
                image_id=file_id,
                filename=file.filename,
                filepath=filepath,
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
                "url": f"/static/uploads/{filename}",
                "width": width,
                "height": height
            })

    return {
        "success": True,
        "data": uploaded
    }


@router.post("/auto-analyze/{image_id}")
async def auto_analyze(image_id: str, db: Session = Depends(get_db)):
    """
    使用 AI 自动分析图像中的题跋、绘画、留白区域
    """
    # 从数据库获取
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    filepath = db_analysis.filepath
    width = db_analysis.image_width or 0
    height = db_analysis.image_height or 0

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="图像文件不存在")

    if width == 0 or height == 0:
        try:
            with Image.open(filepath) as img:
                width, height = img.size
                db_analysis.image_width = width
                db_analysis.image_height = height
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无法读取图像: {str(e)}")

    result = analyze_image_regions(filepath, width, height)

    if not result["success"]:
        db_analysis.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail=result.get("error", "分析失败"))

    regions = result["regions"]
    area_stats = calculate_area_stats(regions, width, height)
    heatmap = generate_heatmap_data(regions, width, height)
    
    # 分析题跋位置
    position_analysis = analyze_inscription_position(regions, width, height)

    # 生成标注图片
    annotated_filename = f"annotated_{image_id}.jpg"
    annotated_path = os.path.join(ANNOTATED_DIR, annotated_filename)
    draw_annotated_image(filepath, regions, annotated_path)

    # 更新数据库
    db_analysis.regions = regions
    db_analysis.inscription_percent = area_stats["inscription_percent"]
    db_analysis.painting_percent = area_stats["painting_percent"]
    db_analysis.blank_percent = area_stats["blank_percent"]
    db_analysis.heatmap_data = heatmap
    db_analysis.position_analysis = position_analysis
    db_analysis.analysis_note = result.get("analysis_note", "")
    db_analysis.annotated_image_path = annotated_path
    db_analysis.status = "analyzed"
    db.commit()
    db.refresh(db_analysis)

    return {
        "success": True,
        "data": {
            "image_id": image_id,
            "filename": db_analysis.filename,
            "title": db_analysis.title,
            "artist": db_analysis.artist,
            "image_width": width,
            "image_height": height,
            "regions": regions,
            "area_stats": area_stats,
            "heatmap": heatmap,
            "position_analysis": position_analysis,
            "analysis_note": result.get("analysis_note", ""),
            "annotated_image_url": f"/static/annotated/{annotated_filename}"
        }
    }


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

    # 构建图片URL
    if db_analysis.filepath:
        actual_filename = os.path.basename(db_analysis.filepath)
        image_url = f"/static/uploads/{actual_filename}"
    elif db_analysis.filename:
        image_url = f"/static/uploads/{db_analysis.filename}"
    else:
        image_url = None

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
            "status": db_analysis.status,
            "created_at": db_analysis.created_at.isoformat() if db_analysis.created_at else None,
            "annotated_image_url": f"/static/annotated/annotated_{image_id}.jpg" if db_analysis.annotated_image_path else None
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
            "inscription_percent": db_analysis.inscription_percent,
            "painting_percent": db_analysis.painting_percent,
            "blank_percent": db_analysis.blank_percent
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
    if request.period is not None:
        db_analysis.period = request.period
    if request.notes is not None:
        db_analysis.notes = request.notes
    if request.analysis_note is not None:
        db_analysis.analysis_note = request.analysis_note
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
        # 从 filepath 提取文件名
        if analysis.filepath:
            actual_filename = os.path.basename(analysis.filepath)
            # 检查文件是否实际存在
            file_exists = os.path.exists(analysis.filepath)
        elif analysis.filename:
            actual_filename = analysis.filename
            # 检查文件是否存在于 uploads 目录
            file_exists = os.path.exists(os.path.join(UPLOAD_DIR, analysis.filename))
        else:
            actual_filename = None
            file_exists = False
        
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
            "position_analysis": analysis.position_analysis,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "url": f"/static/uploads/{actual_filename}" if actual_filename and file_exists else None,
            "annotated_image_url": f"/static/annotated/annotated_{analysis.image_id}.jpg" if analysis.annotated_image_path and os.path.exists(analysis.annotated_image_path) else None,
            "analysis_note": analysis.analysis_note
        })

    return {
        "success": True,
        "data": results,
        "total": db.query(TubiAnalysis).count()
    }


@router.delete("/image/{image_id}")
async def delete_image(image_id: str, db: Session = Depends(get_db)):
    db_analysis = db.query(TubiAnalysis).filter(TubiAnalysis.image_id == image_id).first()
    if not db_analysis:
        raise HTTPException(status_code=404, detail="图像不存在")

    # 删除文件
    if db_analysis.filepath and os.path.exists(db_analysis.filepath):
        os.remove(db_analysis.filepath)
    if db_analysis.annotated_image_path and os.path.exists(db_analysis.annotated_image_path):
        os.remove(db_analysis.annotated_image_path)

    # 删除数据库记录
    db.delete(db_analysis)
    db.commit()

    return {
        "success": True,
        "message": "图像已删除"
    }


@router.delete("/clear-all")
async def clear_all_analyses(db: Session = Depends(get_db)):
    """清空所有分析数据"""
    try:
        # 获取所有记录
        all_analyses = db.query(TubiAnalysis).all()
        
        # 删除所有关联文件
        for analysis in all_analyses:
            if analysis.filepath and os.path.exists(analysis.filepath):
                try:
                    os.remove(analysis.filepath)
                except Exception as e:
                    print(f"删除文件失败 {analysis.filepath}: {e}")
            
            if analysis.annotated_image_path and os.path.exists(analysis.annotated_image_path):
                try:
                    os.remove(analysis.annotated_image_path)
                except Exception as e:
                    print(f"删除标注图失败 {analysis.annotated_image_path}: {e}")
        
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
