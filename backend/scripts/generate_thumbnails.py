"""
批量生成缩略图脚本
为所有已有的上传图片生成缩略图
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.tubi_analysis import TubiAnalysis

UPLOAD_DIR = "data/uploads"
THUMBNAIL_DIR = "data/thumbnails"


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
        print(f"生成缩略图失败 {image_path}: {e}")
        return None


def generate_all_thumbnails():
    """为所有已有图片生成缩略图"""
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)
    
    db = SessionLocal()
    try:
        # 获取所有分析记录
        analyses = db.query(TubiAnalysis).all()
        print(f"共有 {len(analyses)} 条记录需要处理")
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for analysis in analyses:
            image_id = analysis.image_id
            
            # 检查原图是否存在
            if not analysis.filepath or not os.path.exists(analysis.filepath):
                print(f"跳过 {image_id}: 原图不存在")
                skip_count += 1
                continue
            
            # 生成缩略图文件名
            thumbnail_filename = f"{image_id}_thumb.jpg"
            thumbnail_path = os.path.join(THUMBNAIL_DIR, thumbnail_filename)
            
            # 如果缩略图已存在且数据库已记录，跳过
            if analysis.thumbnail_path and os.path.exists(analysis.thumbnail_path):
                print(f"跳过 {image_id}: 缩略图已存在")
                skip_count += 1
                continue
            
            # 生成缩略图
            result = create_thumbnail(analysis.filepath, thumbnail_path)
            
            if result:
                # 更新数据库
                analysis.thumbnail_path = thumbnail_path
                db.commit()
                print(f"成功 {image_id}: 生成缩略图 {thumbnail_path}")
                success_count += 1
            else:
                print(f"失败 {image_id}: 无法生成缩略图")
                error_count += 1
        
        print(f"\n处理完成:")
        print(f"  成功: {success_count}")
        print(f"  跳过: {skip_count}")
        print(f"  失败: {error_count}")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("开始批量生成缩略图...")
    generate_all_thumbnails()
    print("完成!")
