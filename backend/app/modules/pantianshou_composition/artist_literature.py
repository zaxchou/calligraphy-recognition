"""
画家专属文献管理 API
每个画家可上传学术论文和专著 PDF，支持在线阅读和 RAG 问答。
"""

import os
import uuid
import json
import logging
import threading
import time
from collections import deque
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from .database import get_db, SessionLocal
from .models import PdfBook, KnowledgeTask, TextChunk
from .knowledge_ingest_v2 import process_pdf_file_sync
from app.core.config import get_settings
from .knowledge_storage import save_book_upload

from app.core.auth import require_editor
from app.models.user import User

router = APIRouter(prefix="/artists/{artist_id}/literature")
logger = logging.getLogger(__name__)

# 并发限制：最多同时跑 2 个 MinerU 解析任务
_pdf_semaphore = threading.Semaphore(2)
_pdf_queue = []
_pdf_queue_lock = threading.Lock()
_pdf_worker_started = False


def _enqueue_pdf_task(fn):
    """将 PDF 处理任务加入队列，由唯一后台线程消费"""
    global _pdf_worker_started
    with _pdf_queue_lock:
        _pdf_queue.append(fn)
    if not _pdf_worker_started:
        _pdf_worker_started = True
        threading.Thread(target=_pdf_worker_loop, daemon=True).start()


def _pdf_worker_loop():
    """后台循环：逐任务消费，最多 2 个并发"""
    import time
    while True:
        task = None
        with _pdf_queue_lock:
            if _pdf_queue:
                task = _pdf_queue.pop(0)
        if task:
            with _pdf_semaphore:
                try:
                    task()
                except Exception as e:
                    logger.error(f"PDF 处理任务失败: {e}")
        else:
            time.sleep(1)


# 模块加载时恢复 DB 中 queued 的文献任务
def _recover_queued_tasks():
    """重启后把 DB 中 queued/failed 的文献任务重新入队"""
    try:
        from app.modules.pantianshou_composition.database import DB_PATH as _knowledge_db_path
        import sqlite3
        conn = sqlite3.connect(_knowledge_db_path)

        # 先重置 failed 为 queued（失败 1 次的重试）
        conn.execute(
            "UPDATE knowledge_tasks SET status='queued', stage='queued', progress=0 "
            "WHERE task_type='pdf_ingest' AND status='failed' "
            "AND EXISTS (SELECT 1 FROM pdf_books pb WHERE pb.id = book_id AND pb.document_type='literature')"
        )
        # 重置文献状态
        conn.execute(
            "UPDATE pdf_books SET status='processing' WHERE document_type='literature' AND status='failed'"
        )

        rows = conn.execute(
            "SELECT kt.id, kt.book_id, pb.stored_path, pb.artist_id FROM knowledge_tasks kt "
            "JOIN pdf_books pb ON kt.book_id = pb.id "
            "WHERE kt.task_type='pdf_ingest' AND kt.status='queued' "
            "AND pb.document_type='literature'"
        ).fetchall()
        conn.close()

        valid = 0
        missing = 0
        for task_id, book_id, pdf_path, aid in rows:
            if os.path.exists(pdf_path):
                _enqueue_pdf_task(lambda tid=task_id, bid=book_id, pp=pdf_path, ai=aid: _process_existing_pdf(tid, bid, pp, ai))
                valid += 1
            else:
                missing += 1
                logger.warning(f"PDF 文件不存在，跳过恢复: {pdf_path}")

        if valid:
            logger.info(f"恢复 {valid} 个文献任务（{missing} 个因文件缺失跳过）")
        elif missing:
            logger.warning(f"{missing} 个文献任务因文件缺失跳过")
    except Exception as e:
        logger.warning(f"恢复 queued 任务失败（可忽略）: {e}")


def _process_existing_pdf(task_id, book_id, pdf_path, artist_id=None):
    """处理已存在的 PDF（恢复路径）"""
    try:
        process_pdf_file_sync(
            pdf_path=pdf_path,
            task_id=task_id,
            book_id=book_id,
            artist_id=artist_id,
            document_type='literature',
        )
        _try_extract_metadata(book_id)
    except Exception as e:
        logger.error(f"文献恢复处理失败 {book_id}: {e}")


# 首次导入时自动恢复
_recover_queued_tasks()


# ============ Pydantic 模型 ============

class LiteratureResponse(BaseModel):
    id: str
    title: Optional[str] = None
    author: Optional[str] = None
    source_type: Optional[str] = None
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
    source_type: Optional[str] = None


# ============ 端点 ============

@router.post("/upload")
async def upload_literature(
    artist_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publish_year: Optional[int] = Form(None),
    keywords: Optional[str] = Form(None),
    doi: Optional[str] = Form(None),
    current_user: User = Depends(require_editor),
    db: Session = Depends(get_db),
):
    """上传文献 PDF，关联到指定画家"""
    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存文件（限制 50MB）
    MAX_SIZE = 50 * 1024 * 1024
    try:
        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(413, "文件大小超过 50MB 限制")
        file_path, file_url = save_book_upload(file.filename, content)
    except HTTPException:
        raise
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
        author=author,
        journal=journal,
        publish_year=publish_year,
        keywords=json.dumps([k.strip() for k in keywords.split(',') if k.strip()]) if keywords else keywords,
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

    # 后台处理（排队，最多 2 个并发）
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

    _enqueue_pdf_task(_process)

    return {"book_id": book_id, "task_id": task_id}


def _try_extract_metadata(book_id: str):
    """尝试用 LLM 提取元数据"""
    from .database import get_db as _get_db
    from .metadata_extractor import extract_metadata
    import asyncio
    import re

    UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

    def _is_bad_title(t):
        if not t:
            return True
        return bool(UUID_RE.match(t.strip()))

    db = next(_get_db())
    try:
        book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
        if not book or not book.full_md:
            return

        needs_extract = _is_bad_title(book.title) or not book.author or not book.journal
        if not needs_extract:
            return

        meta = asyncio.run(extract_metadata(book.full_md, filename=book.file_name))
        if not meta:
            return

        if _is_bad_title(book.title) and meta.get('title'):
            book.title = meta['title']
        if not book.author and meta.get('authors'):
            book.author = ', '.join(meta['authors']) if isinstance(meta['authors'], list) else str(meta['authors'])
        if not book.journal and meta.get('journal'):
            book.journal = meta['journal']
        if not book.publish_year and meta.get('publish_year'):
            book.publish_year = meta['publish_year']
        if not book.doi and meta.get('doi'):
            book.doi = meta['doi']
        if not book.abstract and meta.get('abstract'):
            book.abstract = meta['abstract']
        if not book.keywords and meta.get('keywords'):
            import json as _json
            book.keywords = _json.dumps(meta['keywords'], ensure_ascii=False)
        if not book.source_type and meta.get('source_type'):
            book.source_type = meta['source_type']
        db.commit()
    except Exception as e:
        logger.error(f"元数据提取失败: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


@router.get("")
async def list_literature(
    artist_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
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
    col_map = {
        'created_at': PdfBook.created_at,
        'publish_year': PdfBook.publish_year,
        'title': PdfBook.title,
    }
    col = col_map.get(sort_by, PdfBook.created_at)
    query = query.order_by(col.desc() if sort_dir == 'desc' else col.asc())

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
                "source_type": b.source_type,
                "publish_year": b.publish_year,
                "doi": b.doi,
                "abstract": b.abstract,
                "keywords": b.keywords,
                "status": b.status,
                "total_pages": b.total_pages,
                "chunk_count": chunk_counts.get(b.id, 0),
                "full_md_length": len(b.full_md) if b.full_md else 0,
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
        "source_type": book.source_type,
        "publish_year": book.publish_year,
        "doi": book.doi,
        "abstract": book.abstract,
        "keywords": book.keywords,
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
    if body.source_type is not None:
        book.source_type = body.source_type

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
        PdfBook.document_type == 'literature',
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
        PdfBook.document_type == 'literature',
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


@router.get("/{book_id}/images")
async def get_literature_images(
    artist_id: int,
    book_id: str,
    db: Session = Depends(get_db),
):
    """获取文献中提取的插图列表"""
    book = db.query(PdfBook).filter(
        PdfBook.id == book_id,
        PdfBook.artist_id == artist_id,
        PdfBook.document_type == 'literature',
    ).first()
    if not book:
        raise HTTPException(404, "文献不存在")

    from .models import ExtractedImage
    images = db.query(ExtractedImage).filter(
        ExtractedImage.book_id == book_id
    ).order_by(ExtractedImage.page, ExtractedImage.file_name).all()

    return {
        "images": [
            {
                "id": img.id,
                "file_name": img.file_name,
                "stored_url": img.stored_url,
                "page": img.page,
                "caption": img.caption,
            }
            for img in images
        ]
    }
