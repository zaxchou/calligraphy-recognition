"""
新版知识入库核心流程
整合 PDF 解析、文本分块、向量化、图像提取、关联映射
"""

import os
import asyncio
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from .models import PdfBook, TextChunk, ExtractedImage, KnowledgeTask
from .database import get_db_context
from .pdf_processor import PdfProcessor, PdfContent
from .text_chunker import TextChunker, chunk_texts
from .embedding_service import EmbeddingService
from .context_prepend import prepend_context_for_chunk
from .image_matcher import ImageMatcher
from .task_manager import TaskManager
from . import qdrant_client

logger = logging.getLogger(__name__)


class KnowledgeIngestV2:
    """知识入库处理器 V2
    
    V2 改动（2026-03-29）：
    - 图片关联改为基于空间位置的精确匹配（bbox 距离）
    - 彻底移除"图X"编号全局搜索，避免后文重复引用
    - 图片记录新增 caption 字段（来自空间邻近的图注文本）
    - 传入 figure_first_page 用于区分首次定义和后续引用
    """
    
    def __init__(self, 
                 db: Optional[Session] = None,
                 chunk_strategy: str = "semantic",
                 chunk_size: int = 500):
        """
        初始化入库处理器
        
        Args:
            db: 数据库会话
            chunk_strategy: 分块策略
            chunk_size: 块大小
        """
        self.db = db
        self._local_db = db is None
        self.chunk_strategy = chunk_strategy
        self.chunk_size = chunk_size
        
        # 初始化服务
        self.embedding_service = EmbeddingService()
        self.image_matcher = ImageMatcher()
        self.chunker = TextChunker(strategy=chunk_strategy, chunk_size=chunk_size)
    
    def __enter__(self):
        if self._local_db:
            self.db_context = get_db_context()
            self.db = self.db_context.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._local_db:
            self.db_context.__exit__(exc_type, exc_val, exc_tb)
    
    async def process_pdf(self, 
                          pdf_path: str, 
                          task_id: Optional[str] = None,
                          book_id: Optional[str] = None) -> Dict[str, Any]:
        """
        处理 PDF 文件
        
        Args:
            pdf_path: PDF 文件路径
            task_id: 任务ID（可选）
            book_id: 书籍ID（可选，用于更新已有书籍）
        
        Returns:
            处理结果统计
        """
        # 创建或获取任务
        task_manager = TaskManager(self.db)
        
        if not book_id:
            # 创建新书籍记录
            book = self._create_book_record(pdf_path)
            book_id = book.id
        else:
            book = self.db.query(PdfBook).filter(PdfBook.id == book_id).first()
        
        if not task_id:
            task = task_manager.create_task(book_id, "full_process")
            task_id = task.id
        
        result = {
            "book_id": book_id,
            "task_id": task_id,
            "texts_extracted": 0,
            "texts_vectorized": 0,
            "images_extracted": 0,
            "images_vectorized": 0,
            "chunks_created": 0,
            "duplicates_skipped": 0,
        }
        
        try:
            # 1. PDF 解析（含 bbox、caption、figure_first_page）
            task_manager.update_progress(task_id, 10, "PDF解析", "正在解析PDF结构...")
            
            with PdfProcessor(pdf_path) as processor:
                pdf_content = processor.process_full()
            
            # 更新书籍元数据
            book.title = pdf_content.metadata.title
            book.author = pdf_content.metadata.author
            book.total_pages = pdf_content.metadata.total_pages
            self.db.commit()
            
            # 2. 文本分块
            task_manager.update_progress(task_id, 25, "文本分块", "正在分块处理文本...")
            
            text_dicts = [
                {
                    "content": t.content,
                    "page": t.page,
                    "chapter_title": t.chapter_title,
                    "bbox": t.bbox,
                }
                for t in pdf_content.texts
            ]
            
            chunks = chunk_texts(text_dicts, self.chunk_strategy, self.chunk_size)
            result["chunks_created"] = len(chunks)
            
            # 3. 文本去重与入库
            task_manager.update_progress(task_id, 40, "文本向量化", "正在生成文本向量...")
            
            texts_to_vectorize = []
            chunk_records = []
            book_info = {"title": book.title, "author": book.author} if book else {}
            
            for chunk in chunks:
                # 检查是否已存在
                existing = self.db.query(TextChunk).filter(
                    TextChunk.content_hash == chunk.compute_hash()
                ).first()
                
                if existing:
                    result["duplicates_skipped"] += 1
                    continue
                
                # Context Prepending: 为每个块预填文档上下文，提升向量质量
                enriched_text = prepend_context_for_chunk(
                    {"content": chunk.content, "chapter_title": chunk.chapter_title,
                     "page_start": chunk.page_start, "page_end": chunk.page_end},
                    book_info=book_info,
                )
                texts_to_vectorize.append(enriched_text)
                chunk_records.append(chunk)
            
            # 批量向量化
            if texts_to_vectorize:
                # 确保知识库 Qdrant 集合存在
                qdrant_client.ensure_knowledge_collections()
                
                embeddings = await self.embedding_service.embed_texts(texts_to_vectorize)
                
                # 保存到数据库和 Qdrant
                for idx, (chunk, emb_result) in enumerate(zip(chunk_records, embeddings)):
                    chunk_record = TextChunk(
                        book_id=book_id,
                        chunk_index=chunk.chunk_index,
                        chapter_title=chunk.chapter_title,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        content=chunk.content,
                        content_hash=chunk.compute_hash(),
                        associated_images=[],
                        bbox=chunk.bbox,
                    )
                    self.db.add(chunk_record)
                    self.db.flush()  # 获取ID
                    
                    # 保存向量到 Qdrant（ID 必须是合法 UUID）
                    import uuid as _uuid
                    vector_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{book_id}_{chunk_record.id}"))
                    qdrant_client.upsert_text_chunks([{
                        "id": vector_id,
                        "vector": emb_result.embedding,
                        "content": chunk.content,
                        "chapter": chunk.chapter_title,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "chunk_index": chunk.chunk_index,
                        "metadata": {"book_title": book.title}
                    }], book_id)
                    chunk_record.vector_id = vector_id
                    
                    result["texts_vectorized"] += 1
                    
                    if idx % 10 == 0:
                        progress = 40 + int((idx / len(chunk_records)) * 30)
                        task_manager.update_progress(
                            task_id, progress, "文本向量化", 
                            f"已处理 {idx}/{len(chunk_records)} 个文本块"
                        )
            
            # 4. 图像处理（含 bbox 和 caption）+ 图像向量化入库
            task_manager.update_progress(task_id, 70, "图像提取", "正在提取PDF图像...")
            
            # 创建图像存储目录
            image_dir = os.path.join(os.path.dirname(pdf_path), "images", book_id)
            os.makedirs(image_dir, exist_ok=True)
            
            # 确保 knowledge_images 集合存在
            qdrant_client.ensure_knowledge_collections()
            
            new_images = []  # (img_record, file_path) — 新提取的图像，待向量化
            
            for img in pdf_content.images:
                # 检查是否已存在
                img_hash = img.compute_hash()
                existing = self.db.query(ExtractedImage).filter(
                    ExtractedImage.image_hash == img_hash
                ).first()
                
                if existing:
                    result["duplicates_skipped"] += 1
                    continue
                
                # 保存图像
                file_path = img.save(image_dir)
                file_name = os.path.basename(file_path)
                
                # 创建记录（包含 caption）
                img_record = ExtractedImage(
                    book_id=book_id,
                    file_name=file_name,
                    stored_path=file_path,
                    stored_url=f"/api/v1/knowledge/images/{book_id}/{file_name}",
                    page=img.page,
                    figure_id=img.figure_id,
                    caption=img.caption,
                    bbox=img.bbox,
                    image_hash=img_hash,
                    associated_chunks=[],
                )
                self.db.add(img_record)
                result["images_extracted"] += 1
                new_images.append((img_record, file_path))
            
            self.db.commit()
            
            # 4b. 图像向量化并入库到 Qdrant knowledge_images 集合
            if new_images:
                task_manager.update_progress(task_id, 78, "图像向量化", 
                    f"正在向量化 {len(new_images)} 张图像...")
                
                import uuid as _uuid
                for idx, (img_record, file_path) in enumerate(new_images):
                    try:
                        # 生成图像 embedding（DashScope multimodal-embedding-v1）
                        emb_result = await self.embedding_service.embed_image(file_path)
                        
                        # 刷新获取 img_record.id（flush 后才有）
                        self.db.flush()
                        
                        # 生成 Qdrant point ID
                        vector_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, 
                            f"knowledge_img:{book_id}_{img_record.id}"))
                        
                        # 构建 payload
                        caption_text = img_record.caption or ""
                        figure_id = img_record.figure_id or f"img_p{img_record.page}"
                        
                        point = {
                            "id": vector_id,
                            "vector": emb_result.embedding,
                            "payload": {
                                "type": "pdf_extracted_image",
                                "source": "pdf_upload",
                                "book_id": book_id,
                                "book_title": book.title or "",
                                "figure_id": figure_id,
                                "caption": caption_text,
                                "page_number": img_record.page,
                                "image_path": img_record.stored_url,
                                "bbox": img_record.bbox or {},
                                "related_chunk_ids": [],
                                "metadata": {
                                    "book_title": book.title or "",
                                    "file_name": img_record.file_name,
                                },
                            },
                        }
                        
                        qdrant_client.upsert_images([point], book_id)
                        img_record.vector_id = vector_id
                        result["images_vectorized"] += 1
                        
                        logger.info("图像向量化成功: %s (page=%d, dim=%d, cache=%s)",
                                    figure_id, img_record.page, 
                                    emb_result.dimensions, emb_result.cache_hit)
                        
                    except Exception as e:
                        logger.warning("图像向量化失败: %s (page=%d): %s",
                                      img_record.figure_id, img_record.page, e)
                        # 向量化失败不影响整体流程，图像仍然保存在磁盘和 SQLite
                    
                    if idx % 3 == 0:
                        progress = 78 + int((idx / len(new_images)) * 10)
                        task_manager.update_progress(
                            task_id, progress, "图像向量化",
                            f"已处理 {idx}/{len(new_images)} 张图像"
                        )
                
                self.db.commit()
            
            # 5. 构建图像-文本关联（新算法：基于空间位置）
            task_manager.update_progress(task_id, 90, "关联映射", "正在构建图像文本关联...")
            
            await self._build_associations(book_id, pdf_content.figure_first_page)
            
            # 完成任务
            # 使 BM25 缓存失效，确保新入库数据可被搜索到
            from .hybrid_search import invalidate_bm25_cache
            invalidate_bm25_cache()
            
            task_manager.complete_task(task_id, result)
            
            result["status"] = "success"
            return result
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            task_manager.fail_task(task_id, error_msg)
            
            result["status"] = "failed"
            result["error"] = str(e)
            return result
    
    def _create_book_record(self, pdf_path: str) -> PdfBook:
        """创建书籍记录"""
        import uuid
        
        file_name = os.path.basename(pdf_path)
        stored_path = pdf_path
        stored_url = f"/api/v1/knowledge/pdfs/{file_name}"
        
        book = PdfBook(
            id=str(uuid.uuid4()),
            file_name=file_name,
            stored_path=stored_path,
            stored_url=stored_url,
            status="processing",
        )
        
        self.db.add(book)
        self.db.commit()
        self.db.refresh(book)
        
        return book
    
    async def _build_associations(self, book_id: str, figure_first_page: Dict[str, int]):
        """构建图像-文本关联（基于空间位置）"""
        # 获取书籍的所有文本块和图像
        chunks = self.db.query(TextChunk).filter(TextChunk.book_id == book_id).all()
        images = self.db.query(ExtractedImage).filter(ExtractedImage.book_id == book_id).all()
        
        if not chunks or not images:
            return
        
        # 转换为字典（包含 bbox）
        chunk_dicts = [
            {
                "id": c.id,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "content": c.content,
                "chunk_index": c.chunk_index,
                "bbox": c.bbox,
            }
            for c in chunks
        ]
        
        img_dicts = [
            {
                "id": i.id,
                "page": i.page,
                "figure_id": i.figure_id,
                "caption": i.caption,
                "bbox": i.bbox,
            }
            for i in images
        ]
        
        # 构建关联（传入 figure_first_page）
        img_to_chunks, chunk_to_images = self.image_matcher.build_associations(
            img_dicts, chunk_dicts, figure_first_page=figure_first_page
        )
        
        # 更新数据库
        for img_id, chunk_ids in img_to_chunks.items():
            img = self.db.query(ExtractedImage).filter(ExtractedImage.id == img_id).first()
            if img:
                img.associated_chunks = chunk_ids
        
        for chunk_id, img_ids in chunk_to_images.items():
            chunk = self.db.query(TextChunk).filter(TextChunk.id == chunk_id).first()
            if chunk:
                chunk.associated_images = img_ids
        
        self.db.commit()
        
        logger.info(
            f"书籍 {book_id} 关联完成: "
            f"{len(img_to_chunks)} 张图片关联了文本块, "
            f"{len(chunk_to_images)} 个文本块关联了图片"
        )


# 便捷函数
async def process_pdf_file(pdf_path: str, 
                           task_id: Optional[str] = None,
                           book_id: Optional[str] = None) -> Dict[str, Any]:
    """
    处理 PDF 文件的便捷函数
    
    Args:
        pdf_path: PDF 文件路径
        task_id: 任务ID
        book_id: 书籍ID
    
    Returns:
        处理结果
    """
    with KnowledgeIngestV2() as ingest:
        return await ingest.process_pdf(pdf_path, task_id, book_id)


def process_pdf_file_sync(pdf_path: str, 
                          task_id: Optional[str] = None,
                          book_id: Optional[str] = None) -> Dict[str, Any]:
    """同步版本"""
    return asyncio.run(process_pdf_file(pdf_path, task_id, book_id))


# 测试代码
if __name__ == "__main__":
    import sys
    
    async def test():
        if len(sys.argv) > 1:
            pdf_file = sys.argv[1]
            print(f"处理 PDF: {pdf_file}")
            
            result = await process_pdf_file(pdf_file)
            print(f"\n处理结果:")
            print(f"  书籍ID: {result.get('book_id')}")
            print(f"  任务ID: {result.get('task_id')}")
            print(f"  文本块: {result.get('chunks_created')}")
            print(f"  图像: {result.get('images_extracted')}")
            print(f"  去重跳过: {result.get('duplicates_skipped')}")
            print(f"  状态: {result.get('status')}")
            
            if result.get('error'):
                print(f"  错误: {result.get('error')}")
    
    asyncio.run(test())
