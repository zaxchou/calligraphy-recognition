"""
画家专属文献管理 API
每个画家可上传学术论文和专著 PDF，支持在线阅读和 RAG 问答。
"""

import os
import uuid
import json
import logging
import threading
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from .database import get_db
from .models import PdfBook, KnowledgeTask, TextChunk
from .knowledge_ingest_v2 import process_pdf_file_sync
from .knowledge_storage import save_book_upload

from app.core.auth import require_editor
from app.models.user import User

router = APIRouter(prefix="/artists/{artist_id}/literature")
logger = logging.getLogger(__name__)


# ============ Pydantic 模型 ============

class LiteratureResponse(BaseModel):
    id: str
    title: Optional[str] = None
    author: Optional[str] = None
    journal: Optional[str] = None
    publish_year: Optional[int] = None
    doi: Optional[str] = None
    status: str
    total_pages: Optional[int] = None
    chunk_count: int = 0
    created_at: Optional[str] = None


class LiteratureDetailResponse(LiteratureResponse):
    outline: Optional[list] = None
    file_name: str = ""
    stored_url: str = ""
    document_type: str = "literature"
    full_md_length: int = 0


class MetadataUpdateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    journal: Optional[str] = None
    publish_year: Optional[int] = None
    doi: Optional[str] = None


# ============ 端点 ============

@router.post("/upload")
async def upload_literature(
    artist_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publish_year: Optional[int] = Form(None),
    doi: Optional[str] = Form(None),
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    """上传文献 PDF，关联到指定画家"""
    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存文件
    try:
        file_path, file_url = save_book_upload(file, prefix="literature")
    except Exception as e:
        raise HTTPException(500, f"文件保存失败: {str(e)}")

    # 创建 book 记录
    book_id = str(uuid.uuid4())
    book = PdfBook(
        id=book_id,
        file_name=file.filename,
        stored_path=file_path,
        stored_url=file_url,
        artist_id=artist_id,
        document_type='literature',
        title=title,
        journal=journal,
        publish_year=publish_year,
        doi=doi,
        status='processing',
    )
    db.add(book)

    # 创建 task 记录
    task_id = str(uuid.uuid4())
    task = KnowledgeTask(
        id=task_id,
        book_id=book_id,
        task_type='pdf_ingest',
        status='queued',
        progress=0,
        stage='queued',
    )
    db.add(task)
    db.commit()

    # 后台处理（含 LLM 元数据提取）
    def _process():
        try:
            process_pdf_file_sync(
                pdf_path=file_path,
                task_id=task_id,
                book_id=book_id,
                artist_id=artist_id,
                document_type='literature',
            )
            # LLM 元数据提取（仅当用户未提供标题时）
            _try_extract_metadata(book_id)
        except Exception as e:
            logger.error(f"文献处理失败: {e}")

    threading.Thread(target=_process, daemon=True).start()

    return {"book_id": book_id, "task_id": task_id}


def _try_extract_metadata(book_id: str):
    """尝试用 LLM 提取元数据"""
    from .database import get_db as _get_db
    from .metadata_extractor import extract_metadata
    import asyncio

    db = next(_get_db())
    try:
        book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
        if not book or not book.full_md:
            return

        # 只在字段为空时提取
        needs_extract = not book.title or not book.author or not book.journal
        if not needs_extract:
            return

        meta = asyncio.run(extract_metadata(book.full_md))
        if not meta:
            return

        if not book.title and meta.get('title'):
            book.title = meta['title']
        if not book.author and meta.get('authors'):
            book.author = ', '.join(meta['authors']) if isinstance(meta['authors'], list) else str(meta['authors'])
        if not book.journal and meta.get('journal'):
            book.journal = meta['journal']
        if not book.publish_year and meta.get('publish_year'):
            book.publish_year = meta['publish_year']
        if not book.doi and meta.get('doi'):
            book.doi = meta['doi']
        db.commit()
    except Exception as e:
        logger.warning(f"元数据提取失败: {e}")
    finally:
        db.close()


@router.get("")
async def list_literature(
    artist_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取画家的文献列表"""
    query = db.query(PdfBook).filter(
        PdfBook.artist_id == artist_id,
        PdfBook.document_type == 'literature',
    )

    if keyword:
        query = query.filter(
            PdfBook.title.contains(keyword) | PdfBook.author.contains(keyword)
        )

    # 排序
    sort_map = {
        'created_at': PdfBook.created_at.desc(),
        'publish_year': PdfBook.publish_year.desc(),
        'title': PdfBook.title.asc(),
    }
    query = query.order_by(sort_map.get(sort_by, PdfBook.created_at.desc()))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    # 批量查 chunk_count
    book_ids = [b.id for b in items]
    chunk_counts = {}
    if book_ids:
        rows = db.query(TextChunk.book_id, func.count(TextChunk.id)).filter(
            TextChunk.book_id.in_(book_ids)
        ).group_by(TextChunk.book_id).all()
        chunk_counts = {r[0]: r[1] for r in rows}

    return {
        "items": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "journal": b.journal,
                "publish_year": b.publish_year,
                "doi": b.doi,
                "status": b.status,
                "total_pages": b.total_pages,
                "chunk_count": chunk_counts.get(b.id, 0),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{book_id}")
async def get_literature_detail(
    artist_id: int,
    book_id: str,
    db: Session = Depends(get_db),
):
    """获取单篇文献详情"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
        PdfBook.document_type == 'literature',
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    chunk_count = db.query(func.count(TextChunk.id)).filter(
        TextChunk.book_id == book_id
    ).scalar()

    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "journal": book.journal,
        "publish_year": book.publish_year,
        "doi": book.doi,
        "status": book.status,
        "total_pages": book.total_pages,
        "chunk_count": chunk_count,
        "outline": book.outline,
        "file_name": book.file_name,
        "stored_url": book.stored_url,
        "document_type": book.document_type,
        "full_md_length": len(book.full_md) if book.full_md else 0,
        "created_at": book.created_at.isoformat() if book.created_at else None,
    }


@router.delete("/{book_id}")
async def delete_literature(
    artist_id: int,
    book_id: str,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    """删除文献"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
        PdfBook.document_type == 'literature',
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    # 删除关联数据
    # Qdrant 向量（通过 vector_id）
    try:
        from . import qdrant_client
        chunks = db.query(TextChunk).filter(TextChunk.book_id == book_id).all()
        vector_ids = [c.vector_id for c in chunks if c.vector_id]
        if vector_ids:
            qdrant_client.delete_points(qdrant_client.KNOWLEDGE_TEXTS_COLLECTION, vector_ids)
    except Exception as e:
        logger.warning(f"删除 Qdrant 向量失败: {e}")

    # 删除文件
    if book.stored_path and os.path.exists(book.stored_path):
        try:
            os.remove(book.stored_path)
        except Exception as e:
            logger.warning(f"删除文件失败: {e}")

    # 删除数据库记录（cascade 会删 chunks/images/tasks）
    db.delete(book)
    db.commit()

    return {"message": "文献已删除"}


@router.patch("/{book_id}")
async def update_literature_metadata(
    artist_id: int,
    book_id: str,
    body: MetadataUpdateRequest,
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    """修改文献元数据"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
        PdfBook.document_type == 'literature',
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    if body.title is not None:
        book.title = body.title
    if body.author is not None:
        book.author = body.author
    if body.journal is not None:
        book.journal = body.journal
    if body.publish_year is not None:
        book.publish_year = body.publish_year
    if body.doi is not None:
        book.doi = body.doi

    db.commit()
    return {"message": "元数据已更新"}


@router.get("/{book_id}/chunks")
async def get_literature_chunks(
    artist_id: int,
    book_id: str,
    db: Session = Depends(get_db),
):
    """获取文献全文 chunks（供 Markdown 阅读）"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    chunks = db.query(TextChunk).filter(
        TextChunk.book_id == book_id
    ).order_by(TextChunk.chunk_index).all()

    return {
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "chapter_title": c.chapter_title,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "content": c.content,
            }
            for c in chunks
        ]
    }


@router.get("/{book_id}/pdf")
async def get_literature_pdf(
    artist_id: int,
    book_id: str,
    db: Session = Depends(get_db),
):
    """获取原 PDF 文件（供 PDF.js 渲染）"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    if not book.stored_path or not os.path.exists(book.stored_path):
        raise HTTPException(404, "PDF 文件不存在")

    return FileResponse(
        book.stored_path,
        media_type="application/pdf",
        filename=book.file_name,
    )
