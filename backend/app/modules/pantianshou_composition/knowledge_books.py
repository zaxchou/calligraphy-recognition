"""
书籍管理 API 路由
提供 PDF 上传、CRUD、内容查看等功能
"""

import os
import re
import json
import shutil
import uuid
import asyncio
import threading
import logging
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db, SessionLocal
from .models import PdfBook, TextChunk, ExtractedImage, SummaryCache
from .task_manager import TaskManager
from .knowledge_ingest_v2 import process_pdf_file_sync, KnowledgeIngestV2

from app.core.auth import require_admin_role

router = APIRouter()

logger = logging.getLogger(__name__)

# 存储路径
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 输出安全层：移除 LaTeX 数学标记（处理旧数据中残留的 $...$）
_STRIP_LATEX_RE = re.compile(r'\$\$[^$]*\$\$|\$[^$]*\$|\\(?:begin|end)\{[^}]*\}')


def _parse_caption_for_display(caption: str) -> str:
    """
    从长 caption 中提取简短显示标签。
    caption 格式示例：
      "图16　清代　朱耷　《梅花图轴》　纸本水墨 32.4cm×25.1cm　年代不详　江苏南京博物院藏"
      "图7　 明代　 林良　 《双鹰图》　 绢本设色\r\n133.4cm×50.5cm ..."

    返回格式示例："图七 | 清代·朱耷《梅花图轴》"
    """
    if not caption:
        return ""
    text = caption.replace("\r\n", " ").replace("\n", " ")
    # 清理多余空白
    text = re.sub(r"\s+", "　", text).strip()

    # 提取图号（图+数字或中文数字）
    figure_id = ""
    fig_match = re.search(r"图\s*([0-9]+|[一二三四五六七八九十百零〇○]+)", text)
    if fig_match:
        raw = fig_match.group(0).strip()
        # 中文数字转阿拉伯
        cn = {"〇": "0", "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
              "五": "5", "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
        digit = fig_match.group(1)
        if digit in cn:
            digit = cn[digit]
        figure_id = f"图{digit}"

    # 提取朝代
    era = ""
    era_match = re.search(r"(上古|先秦|秦汉|汉代|魏晋|南北朝|隋代|唐代|五代|宋代|元代|明代|清代|近代|现代)", text)
    if era_match:
        era = era_match.group(1)

    # 提取画家（朝代之后、书名号之前的词）
    artist = ""
    if era:
        after_era = text[text.find(era) + len(era):]
        bracket_match = re.search(r"《", after_era)
        if bracket_match:
            artist_text = after_era[:bracket_match.start()].strip()
            # 取最后一个词（画家名通常就一到两字）
            words = artist_text.split()
            if words:
                artist = words[-1].strip()
    else:
        # 没有朝代时，尝试直接找画家
        bracket_match = re.search(r"《", text)
        if bracket_match:
            before_title = text[:bracket_match.start()].strip()
            words = before_title.split()
            if words:
                artist = words[-1].strip()

    # 提取作品名
    title = ""
    title_match = re.search(r"《([^》]+)》", text)
    if title_match:
        title = title_match.group(1).strip()

    # 组装 display_label
    parts = []
    if figure_id:
        parts.append(figure_id)
    if artist and title:
        era_prefix = f"{era}·" if era else ""
        parts.append(f"{era_prefix}{artist}《{title}》")
    elif artist:
        era_prefix = f"{era}·" if era else ""
        parts.append(f"{era_prefix}{artist}")
    elif title:
        parts.append(f"《{title}》")

    return " | ".join(parts) if parts else (figure_id or caption[:20])


def _clear_summary_cache(db: Session):
    """清除全部 AI 摘要缓存（新书上架/重新入库后调用）"""
    count = db.query(SummaryCache).count()
    if count > 0:
        db.query(SummaryCache).delete()
        db.commit()
        logger.info("已清除 %d 条 AI 摘要缓存", count)


# ============ 数据模型 ============

class BookCreateResponse(BaseModel):
    book_id: str
    task_id: str
    message: str


class BookResponse(BaseModel):
    id: str
    file_name: str
    title: Optional[str]
    author: Optional[str]
    total_pages: Optional[int]
    status: str
    created_at: str

    class Config:
        from_attributes = True


# ============ 书籍管理 API ============

@router.post("/books/upload", response_model=BookCreateResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    chunk_strategy: str = Form("semantic"),
    chunk_size: int = Form(500),
    parser_backend: str = Form("mineru"),
    series_id: str = Form(None),
    page_offset: int = Form(1),
    db: Session = Depends(get_db)
):
    """
    上传 PDF 文件并开始处理

    Args:
        file: PDF 文件
        chunk_strategy: 分块策略 (semantic/fixed)
        chunk_size: 块大小
        parser_backend: PDF 解析器后端 ("mineru")
        series_id: 系列ID，同一套书的多卷共享此ID（传空字符串则不关联）
        page_offset: 系列内起始页码偏移（本卷在完整书中的第一页页码，如 part2 从 201 开始）
    """
    # 检查文件类型
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "只支持 PDF 文件")

    # 验证 parser_backend
    if parser_backend not in ("mineru",):
        raise HTTPException(400, f"不支持的 parser_backend: {parser_backend}，仅支持: mineru")

    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    # 保存文件
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 创建处理任务（后台线程模式，立即返回 task_id）
    try:
        # 先创建书籍记录和任务记录
        with KnowledgeIngestV2(
            db=db,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            parser_backend=parser_backend
        ) as ingest:
            # 创建书籍记录
            book = ingest._create_book_record(file_path)
            book_id = book.id

            # 设置系列ID和页面偏移（用于跨文件定位）
            if series_id:
                book.series_id = series_id
            book.page_offset = page_offset

            # 创建任务记录
            task_manager = TaskManager(db)
            task = task_manager.create_task(book_id, "full_process")
            task_id = task.id

            db.commit()

        # 启动后台线程执行入库
        def _run_ingest():
            try:
                with TaskManager() as tm:
                    tm.update_progress(task_id, 5, "初始化", f"开始处理（使用 {parser_backend} 解析器）...")

                with KnowledgeIngestV2(
                    chunk_strategy=chunk_strategy,
                    chunk_size=chunk_size,
                    parser_backend=parser_backend
                ) as ingest:
                    result = asyncio.run(ingest.process_pdf(file_path, task_id=task_id, book_id=book_id))

                if result.get("status") == "failed":
                    with TaskManager() as tm:
                        tm.fail_task(task_id, result.get("error", "未知错误"), "处理失败")

                # 新书上架，清除摘要缓存
                with SessionLocal() as db2:
                    _clear_summary_cache(db2)

            except Exception as e:
                import traceback
                logger.error(f"上传处理后台线程异常: {e}\n{traceback.format_exc()}")
                with TaskManager() as tm:
                    tm.fail_task(task_id, str(e), "处理异常")

        thread = threading.Thread(target=_run_ingest, daemon=True)
        thread.start()

        return BookCreateResponse(
            book_id=book_id,
            task_id=task_id,
            message=f"PDF 上传成功，正在使用 {parser_backend} 解析器处理中"
        )

    except Exception as e:
        import traceback
        # 清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(500, f"处理失败: {str(e)}\n{traceback.format_exc()}")


@router.get("/books", response_model=List[BookResponse])
async def list_books(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取书籍列表
    """
    query = db.query(PdfBook)

    if status:
        query = query.filter(PdfBook.status == status)

    books = query.order_by(PdfBook.created_at.desc()).offset(offset).limit(limit).all()

    return [BookResponse(
        id=b.id,
        file_name=b.file_name,
        title=b.title,
        author=b.author,
        total_pages=b.total_pages,
        status=b.status,
        created_at=b.created_at.isoformat() if b.created_at else None,
    ) for b in books]


@router.get("/books/{book_id}", response_model=BookResponse)
async def get_book(book_id: str, db: Session = Depends(get_db)):
    """
    获取书籍详情
    """
    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    return BookResponse(
        id=book.id,
        file_name=book.file_name,
        title=book.title,
        author=book.author,
        total_pages=book.total_pages,
        status=book.status,
        created_at=book.created_at.isoformat() if book.created_at else None,
    )


@router.delete("/books/{book_id}")
async def delete_book(book_id: str, db: Session = Depends(get_db), admin=Depends(require_admin_role)):
    """
    删除书籍及其所有相关数据（级联删除）

    删除范围：
    1. SQLite: pdf_books + 级联删除 text_chunks, extracted_images, knowledge_tasks
    2. Qdrant: knowledge_texts, knowledge_images, knowledge_tables 中的向量
    3. 磁盘: PDF 文件 + 提取的图像文件
    """
    from .qdrant_client import delete_book_vectors

    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    book_title = book.title or book.file_name
    logger.info("开始删除书籍: %s (id=%s)", book_title, book_id)

    # 1. 删除 Qdrant 中的向量（必须在删除 SQLite 之前，因为需要 book_id）
    try:
        delete_book_vectors(book_id)
        logger.info("Qdrant 向量已删除: %s", book_id)
    except Exception as e:
        logger.error("删除 Qdrant 向量失败: %s", e)
        # 继续删除其他数据，不中断流程

    # 2. 删除磁盘上的 PDF 文件
    if book.stored_path and os.path.exists(book.stored_path):
        try:
            os.remove(book.stored_path)
            logger.info("PDF 文件已删除: %s", book.stored_path)
        except Exception as e:
            logger.error("删除 PDF 文件失败: %s", e)

    # 3. 删除磁盘上的图像文件（统一路径: data/knowledge/books/images/{book_id}/）
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    image_dirs_to_try = [
        os.path.join(base_dir, "knowledge", "books", "images", book_id),  # MinerU 解析
        os.path.join(base_dir, "uploads", "images", book_id),  # PyMuPDF 解析（兼容旧数据）
    ]
    for image_dir in image_dirs_to_try:
        if os.path.exists(image_dir):
            try:
                shutil.rmtree(image_dir)
                logger.info("图像目录已删除: %s", image_dir)
            except Exception as e:
                logger.error("删除图像目录失败: %s", e)

    # 4. 删除 SQLite 记录（级联删除会处理 text_chunks, extracted_images, knowledge_tasks）
    try:
        db.delete(book)
        db.commit()
        logger.info("SQLite 记录已删除: %s", book_id)
    except Exception as e:
        db.rollback()
        logger.error("删除 SQLite 记录失败: %s", e)
        raise HTTPException(500, f"删除数据库记录失败: {str(e)}")

    return {"message": f"书籍 '{book_title}' 及其所有关联数据已删除"}


@router.post("/books/{book_id}/reingest")
async def reingest_book(
    book_id: str,
    chunk_strategy: str = Form("semantic"),
    chunk_size: int = Form(500),
    parser_backend: str = Form("mineru"),
    db: Session = Depends(get_db)
):
    """
    重新入库书籍 - 异步模式

    立即返回 task_id，后台线程执行入库。
    前端通过 GET /tasks/{task_id} 轮询进度。

    Args:
        book_id: 书籍ID
        chunk_strategy: 分块策略
        chunk_size: 块大小
        parser_backend: PDF 解析器后端 ("mineru")
    """
    # 验证 parser_backend
    if parser_backend not in ("mineru",):
        raise HTTPException(400, f"不支持的 parser_backend: {parser_backend}，仅支持: mineru")
    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    if not os.path.exists(book.stored_path):
        raise HTTPException(404, "PDF 文件不存在")

    # 1. 创建任务记录
    task_manager = TaskManager(db)
    task = task_manager.create_task(book_id, "full_process", "准备重新入库...")
    task_id = task.id

    # 2. 预清理旧数据（同步完成，避免后台线程 db session 冲突）
    from . import qdrant_client

    old_chunks = db.query(TextChunk).filter(TextChunk.book_id == book_id).all()
    vector_ids = [c.vector_id for c in old_chunks if c.vector_id]
    if vector_ids:
        qdrant_client.delete_points(qdrant_client.KNOWLEDGE_TEXTS_COLLECTION, vector_ids)
    db.query(TextChunk).filter(TextChunk.book_id == book_id).delete()
    book.status = "processing"
    db.commit()

    # 3. 启动后台线程执行入库
    pdf_path = book.stored_path  # 在线程外读取，避免 session 问题

    def _run_ingest():
        try:
            with TaskManager() as tm:
                tm.update_progress(task_id, 5, "初始化", f"开始重新入库（使用 {parser_backend} 解析器）...")

            with KnowledgeIngestV2(
                chunk_strategy=chunk_strategy,
                chunk_size=chunk_size,
                parser_backend=parser_backend
            ) as ingest:
                result = asyncio.run(ingest.process_pdf(pdf_path, task_id=task_id, book_id=book_id))

            if result.get("status") == "failed":
                with TaskManager() as tm:
                    tm.fail_task(task_id, result.get("error", "未知错误"), "入库失败")
                with SessionLocal() as db2:
                    bk = db2.query(PdfBook).filter(PdfBook.id == book_id).first()
                    if bk:
                        bk.status = "failed"
                        db2.commit()
        except Exception as e:
            import traceback
            logger.error(f"重新入库后台线程异常: {e}\n{traceback.format_exc()}")
            try:
                with TaskManager() as tm:
                    tm.fail_task(task_id, str(e), "入库异常")
                with SessionLocal() as db2:
                    bk = db2.query(PdfBook).filter(PdfBook.id == book_id).first()
                    if bk:
                        bk.status = "failed"
                        db2.commit()
            except Exception:
                pass

    t = threading.Thread(target=_run_ingest, daemon=True)
    t.start()

    # 重新入库，清除摘要缓存
    _clear_summary_cache(db)

    return {
        "message": "已开始重新入库",
        "book_id": book_id,
        "task_id": task_id,
        "status": "processing"
    }


# ============ 内容查看 API ============

@router.get("/books/{book_id}/chunks")
async def get_book_chunks(
    book_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取书籍的文本块（含完整配图信息）
    """
    chunks = db.query(TextChunk).filter(
        TextChunk.book_id == book_id
    ).order_by(TextChunk.chunk_index).offset(offset).limit(limit).all()

    results = []
    for c in chunks:
        # associated_images 可能是 JSON 字符串或列表，统一解析
        raw_images = c.associated_images
        image_ids = []
        if isinstance(raw_images, str):
            try:
                image_ids = json.loads(raw_images) if raw_images.strip() else []
            except (json.JSONDecodeError, ValueError):
                image_ids = []
        elif isinstance(raw_images, list):
            image_ids = raw_images
        else:
            image_ids = []

        # 查完整图片信息
        full_images = []
        if image_ids:
            imgs = db.query(ExtractedImage).filter(
                ExtractedImage.id.in_(image_ids)
            ).all()
            img_map = {img.id: img for img in imgs}
            for img_id in image_ids:
                img = img_map.get(img_id)
                if img:
                    url = img.stored_url or img.url or ""
                    full_images.append({
                        "id": img.id,
                        "file_name": img.file_name,
                        "url": url,
                        "stored_url": url,
                        "page": img.page,
                        "figure_id": img.figure_id,
                        "caption": img.caption or "",
                        "display_label": _parse_caption_for_display(img.caption) or img.figure_id or f"图{img.page}" if img.page else "",
                    })

        results.append({
            "id": c.id,
            "chunk_index": c.chunk_index,
            "chapter_title": c.chapter_title,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
            "associated_images": full_images,
        })

    return results


@router.get("/books/{book_id}/images")
async def get_book_images(
    book_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取书籍的图像
    """
    images = db.query(ExtractedImage).filter(
        ExtractedImage.book_id == book_id
    ).order_by(ExtractedImage.page).offset(offset).limit(limit).all()

    return [{
        "id": i.id,
        "file_name": i.file_name,
        "stored_url": i.stored_url,
        "page": i.page,
        "figure_id": i.figure_id,
        "caption": i.caption,
        "bbox": i.bbox,
        "associated_chunks": i.associated_chunks,
    } for i in images]


@router.get("/books/{book_id}/pdf")
async def get_book_pdf(book_id: str, db: Session = Depends(get_db)):
    """
    获取 PDF 文件
    """
    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    if not os.path.exists(book.stored_path):
        # Try resolved absolute path
        abs_path = os.path.abspath(book.stored_path)
        if not os.path.exists(abs_path):
            raise HTTPException(404, "PDF 文件不存在")
        file_path = abs_path
    else:
        file_path = book.stored_path

    file_name = os.path.basename(book.file_name or file_path)
    # Content-Disposition 不能包含中文字符，用 URL 编码
    import urllib.parse
    ascii_name = urllib.parse.quote(file_name, safe='_.-')
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{ascii_name}\""}
    )


# ============ 大纲 API ============

@router.get("/books/{book_id}/outline")
async def get_book_outline(book_id: str, db: Session = Depends(get_db)):
    """
    获取书籍的文档大纲

    如果该书属于某个系列（有 series_id），会合并该系列中所有书籍的大纲，
    并根据每本书的 page_offset 调整页码，同时标记每个大纲项属于哪本书。
    """
    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    # 如果该书属于某个系列，合并系列内所有大纲
    if book.series_id:
        siblings = db.query(PdfBook).filter(
            PdfBook.series_id == book.series_id,
            PdfBook.outline.isnot(None)
        ).order_by(PdfBook.page_offset).all()

        merged = []
        for sib in siblings:
            offset = sib.page_offset or 1
            # Build page map from chunks (outline items in order → chunk page_start)
            chunk_pages = []
            if sib.id != book_id:
                chunks = db.query(TextChunk.page_start).filter(
                    TextChunk.book_id == sib.id,
                    TextChunk.page_start.isnot(None)
                ).order_by(TextChunk.chunk_index).all()
                chunk_pages = [c[0] for c in chunks]

            outline_items = sib.outline or []
            for i, item in enumerate(outline_items):
                raw_page = item.get("page")
                if raw_page is not None and raw_page > 0:
                    page = raw_page + offset - 1
                elif raw_page is not None and raw_page == 0 and chunk_pages:
                    # Map by proportional position: outline[i] ≈ chunk[floor(i/N*M)]
                    idx = int(i / max(len(outline_items)-1, 1) * (len(chunk_pages)-1))
                    page = chunk_pages[idx] + offset - 1
                else:
                    page = offset if raw_page == 0 else None
                merged.append({
                    "title": item["title"],
                    "page": page,
                    "level": item.get("level", 2),
                    "target_book_id": sib.id,
                })
        return {"book_id": book_id, "outline": merged, "series": True}

    if not book.outline:
        return {"book_id": book_id, "outline": [], "message": "暂无大纲数据"}
    return {"book_id": book_id, "outline": book.outline}


# ============ Markdown API ============

@router.get("/books/{book_id}/markdown")
async def get_book_markdown(book_id: str, db: Session = Depends(get_db)):
    """
    获取书籍的完整 Markdown 内容

    返回 MinerU 提取的完整 Markdown 格式文本
    """
    book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
    if not book:
        raise HTTPException(404, "书籍不存在")

    if not book.full_md:
        return {
            "book_id": book_id,
            "markdown": "",
            "message": "暂无 Markdown 数据（需使用 MinerU 解析器重新入库）"
        }

    return {
        "book_id": book_id,
        "markdown": _STRIP_LATEX_RE.sub('', book.full_md or ""),
        "length": len(book.full_md or ""),
    }
