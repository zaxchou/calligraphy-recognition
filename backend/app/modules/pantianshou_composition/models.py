"""
知识库数据模型
定义 PDF 书籍、任务、文本块、图像的 SQLAlchemy 模型
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def generate_uuid() -> str:
    """生成 UUID 字符串"""
    return str(uuid.uuid4())


class PdfBook(Base):
    """PDF 书籍元数据表"""
    __tablename__ = "pdf_books"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    stored_url = Column(String(500), nullable=False)
    title = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    total_pages = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending/processing/completed/failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    tasks = relationship("KnowledgeTask", back_populates="book", cascade="all, delete-orphan")
    chunks = relationship("TextChunk", back_populates="book", cascade="all, delete-orphan")
    images = relationship("ExtractedImage", back_populates="book", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_pdf_books_status", "status"),
        Index("idx_pdf_books_created", "created_at"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "file_name": self.file_name,
            "stored_path": self.stored_path,
            "stored_url": self.stored_url,
            "title": self.title,
            "author": self.author,
            "total_pages": self.total_pages,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class KnowledgeTask(Base):
    """知识入库任务表"""
    __tablename__ = "knowledge_tasks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(String(36), ForeignKey("pdf_books.id"), nullable=False)
    task_type = Column(String(50), nullable=False)  # text_extract/image_extract/full_process
    status = Column(String(20), default="queued")  # queued/processing/completed/failed/cancelled
    progress = Column(Integer, default=0)  # 0-100
    stage = Column(String(100), nullable=True)  # 当前处理阶段描述
    message = Column(Text, nullable=True)  # 状态消息
    result = Column(JSON, nullable=True)  # 处理结果
    error_message = Column(Text, nullable=True)  # 错误信息
    celery_task_id = Column(String(100), nullable=True)  # Celery 任务ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    book = relationship("PdfBook", back_populates="tasks")
    
    __table_args__ = (
        Index("idx_knowledge_tasks_book", "book_id"),
        Index("idx_knowledge_tasks_status", "status"),
        Index("idx_knowledge_tasks_created", "created_at"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "message": self.message,
            "result": self.result,
            "error_message": self.error_message,
            "celery_task_id": self.celery_task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TextChunk(Base):
    """文本块表"""
    __tablename__ = "text_chunks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(String(36), ForeignKey("pdf_books.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 块序号
    chapter_title = Column(String(255), nullable=True)  # 章节标题
    page_start = Column(Integer, nullable=True)  # 起始页码
    page_end = Column(Integer, nullable=True)  # 结束页码
    content = Column(Text, nullable=False)  # 文本内容
    content_hash = Column(String(64), nullable=False, index=True)  # 内容 MD5 哈希，用于去重
    vector_id = Column(String(100), nullable=True, index=True)  # Qdrant point ID
    associated_images = Column(JSON, default=list)  # 关联图像ID列表 ["image_id1", ...]
    bbox = Column(JSON, nullable=True)  # 合并后的边界框 {x0, y0, x1, y1}
    meta_data = Column(JSON, nullable=True)  # 额外元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联关系
    book = relationship("PdfBook", back_populates="chunks")
    
    __table_args__ = (
        Index("idx_text_chunks_book", "book_id"),
        Index("idx_text_chunks_hash", "content_hash"),
        Index("idx_text_chunks_vector", "vector_id"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "chunk_index": self.chunk_index,
            "chapter_title": self.chapter_title,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "content": self.content,
            "content_hash": self.content_hash,
            "vector_id": self.vector_id,
            "associated_images": self.associated_images or [],
            "bbox": self.bbox,
            "meta_data": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExtractedImage(Base):
    """图像表"""
    __tablename__ = "extracted_images"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(String(36), ForeignKey("pdf_books.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    stored_url = Column(String(500), nullable=False)
    page = Column(Integer, nullable=True)  # 所在页码
    figure_id = Column(String(100), nullable=True)  # 图号（如"图五"）
    caption = Column(Text, nullable=True)  # 图注文本（如"图三七 清代 朱耷《菊花》"）
    bbox = Column(JSON, nullable=True)  # 边界框 {x0, y0, x1, y1}
    image_hash = Column(String(64), nullable=True, index=True)  # 图像感知哈希，用于去重
    vector_id = Column(String(100), nullable=True, index=True)  # Qdrant point ID
    associated_chunks = Column(JSON, default=list)  # 关联文本块ID列表
    meta_data = Column(JSON, nullable=True)  # 额外元数据
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系
    book = relationship("PdfBook", back_populates="images")

    __table_args__ = (
        Index("idx_extracted_images_book", "book_id"),
        Index("idx_extracted_images_hash", "image_hash"),
        Index("idx_extracted_images_vector", "vector_id"),
        Index("idx_extracted_images_page", "page"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "book_id": self.book_id,
            "file_name": self.file_name,
            "stored_path": self.stored_path,
            "stored_url": self.stored_url,
            "page": self.page,
            "figure_id": self.figure_id,
            "caption": self.caption,
            "bbox": self.bbox,
            "image_hash": self.image_hash,
            "vector_id": self.vector_id,
            "associated_chunks": self.associated_chunks or [],
            "meta_data": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchHistory(Base):
    """搜索历史表"""
    __tablename__ = "search_history"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    query = Column(String(500), nullable=False)  # 搜索关键词
    query_type = Column(String(20), default="text")  # text/image
    filters = Column(JSON, nullable=True)  # 过滤条件
    result_count = Column(Integer, default=0)  # 结果数量
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_search_history_created", "created_at"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "query": self.query,
            "query_type": self.query_type,
            "filters": self.filters,
            "result_count": self.result_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SummaryCache(Base):
    """AI 摘要缓存表
    
    缓存 key: query 归一化（去空格转小写）
    新书上架/重新入库时清除全部缓存
    """
    __tablename__ = "summary_cache"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    query_key = Column(String(500), nullable=False, unique=True)  # 归一化后的查询
    query_original = Column(String(500), nullable=False)  # 原始查询
    answer = Column(Text, nullable=False)  # AI 回答
    confidence = Column(Integer, default=0)  # confidence * 100（存整数）
    sources = Column(JSON, default=list)  # 来源列表
    extra_data = Column(JSON, default=dict)  # 额外数据：key_points, related_concepts 等
    created_at = Column(DateTime, default=datetime.utcnow)
    hit_count = Column(Integer, default=0)  # 缓存命中次数
    
    __table_args__ = (
        Index("idx_summary_cache_key", "query_key"),
    )


# 保留原有模型用于兼容性
class CompositionJob(Base):
    """构图分析任务表"""
    __tablename__ = "composition_jobs"

    id = Column(String(64), primary_key=True)
    status = Column(String(32), default="pending")
    progress = Column(Integer, default=0)
    stage = Column(String(64), nullable=True)
    stage_text = Column(String(64), nullable=True)
    message = Column(String(255), nullable=True)
    eta_seconds = Column(Integer, default=0)
    eta_confidence = Column(Integer, default=0)
    queue_eta_seconds = Column(Integer, default=0)
    celery_task_id = Column(String(128), nullable=True)
    upload_path = Column(String(512), nullable=True)
    original_url = Column(String(512), nullable=True)
    report_json_path = Column(String(512), nullable=True)
    pdf_path = Column(String(512), nullable=True)
    overlay_heatmap_url = Column(String(512), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    

class CompositionFeedback(Base):
    """构图反馈表（保留兼容）"""
    __tablename__ = "composition_feedback"
    
    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), nullable=False)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# 数据库初始化函数
def init_knowledge_tables(engine):
    """初始化知识库相关表"""
    Base.metadata.create_all(bind=engine, tables=[
        PdfBook.__table__,
        KnowledgeTask.__table__,
        TextChunk.__table__,
        ExtractedImage.__table__,
        SearchHistory.__table__,
        SummaryCache.__table__,
    ])
