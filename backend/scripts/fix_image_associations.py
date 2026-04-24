"""
修复已有数据的图像-文本关联
用于处理已入库但关联未建立的数据
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.modules.pantianshou_composition.models import TextChunk, ExtractedImage, PdfBook
from app.modules.pantianshou_composition.image_matcher import ImageMatcher

def fix_associations():
    """修复所有书籍的图像-文本关联"""
    # 创建数据库连接
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # 获取所有已完成的书籍
        books = db.query(PdfBook).filter(PdfBook.status == 'completed').all()
        print(f"找到 {len(books)} 本已完成的书籍")
        
        matcher = ImageMatcher()
        total_fixed = 0
        
        for book in books:
            print(f"\n处理书籍: {book.title or book.file_name} ({book.id})")
            
            # 获取该书籍的所有文本块和图像
            chunks = db.query(TextChunk).filter(TextChunk.book_id == book.id).all()
            images = db.query(ExtractedImage).filter(ExtractedImage.book_id == book.id).all()
            
            print(f"  文本块: {len(chunks)}, 图像: {len(images)}")
            
            if not chunks or not images:
                print("  跳过: 没有足够的数据")
                continue
            
            # 转换为字典
            chunk_dicts = [
                {
                    "id": c.id,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "content": c.content,
                }
                for c in chunks
            ]
            
            img_dicts = [
                {
                    "id": i.id,
                    "page": i.page,
                    "figure_id": i.figure_id,
                    "bbox": i.bbox,
                }
                for i in images
            ]
            
            # 构建关联
            img_to_chunks, chunk_to_images = matcher.build_associations(img_dicts, chunk_dicts)
            
            # 更新数据库
            fixed_count = 0
            for chunk_id, img_ids in chunk_to_images.items():
                chunk = db.query(TextChunk).filter(TextChunk.id == chunk_id).first()
                if chunk:
                    old_images = chunk.associated_images or []
                    if set(old_images) != set(img_ids):
                        chunk.associated_images = img_ids
                        fixed_count += 1
            
            for img_id, chunk_ids in img_to_chunks.items():
                img = db.query(ExtractedImage).filter(ExtractedImage.id == img_id).first()
                if img:
                    old_chunks = img.associated_chunks or []
                    if set(old_chunks) != set(chunk_ids):
                        img.associated_chunks = chunk_ids
            
            db.commit()
            total_fixed += fixed_count
            print(f"  修复了 {fixed_count} 个文本块的关联")
            print(f"  图像->文本块映射: {len(img_to_chunks)}")
            print(f"  文本块->图像映射: {len(chunk_to_images)}")
        
        print(f"\n总共修复了 {total_fixed} 个文本块")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        db.close()

if __name__ == "__main__":
    fix_associations()
