"""
知识管理 API 路由
提供 PDF 上传、任务管理、搜索等功能
"""

import os
import re
import shutil
import uuid
import asyncio
from datetime import datetime
import logging
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .models import PdfBook, KnowledgeTask, TextChunk, ExtractedImage, SearchHistory, SummaryCache, CompositionRule, CompositionFigure
from .task_manager import TaskManager
from .knowledge_ingest_v2 import process_pdf_file_sync

router = APIRouter()
logger = logging.getLogger(__name__)

# 输出安全层：移除 LaTeX 数学标记（处理旧数据中残留的 $...$）
_STRIP_LATEX_RE = re.compile(r'\$\$[^$]*\$\$|\$[^$]*\$|\\(?:begin|end)\{[^}]*\}')


def _parse_caption_for_display(caption: str) -> str:
    """
    从长 caption 中提取简短显示标签。
    caption 格式示例：
      "图16\u3000清代\u3000朱耷\u3000《梅花图轴》\u3000纸本水墨 32.4cm×25.1cm\u3000年代不详\u3000江苏南京博物院藏"
      "图7\u3000 明代\u3000 林良\u3000 《双鹰图》\u3000 绢本设色\r\n133.4cm×50.5cm ..."

    返回格式示例："图七 | 清代·朱耷《梅花图轴》"
    """
    if not caption:
        return ""
    text = caption.replace("\r\n", " ").replace("\n", " ")
    # 清理多余空白
    text = re.sub(r"\s+", "\u3000", text).strip()

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


# 存储路径
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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


class TaskResponse(BaseModel):
    id: str
    book_id: str
    task_type: str
    status: str
    progress: int
    stage: Optional[str]
    message: Optional[str]
    result: Optional[dict]
    error_message: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    book_ids: Optional[List[str]] = None
    limit: int = 10


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    chapter_title: Optional[str]
    page_start: Optional[int]
    page_end: Optional[int]
    book_title: Optional[str]
    score: float


# ============ 书籍管理 API ============

def _clear_summary_cache(db: Session):
    """清除全部 AI 摘要缓存（新书上架/重新入库后调用）"""
    count = db.query(SummaryCache).count()
    if count > 0:
        db.query(SummaryCache).delete()
        db.commit()
        logger.info("已清除 %d 条 AI 摘要缓存", count)

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
        from .knowledge_ingest_v2 import KnowledgeIngestV2
        from .database import SessionLocal
        
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
        import threading
        
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
async def delete_book(book_id: str, db: Session = Depends(get_db)):
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
    import threading
    pdf_path = book.stored_path  # 在线程外读取，避免 session 问题
    
    def _run_ingest():
        try:
            from .knowledge_ingest_v2 import KnowledgeIngestV2
            from .database import SessionLocal
            
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
                from .database import SessionLocal
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


# ============ 任务管理 API ============

@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    book_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取任务列表
    """
    query = db.query(KnowledgeTask)
    
    if book_id:
        query = query.filter(KnowledgeTask.book_id == book_id)
    if status:
        query = query.filter(KnowledgeTask.status == status)
    
    tasks = query.order_by(KnowledgeTask.created_at.desc()).limit(limit).all()
    
    return [TaskResponse(
        id=t.id,
        book_id=t.book_id,
        task_type=t.task_type,
        status=t.status,
        progress=t.progress,
        stage=t.stage,
        message=t.message,
        result=t.result,
        error_message=t.error_message,
        created_at=t.created_at.isoformat() if t.created_at else None,
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
    ) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """
    获取任务详情
    """
    task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    
    return TaskResponse(
        id=task.id,
        book_id=task.book_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        stage=task.stage,
        message=task.message,
        result=task.result,
        error_message=task.error_message,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: Session = Depends(get_db)):
    """
    重试失败的任务
    """
    task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    
    if task.status not in ["failed", "cancelled"]:
        raise HTTPException(400, "只有失败或取消的任务可以重试")
    
    book = db.query(PdfBook).filter(PdfBook.id == task.book_id).first()
    if not book or not os.path.exists(book.stored_path):
        raise HTTPException(404, "PDF 文件不存在")
    
    # 重新处理
    try:
        result = process_pdf_file_sync(book.stored_path, task_id=task_id, book_id=book.id)
        return {"message": "任务已重新提交", "result": result}
    except Exception as e:
        raise HTTPException(500, f"重试失败: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """
    取消任务
    """
    task_manager = TaskManager(db)
    success = task_manager.cancel_task(task_id)
    
    if not success:
        raise HTTPException(400, "任务无法取消")
    
    return {"message": "任务已取消"}


# ============ 内容查看 API ============

@router.get("/books/{book_id}/chunks")
async def get_book_chunks(
    book_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取书籍的文本块
    """
    chunks = db.query(TextChunk).filter(
        TextChunk.book_id == book_id
    ).order_by(TextChunk.chunk_index).offset(offset).limit(limit).all()
    
    return [{
        "id": c.id,
        "chunk_index": c.chunk_index,
        "chapter_title": c.chapter_title,
        "page_start": c.page_start,
        "page_end": c.page_end,
        "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
        "associated_images": c.associated_images,
    } for c in chunks]


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


@router.get("/images/{image_id}/related-chunks")
async def get_image_related_chunks(image_id: str, db: Session = Depends(get_db)):
    """
    获取图片关联的文本块
    
    返回与该图片关联的所有文本块信息
    """
    image = db.query(ExtractedImage).filter(ExtractedImage.id == image_id).first()
    if not image:
        raise HTTPException(404, "图片不存在")
    
    related_chunks = []
    if image.associated_chunks:
        chunks = db.query(TextChunk).filter(
            TextChunk.id.in_(image.associated_chunks)
        ).order_by(TextChunk.chunk_index).all()
        
        related_chunks = [{
            "id": c.id,
            "chunk_index": c.chunk_index,
            "chapter_title": c.chapter_title,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
            "bbox": c.bbox,
        } for c in chunks]
    
    return {
        "image_id": image_id,
        "image_info": {
            "file_name": image.file_name,
            "stored_url": image.stored_url,
            "page": image.page,
            "figure_id": image.figure_id,
            "caption": image.caption,
            "bbox": image.bbox,
        },
        "related_chunks": related_chunks,
        "total_chunks": len(related_chunks),
    }


@router.get("/images/{book_id}/{image_name}")
async def get_image(book_id: str, image_name: str):
    """
    获取图像文件
    支持两个存储位置：
    1. data/knowledge/books/images/{book_id}/{image_name} (MinerU 解析)
    2. data/uploads/images/{book_id}/{image_name} (PyMuPDF 解析)
    """
    # 尝试两个可能的路径
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    
    # 路径1: knowledge/books/images (MinerU 解析的图像)
    path1 = os.path.join(base_dir, "knowledge", "books", "images", book_id, image_name)
    if os.path.exists(path1):
        return FileResponse(path1)
    
    # 路径2: uploads/images (PyMuPDF 解析的图像)
    path2 = os.path.join(base_dir, "uploads", "images", book_id, image_name)
    if os.path.exists(path2):
        return FileResponse(path2)
    
    raise HTTPException(404, f"图像不存在: {image_name}")


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


# ============ 搜索 API ============

def _truncate_to_sentence_boundary(text: str, max_len: int, direction: str = "tail") -> str:
    """智能截取文本到最近的句子边界

    Args:
        text: 原始文本
        max_len: 最大长度
        direction: "tail" 从末尾截取（用于上文），"head" 从开头截取（用于下文）

    Returns:
        截取后的文本，在最近的句号/问号/感叹号处截断
    """
    if not text or len(text) <= max_len:
        return text

    # 句子结束符
    sentence_endings = [".", "?", "!", "。", "？", "！", "\n"]

    if direction == "tail":
        # 从末尾截取：取最后 max_len 个字符，然后找到第一个句子结束符
        truncated = text[-max_len:]
        # 找到第一个句子结束符的位置（跳过开头可能的不完整句子）
        first_end = -1
        for i, char in enumerate(truncated):
            if char in sentence_endings:
                first_end = i
                break
        if first_end >= 0 and first_end < len(truncated) - 1:
            return truncated[first_end + 1:].strip()
        return truncated.strip()
    else:
        # 从开头截取：取前 max_len 个字符，找到最后一个句子结束符
        truncated = text[:max_len]
        # 找到最后一个句子结束符
        last_end = -1
        for i, char in enumerate(truncated):
            if char in sentence_endings:
                last_end = i
        if last_end >= 0:
            return truncated[:last_end + 1].strip()
        return truncated.strip()


def _should_include_in_search(payload: dict) -> bool:
    """判断该文档是否应该包含在搜索结果中

    图像类型（pantianshou_illustration、knowledge_figure）现在由跨模态搜索返回，
    应该包含在结果中。排除规则、章节元数据、艺术家档案等非搜索内容。
    """
    doc_type = payload.get("type")

    # 排除潘天寿规则（这些应该在构图分析中使用，不在知识搜索中显示）
    if doc_type == "pantianshou_rule":
        return False

    # 图像类型：现在跨模态搜索可以返回有意义的图像结果，保留
    # pantianshou_illustration → 潘天寿正反例插图
    # knowledge_figure → 写意花鸟画教程插图
    # 这些通过跨模态 embedding 搜索找到，前端标记 result_type="image" 区分展示

    # 排除章节元数据（这些是结构信息，不是可搜索的文本内容）
    if doc_type == "knowledge_chapter":
        return False
    
    # 排除艺术家档案（这些是元数据，不是可搜索的文本内容）
    if doc_type == "knowledge_artist":
        return False

    # 其他类型（包括 None，即 PDF 上传的文本）都包含
    return True


def _extract_book_title(payload: dict) -> str:
    """从 payload 中提取书名/来源名称

    支持多种字段路径回退：
    - metadata.book_title (PDF 上传)
    - book (花鸟教程章节)
    - name (艺术家档案)
    - type (其他类型)
    """
    # 1. PDF 上传: metadata.book_title
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        book_title = metadata.get("book_title")
        if book_title:
            return book_title

    # 2. 章节/分类字段
    book = payload.get("book")
    if book:
        return book

    # 3. 书名字段
    bt = payload.get("book_title")
    if bt:
        return bt

    # 4. 艺术家档案: name 字段
    name = payload.get("name")
    if name:
        era = payload.get("era", "")
        if era:
            return f"{era}·{name}"
        return name

    # 5. 来源字段
    source = payload.get("source", "")
    if source and source != "uploaded_images":
        return source

    # 6. 最后回退
    doc_type = payload.get("type", "")
    return doc_type or "知识库"


@router.post("/search")
async def search(request: SearchRequest, db: Session = Depends(get_db)):
    """
    语义搜索 - 基于 Qdrant 向量搜索
    集成 Query 改写 + 混合搜索 + AI 摘要回答
    """
    from .embedding_service import EmbeddingService
    from . import qdrant_client
    from .hybrid_search import hybrid_search as do_hybrid_search
    from .ai_summarizer import generate_summary
    import traceback
    
    try:
        # ---- ① Query 改写（异步，不阻塞主流程）----
        from .query_rewriter import rewrite_query
        try:
            rewrite_result = await asyncio.wait_for(
                rewrite_query(request.query), timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("Query 改写超时(10s)，使用原始查询")
            rewrite_result = {"original": request.query, "rewrites": [], "intent": "综合"}
        except Exception as e:
            logger.warning("Query 改写异常: %s，使用原始查询", e)
            rewrite_result = {"original": request.query, "rewrites": [], "intent": "综合"}

        rewritten_queries = rewrite_result.get("rewrites", [])
        query_intent = rewrite_result.get("intent", "综合")
        all_queries = [request.query] + rewritten_queries

        logger.info("搜索查询: 原始='%s', 改写=%s, 意图=%s",
                   request.query, rewritten_queries, query_intent)

        # ---- ② 对所有查询分别做混合搜索，合并去重 ----
        embedding_service = EmbeddingService()
        seen_ids = set()  # 用 vector_id 去重
        merged_results = []

        for q in all_queries:
            embed_result = await embedding_service.embed_text(q)
            q_embedding = embed_result.embedding if embed_result else None
            if not q_embedding:
                continue

            # 搜索文本集合
            hybrid_results = await do_hybrid_search(
                query_text=q,
                query_vector=q_embedding,
                collection=qdrant_client.KNOWLEDGE_TEXTS_COLLECTION,
                limit=request.limit,
            )

            for r in hybrid_results:
                vid = r.get("id")
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    merged_results.append(r)

        # ---- ②.5 跨模态搜索：用 multimodal-embedding-v1 文本向量搜索图像集合 ----
        if embedding_service.multimodal_enabled and embedding_service.api_key:
            try:
                from dashscope import MultiModalEmbedding
                from dashscope.embeddings.multimodal_embedding import MultiModalEmbeddingItemText
                import dashscope

                dashscope.api_key = embedding_service.api_key

                for q in all_queries[:3]:  # 最多3个查询做图像搜索，控制API调用量
                    try:
                        mm_result = await asyncio.to_thread(
                            MultiModalEmbedding.call,
                            model="multimodal-embedding-v1",
                            input=[MultiModalEmbeddingItemText(text=q, factor=1.0)],
                        )
                        if mm_result.status_code != 200:
                            logger.warning("跨模态文本 embedding 失败: %s", mm_result.message)
                            continue

                        mm_vec = mm_result.output["embeddings"][0]["embedding"]
                        # 跨模态图像搜索：纯向量搜索（BM25 对图像帮助有限，且会挤掉 caption 为空的新图）
                        # score_threshold=0.22: 跨模态余弦正常范围 0.19-0.23，低于此阈值视为噪声
                        img_vec_results = qdrant_client.search_collection(
                            qdrant_client.KNOWLEDGE_IMAGES_COLLECTION,
                            mm_vec,
                            limit=max(5, request.limit // 2),
                            score_threshold=0.22,
                        )
                        img_results = [
                            {"id": r.get("id"), "score": r.get("score", 0), "payload": r.get("payload", {})}
                            for r in img_vec_results
                        ]
                        
                        for r in img_results:
                            vid = r.get("id")
                            if vid and vid not in seen_ids:
                                seen_ids.add(vid)
                                merged_results.append(r)
                    except Exception as e:
                        logger.warning("跨模态图像搜索失败(query='%s'): %s", q[:30], e)
            except ImportError:
                logger.warning("dashscope SDK 未安装，跳过跨模态图像搜索")

        # 构建 book_ids 过滤
        search_results = []
        if request.book_ids:
            for r in merged_results:
                book_id = r.get("payload", {}).get("book_id")
                if book_id in request.book_ids:
                    search_results.append(r)
        else:
            search_results = merged_results
        
        # 启发式精排（图像结果不参与精排，直接保留）
        from .reranker import heuristic_rerank
        IMAGE_TYPES = {"knowledge_figure", "pantianshou_illustration", "pdf_extracted_image"}
        text_results = [r for r in search_results if r.get("payload", {}).get("type") not in IMAGE_TYPES]
        image_results = [r for r in search_results if r.get("payload", {}).get("type") in IMAGE_TYPES]
        
        # 文本结果精排
        reranked_texts = heuristic_rerank(request.query, text_results, top_k=request.limit)
        
        # 图像结果：跨模态余弦分数 >= 0.25 才保留（0.22-0.24 属于弱相关，不放主结果列表）
        # 不强制保留最低数量，宁缺毋滥
        image_results = [r for r in image_results if r.get("score", 0) >= 0.25]
        image_results.sort(key=lambda r: r.get("score", 0), reverse=True)
        max_images = request.limit // 3
        kept_images = image_results[:max_images]
        
        # 合并：文本在前，图像在后
        search_results = reranked_texts + kept_images

        # ---- 过滤非文本内容 ----
        search_results = [r for r in search_results if _should_include_in_search(r.get("payload", {}))]

        # ---- 过滤孤立向量（book_id 不存在于 SQLite 的结果）----
        # 收集所有结果中涉及的 book_id，批量查询数据库
        result_book_ids = set()
        for r in search_results:
            bid = r.get("payload", {}).get("book_id")
            if bid:
                result_book_ids.add(bid)
        
        if result_book_ids:
            existing_book_ids = set(
                row[0] for row in db.query(PdfBook.id).filter(PdfBook.id.in_(result_book_ids)).all()
            )
            # 过滤掉 book_id 存在但不在数据库中的结果
            # 注意：没有 book_id 的结果（如花鸟教程章节）保留
            search_results = [
                r for r in search_results
                if not r.get("payload", {}).get("book_id") 
                or r.get("payload", {}).get("book_id") in existing_book_ids
            ]

        # ---- ③ AI 摘要回答（带缓存）----
        # 缓存 key 包含 query + book_ids，不同书库过滤结果不同
        book_ids_str = ",".join(sorted(request.book_ids)) if request.book_ids else "all"
        query_key = f"{re.sub(r'\\s+', '', request.query).lower()}|{book_ids_str}"
        
        cached = db.query(SummaryCache).filter(SummaryCache.query_key == query_key).first()
        if cached:
            # 缓存命中
            cached.hit_count = (cached.hit_count or 0) + 1
            db.commit()
            # 从缓存的 extra_data 恢复 key_points、related_concepts 和 related_images
            extra = cached.extra_data or {}
            ai_summary = {
                "answer": cached.answer,
                "key_points": extra.get("key_points", []),
                "related_concepts": extra.get("related_concepts", []),
                "confidence": cached.confidence / 100.0,
                "sources": cached.sources or [],
            }
            # 从缓存恢复 related_images（避免重复搜索和跨模态 API 调用）
            cached_related_images = extra.get("related_images", [])
            logger.info("AI 摘要缓存命中: query='%s', hit_count=%d, cached_images=%d", 
                       request.query, cached.hit_count, len(cached_related_images))
        else:
            try:
                ai_summary = await asyncio.wait_for(
                    generate_summary(request.query, search_results), timeout=30.0
                )
                # related_images 将在后面构建，这里先初始化为空
                cached_related_images = None  # 标记需要后续构建
                # 写入缓存在 related_images 构建完成后进行
            except asyncio.TimeoutError:
                logger.warning("AI 摘要超时(30s)，返回空结果")
                ai_summary = {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}
                cached_related_images = None

        # 格式化结果 -  enriched with DB data
        results = []
        # 收集 top 文本结果的关联图片（供 AI 概述区 related_images 使用）
        collected_assoc_images = []  # [{stored_url, display_label, figure_id, ...}]
        seen_assoc_urls = set()
        MAX_RELATED_IMAGES = 6
        for r in search_results:
            payload = r.get("payload", {})
            # 支持多种 book_id 字段名（PDF上传用 book_id，花鸟教程用 book）
            book_id = payload.get("book_id") or payload.get("book")
            vector_id = r.get("id")
            
            # 从数据库获取更完整的信息（仅当 book_id 存在时）
            chunk = None
            if book_id:
                chunk = db.query(TextChunk).filter(
                    TextChunk.book_id == book_id,
                    TextChunk.vector_id == vector_id
                ).first()
            
            # 对于没有数据库记录的向量（如 bird_flower_tutorial 章节/图像），直接从 payload 提取信息
            if not chunk:
                # 检查是否是 bird_flower_tutorial 类型的数据
                if payload.get("type") == "chapter" or payload.get("source") == "bird_flower_tutorial":
                    # 直接从 payload 构建结果
                    raw_content = payload.get("content", "") or payload.get("text_preview", "")
                    truncated_content = _truncate_to_sentence_boundary(raw_content, 200, direction="head")
                    
                    results.append({
                        "chunk_id": None,
                        "vector_id": vector_id,
                        "book_id": book_id,
                        "book_title": _extract_book_title(payload),
                        "content": truncated_content,
                        "content_full": raw_content,
                        "chapter_title": payload.get("chapter_title", ""),
                        "page_start": payload.get("page_start", 0),
                        "page_end": payload.get("page_end", 0),
                        "chunk_index": 0,
                        "score": r.get("score", 0),
                        "associated_images": [],
                        "context_before": "",
                        "context_after": "",
                        "has_prev": False,
                        "has_next": False,
                        "bbox": payload.get("bbox"),  # 添加 bbox 字段
                    })
                    continue
                # 检查是否是图像类型的数据（跨模态搜索结果）
                elif payload.get("type") in ("knowledge_figure", "pantianshou_illustration", "pdf_extracted_image"):
                    fig_desc = payload.get("description", "") or payload.get("caption", "")
                    fig_id = payload.get("figure_id", "")
                    artist = payload.get("artist", "")
                    artwork = payload.get("artwork_title", "")
                    # image_url 用于知识库图片，image_path 用于 PDF 提取图片
                    image_url = payload.get("image_url", "")
                    if not image_url:
                        img_path = payload.get("image_path", "")
                        if img_path:
                            if img_path.startswith("/"):
                                image_url = img_path
                            elif img_path.startswith("http"):
                                image_url = img_path
                            else:
                                image_url = f"/api/v1/knowledge/{img_path}"
                    era = payload.get("era", "")
                    chapter = payload.get("chapter", "")
                    # 构建图像搜索结果
                    content_parts = []
                    if artist:
                        content_parts.append(f"作者: {artist}")
                    if artwork:
                        content_parts.append(f"作品: {artwork}")
                    if fig_desc:
                        content_parts.append(fig_desc)
                    content_text = " | ".join(content_parts) if content_parts else f"图 {fig_id}"
                    
                    results.append({
                        "chunk_id": None,
                        "vector_id": vector_id,
                        "book_id": book_id,
                        "book_title": _extract_book_title(payload),
                        "content": content_text[:200],
                        "content_full": content_text,
                        "chapter_title": chapter,
                        "page_start": payload.get("page_number") or payload.get("page", 0),
                        "page_end": payload.get("page_number") or payload.get("page", 0),
                        "chunk_index": 0,
                        "score": r.get("score", 0),
                        "associated_images": [{"url": image_url, "stored_url": image_url, "figure_id": fig_id}] if image_url else [],
                        "context_before": "",
                        "context_after": "",
                        "has_prev": False,
                        "has_next": False,
                        "result_type": "image",  # 标记为图像结果，前端可区分展示
                        "bbox": payload.get("bbox"),  # 添加 bbox 字段
                        # 图像专属字段
                        "image": {
                            "url": image_url,
                            "stored_url": image_url,
                            "figure_id": fig_id,
                            "artist": artist,
                            "artwork_title": artwork,
                            "era": era,
                            "description": fig_desc,
                            "chapter": chapter,
                        },
                    })
                    continue
                else:
                    logger.warning("跳过孤立向量: vector_id=%s, book_id=%s", vector_id, book_id)
                    continue
            
            # 获取关联图片
            associated_images = []
            if chunk and chunk.associated_images:
                images = db.query(ExtractedImage).filter(
                    ExtractedImage.id.in_(chunk.associated_images)
                ).all()
                associated_images = [{
                    "id": img.id,
                    "file_name": img.file_name,
                    "url": img.stored_url,
                    "stored_url": img.stored_url,
                    "page": img.page,
                    "figure_id": img.figure_id,
                    "caption": img.caption,
                    "display_label": _parse_caption_for_display(img.caption) or img.figure_id or f"图{img.page}" if img.page else img.figure_id or "",
                } for img in images]
                
                # 收集关联图片供 AI 概述区 related_images 使用（最多 MAX_RELATED_IMAGES 张）
                for ai in associated_images:
                    url_key = ai.get("stored_url") or ai.get("id")
                    if url_key and url_key not in seen_assoc_urls and len(collected_assoc_images) < MAX_RELATED_IMAGES:
                        seen_assoc_urls.add(url_key)
                        collected_assoc_images.append(ai)
            
            # 获取前后上下文（同章节的相邻块）
            context_before = ""
            context_after = ""
            if chunk:
                prev_chunk = db.query(TextChunk).filter(
                    TextChunk.book_id == book_id,
                    TextChunk.chunk_index == chunk.chunk_index - 1
                ).first()
                next_chunk = db.query(TextChunk).filter(
                    TextChunk.book_id == book_id,
                    TextChunk.chunk_index == chunk.chunk_index + 1
                ).first()
                if prev_chunk:
                    # 智能截取：从末尾截取到最近的句子边界
                    context_before = _truncate_to_sentence_boundary(prev_chunk.content, 200, direction="tail")
                if next_chunk:
                    # 智能截取：从开头截取到最近的句子边界
                    context_after = _truncate_to_sentence_boundary(next_chunk.content, 200, direction="head")
            
            # 智能章节标题
            chapter_title = payload.get("chapter", "")
            if not chapter_title or chapter_title.strip() == "正文":
                # 尝试从内容推断章节
                raw_content = payload.get("content", "")
                ch_match = re.search(r'第[一二三四五六七八九十百千万\d]+章[\s]*[^\n]{2,20}', raw_content)
                if ch_match:
                    chapter_title = ch_match.group(0).strip()
                elif chunk and chunk.page_start:
                    chapter_title = f"第{chunk.page_start}页"
            
            # 对 content 在句子边界截断（用于搜索列表预览）
            raw_content = payload.get("content", "")
            raw_content = _STRIP_LATEX_RE.sub('', raw_content)
            truncated_content = _truncate_to_sentence_boundary(raw_content, 200, direction="head")
            
            results.append({
                "chunk_id": chunk.id if chunk else None,
                "vector_id": vector_id,
                "book_id": book_id,
                "book_title": _extract_book_title(payload),
                "content": truncated_content,
                "content_full": raw_content,  # 完整内容供详情弹窗使用
                "chapter_title": chapter_title,
                "page_start": payload.get("page_start", 0),
                "page_end": payload.get("page_end", 0),
                "chunk_index": chunk.chunk_index if chunk else 0,
                "score": r.get("score", 0),
                "associated_images": associated_images,
                "context_before": context_before,
                "context_after": context_after,
                "has_prev": bool(context_before),
                "has_next": bool(context_after),
                "bbox": payload.get("bbox"),  # 添加 bbox 字段
            })
        
        # 记录搜索历史（相同 query 只保留最新一条）
        existing = db.query(SearchHistory).filter(
            SearchHistory.query == request.query
        ).first()
        if existing:
            existing.created_at = datetime.utcnow()
            existing.result_count = len(results)
            existing.filters = {"book_ids": request.book_ids}
            db.commit()
        else:
            history = SearchHistory(
                query=request.query,
                query_type="text",
                filters={"book_ids": request.book_ids},
                result_count=len(results),
            )
            db.add(history)
            db.commit()
        
        # ai_summary 已在上方通过 await 直接获取

        # 构建相关图像（供 AI 概述区配图展示）
        # 来源优先级：① 文本结果的 associated_images（编辑关联，高相关性）
        #            ② 跨模态向量搜索结果（已过 score_threshold=0.22，需去重补充）
        
        # 缓存命中时直接使用缓存的 related_images，跳过构建和跨模态搜索
        if cached_related_images is not None:
            related_images = cached_related_images
            logger.info("相关配图从缓存恢复: %d 张", len(related_images))
        else:
            related_images = []
            seen_related_urls = set()

            # 来源①：从 collected_assoc_images 转换格式
            for ai in collected_assoc_images:
                url = ai.get("stored_url", "")
                url_key = url or ai.get("id", "")
                if not url_key or url_key in seen_related_urls:
                    continue
                seen_related_urls.add(url_key)
                related_images.append({
                    "url": url,
                    "stored_url": url,
                    "figure_id": ai.get("figure_id", ""),
                    "display_label": ai.get("display_label", ai.get("figure_id", "")),
                    "source": "associated",
                })

            # 来源②：从跨模态搜索结果补充（仅当来源①不足时）
            if len(related_images) < MAX_RELATED_IMAGES:
                for r in search_results:
                    if len(related_images) >= MAX_RELATED_IMAGES:
                        break
                    payload = r.get("payload", {})
                    img_type = payload.get("type")
                    if img_type not in ("knowledge_figure", "pantianshou_illustration", "pdf_extracted_image"):
                        continue
                    # 跳过低分结果（跨模态搜索虽已在 search_collection 过 0.22，此处双保险）
                    score = r.get("score", 0)
                    if score < 0.22:
                        continue
                    img_url = payload.get("image_url", "")
                    if not img_url:
                        image_path = payload.get("image_path", "")
                        if image_path:
                            if image_path.startswith("/") or image_path.startswith("http"):
                                img_url = image_path
                            else:
                                img_url = f"/api/v1/knowledge/{image_path}"
                    if not img_url or img_url in seen_related_urls:
                        continue
                    seen_related_urls.add(img_url)
                    artist = payload.get("artist", "")
                    artwork_title = payload.get("artwork_title", "")
                    era = payload.get("era", "")
                    figure_id = payload.get("figure_id", "")
                    # 构建 display_label
                    if artist and artwork_title:
                        display_label = f"{figure_id} | {era + '·' if era else ''}{artist}《{artwork_title}》" if figure_id else f"{era + '·' if era else ''}{artist}《{artwork_title}》"
                    elif artist:
                        display_label = f"{figure_id} | {era + '·' if era else ''}{artist}" if figure_id else f"{era + '·' if era else ''}{artist}"
                    elif artwork_title:
                        display_label = f"{figure_id} | 《{artwork_title}》" if figure_id else f"《{artwork_title}》"
                    else:
                        display_label = figure_id
                    related_images.append({
                        "url": img_url,
                        "stored_url": img_url,
                        "figure_id": figure_id,
                        "artist": artist,
                        "artwork_title": artwork_title,
                        "era": era,
                        "description": payload.get("description", "") or payload.get("caption", ""),
                        "score": score,
                        "display_label": display_label,
                        "source": "crossmodal",
                    })

            logger.info("相关配图: associated=%d, crossmodal=%d, total=%d",
                        sum(1 for r in related_images if r.get("source") == "associated"),
                        sum(1 for r in related_images if r.get("source") == "crossmodal"),
                        len(related_images))

            # 缓存未命中时：AI 摘要 + related_images 构建完成，写入缓存
            if ai_summary.get("answer"):
                cache_entry = SummaryCache(
                    query_key=query_key,
                    query_original=request.query,
                    answer=ai_summary.get("answer", ""),
                    confidence=int(ai_summary.get("confidence", 0) * 100),
                    sources=ai_summary.get("sources", []),
                    hit_count=0,
                    extra_data={
                        "key_points": ai_summary.get("key_points", []),
                        "related_concepts": ai_summary.get("related_concepts", []),
                        "related_images": related_images,  # 缓存 related_images
                    },
                )
                db.add(cache_entry)
                db.commit()
                logger.info("AI 摘要+配图已缓存: query='%s', images=%d", request.query, len(related_images))

        return {
            "query": request.query,
            "results": results,
            "total": len(results),
            "ai_summary": {
                "answer": _STRIP_LATEX_RE.sub('', ai_summary.get("answer", "")),
                "key_points": ai_summary.get("key_points", []),
                "related_concepts": ai_summary.get("related_concepts", []),
                "confidence": ai_summary.get("confidence", 0),
                "sources": ai_summary.get("sources", []),
            },
            "related_images": related_images,
            "query_rewrite": {
                "rewrites": rewritten_queries,
                "intent": query_intent,
            },
        }
    except Exception as e:
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[Search Error] {error_detail}")
        raise HTTPException(500, f"搜索失败: {str(e)}")


@router.get("/search/history")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取搜索历史
    """
    history = db.query(SearchHistory).order_by(
        SearchHistory.created_at.desc()
    ).limit(limit).all()
    
    return [{
        "id": h.id,
        "query": h.query,
        "query_type": h.query_type,
        "result_count": h.result_count,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    } for h in history]


@router.delete("/search/history/{history_id}")
async def delete_search_history_item(
    history_id: str,
    db: Session = Depends(get_db)
):
    """
    删除单条搜索历史
    """
    history = db.query(SearchHistory).filter(SearchHistory.id == history_id).first()
    if not history:
        raise HTTPException(404, "搜索历史不存在")
    
    db.delete(history)
    db.commit()
    return {"success": True, "message": "已删除"}


@router.delete("/search/history")
async def clear_search_history(
    db: Session = Depends(get_db)
):
    """
    清空所有搜索历史
    """
    db.query(SearchHistory).delete()
    db.commit()
    return {"success": True, "message": "搜索历史已清空"}


# ============ 表格搜索 API ============

class TableSearchRequest(BaseModel):
    """表格搜索请求"""
    query: str
    book_ids: Optional[List[str]] = None
    limit: int = 10


@router.post("/search/tables")
async def search_tables(request: TableSearchRequest, db: Session = Depends(get_db)):
    """
    搜索知识库表格
    
    基于 Qdrant 向量搜索 knowledge_tables 集合
    """
    from .embedding_service import EmbeddingService
    from . import qdrant_client
    
    try:
        embedding_service = EmbeddingService()
        embed_result = await embedding_service.embed_text(request.query)
        if not embed_result:
            raise HTTPException(500, "文本向量化失败")
        
        q_embedding = embed_result.embedding
        
        # 搜索表格集合
        table_results = qdrant_client.search_knowledge_tables(
            vector=q_embedding,
            book_ids=request.book_ids,
            limit=request.limit,
            score_threshold=0.6,
        )
        
        # 格式化结果
        results = []
        for r in table_results:
            payload = r.get("payload", {})
            results.append({
                "vector_id": r.get("id"),
                "score": r.get("score", 0),
                "content": payload.get("content", ""),
                "page": payload.get("page"),
                "chapter_title": payload.get("chapter_title"),
                "book_id": payload.get("book_id"),
                "book_title": payload.get("book_title", ""),
                "table_index": payload.get("table_index"),
                "bbox": payload.get("bbox"),
            })
        
        return {
            "query": request.query,
            "results": results,
            "total": len(results),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("表格搜索失败: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(500, f"表格搜索失败: {str(e)}")


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
            from app.modules.pantianshou_composition.models import TextChunk
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
        "markdown": book.full_md,
        "length": len(book.full_md),
    }


# ============ 统计 API ============

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    获取知识库统计
    """
    # 书籍统计
    book_stats = db.query(PdfBook.status).all()
    book_count = len(book_stats)
    book_status = {}
    for status in ["pending", "processing", "completed", "failed"]:
        book_status[status] = sum(1 for s in book_stats if s[0] == status)
    
    # 任务统计
    task_manager = TaskManager(db)
    task_stats = task_manager.get_task_stats()
    
    # 内容统计
    chunk_count = db.query(TextChunk).count()
    image_count = db.query(ExtractedImage).count()
    
    return {
        "books": {
            "total": book_count,
            "by_status": book_status,
        },
        "tasks": task_stats,
        "contents": {
            "chunks": chunk_count,
            "images": image_count,
        },
    }


# ============ 百炼智能体聊天端点 ============

class ChatRequest(BaseModel):
    """百炼智能体聊天请求"""
    prompt: str
    session_id: Optional[str] = None


@router.post("/chat")
async def bailian_chat(request: ChatRequest):
    """
    百炼智能体聊天 — 流式 SSE 响应
    
    接入阿里云百炼智能体（app_id: b259c13c595445d59bb35efd2afc818f）
    支持多轮对话（通过 session_id 维护上下文）
    流式输出（stream=True, incremental_output=True）
    """
    from .bailian_service import chat_stream

    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    return StreamingResponse(
        chat_stream(request.prompt, request.session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 不缓冲
        },
    )


# ======================================================================
# 构图规则 CRUD API
# ======================================================================

class RuleCreateRequest(BaseModel):
    """创建/更新构图规则请求"""
    rule_id: str  # 如 "KH-01-01"
    rule_name: str
    condition: str
    quantitative_standard: Optional[str] = ""
    weight: int = 50  # 0-100
    category_name: str
    category_code: str
    subcategory_name: Optional[str] = ""
    reference_figures: List[str] = []
    source: str = "manual"


class RuleUpdateRequest(BaseModel):
    """更新构图规则请求（所有字段可选）"""
    rule_name: Optional[str] = None
    condition: Optional[str] = None
    quantitative_standard: Optional[str] = None
    weight: Optional[int] = None
    category_name: Optional[str] = None
    category_code: Optional[str] = None
    subcategory_name: Optional[str] = None
    reference_figures: Optional[List[str]] = None
    is_active: Optional[int] = None


@router.get("/rules")
def list_rules(
    category_code: Optional[str] = Query(None, description="按维度编码筛选"),
    source: Optional[str] = Query(None, description="按来源筛选"),
    is_active: Optional[int] = Query(None, description="按启用状态筛选"),
    db: Session = Depends(get_db),
):
    """获取构图规则列表"""
    query = db.query(CompositionRule)
    if category_code:
        query = query.filter(CompositionRule.category_code == category_code)
    if source:
        query = query.filter(CompositionRule.source == source)
    if is_active is not None:
        query = query.filter(CompositionRule.is_active == is_active)
    
    rules = query.order_by(CompositionRule.category_code, CompositionRule.rule_id).all()
    return {
        "success": True,
        "count": len(rules),
        "rules": [r.to_dict() for r in rules],
    }


@router.get("/rules/categories")
def list_rule_categories(db: Session = Depends(get_db)):
    """获取构图规则维度列表"""
    from sqlalchemy import func
    categories = db.query(
        CompositionRule.category_code,
        CompositionRule.category_name,
        func.count(CompositionRule.id).label("count"),
    ).group_by(
        CompositionRule.category_code, CompositionRule.category_name
    ).order_by(CompositionRule.category_code).all()
    
    return {
        "success": True,
        "categories": [
            {"code": c[0], "name": c[1], "count": c[2]}
            for c in categories
        ],
    }


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """获取单条构图规则"""
    rule = db.query(CompositionRule).filter_by(rule_id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")
    return {"success": True, "rule": rule.to_dict()}


@router.post("/rules")
def create_rule(request: RuleCreateRequest, db: Session = Depends(get_db)):
    """创建构图规则"""
    existing = db.query(CompositionRule).filter_by(rule_id=request.rule_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"规则 {request.rule_id} 已存在")
    
    rule = CompositionRule(
        rule_id=request.rule_id,
        rule_name=request.rule_name,
        condition=request.condition,
        quantitative_standard=request.quantitative_standard,
        weight=request.weight,
        category_name=request.category_name,
        category_code=request.category_code,
        subcategory_name=request.subcategory_name,
        reference_figures=request.reference_figures,
        source=request.source,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    # 清除规则缓存
    from .rule_matcher import clear_db_rules_cache
    clear_db_rules_cache()
    
    return {"success": True, "rule": rule.to_dict()}


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, request: RuleUpdateRequest, db: Session = Depends(get_db)):
    """更新构图规则"""
    rule = db.query(CompositionRule).filter_by(rule_id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")
    
    update_data = request.dict(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    
    db.commit()
    db.refresh(rule)
    
    # 清除规则缓存
    from .rule_matcher import clear_db_rules_cache
    clear_db_rules_cache()
    
    return {"success": True, "rule": rule.to_dict()}


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """删除构图规则"""
    rule = db.query(CompositionRule).filter_by(rule_id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {rule_id} 不存在")
    
    db.delete(rule)
    db.commit()
    
    # 清除规则缓存
    from .rule_matcher import clear_db_rules_cache
    clear_db_rules_cache()
    
    return {"success": True, "message": f"规则 {rule_id} 已删除"}


@router.post("/rules/batch-toggle")
def batch_toggle_rules(
    rule_ids: List[str],
    is_active: int = Query(..., description="1=启用，0=禁用"),
    db: Session = Depends(get_db),
):
    """批量启用/禁用构图规则"""
    updated = db.query(CompositionRule).filter(
        CompositionRule.rule_id.in_(rule_ids)
    ).update({CompositionRule.is_active: is_active}, synchronize_session=False)
    db.commit()
    
    # 清除规则缓存
    from .rule_matcher import clear_db_rules_cache
    clear_db_rules_cache()
    
    return {"success": True, "updated": updated}


@router.get("/figures")
def list_figures(
    figure_type: Optional[str] = Query(None, description="按类型筛选：positive/negative"),
    db: Session = Depends(get_db),
):
    """获取构图插图列表"""
    query = db.query(CompositionFigure)
    if figure_type:
        query = query.filter(CompositionFigure.figure_type == figure_type)
    
    figures = query.order_by(CompositionFigure.figure_id).all()
    return {
        "success": True,
        "count": len(figures),
        "figures": [f.to_dict() for f in figures],
    }


@router.get("/figures/{figure_id}")
def get_figure(figure_id: str, db: Session = Depends(get_db)):
    """获取单个插图信息"""
    figure = db.query(CompositionFigure).filter_by(figure_id=figure_id).first()
    if not figure:
        raise HTTPException(status_code=404, detail=f"插图 {figure_id} 不存在")
    return {"success": True, "figure": figure.to_dict()}


@router.get("/graph")
def get_knowledge_graph():
    """获取知识图谱数据（朝代→画册→技法类型→图例）"""
    import json, re
    from app.core.config import BASE_DIR

    meta_path = os.path.join(BASE_DIR, "data", "knowledge", "figure_metadata.json")
    nodes = {}
    edges = []

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        for fid, fig in metadata.items():
            era = (fig.get("era") or "").strip()
            fig_type = (fig.get("figure_type") or "").strip()
            chapter = (fig.get("chapter") or "").strip()
            artist = (fig.get("artist") or "").strip()
            artwork = (fig.get("artwork_title") or fig.get("title") or "").strip()

            # Map figure_type to Chinese
            type_map = {"artwork": "作品", "technique": "技法", "teaching_illustration": "教学图例",
                        "positive": "正例", "negative": "反例", "unknown": "其他"}
            fig_type_cn = type_map.get(fig_type, fig_type)

            # Parse chapter into book + section
            section = ""
            book = ""
            if "•" in chapter:
                parts = chapter.split("•")
                if len(parts) >= 2:
                    section = parts[0].strip().rstrip(" \u2022")
                    book_raw = parts[-1].strip()
                    if "国美好教材" in book_raw or "写意花鸟画" in book_raw:
                        book = "中国写意花鸟画教程"
                    else:
                        book = book_raw[:20]
            elif chapter:
                section = chapter[:20]

            # Artist node
            if artist:
                akey = f"artist:{artist}"
                nodes.setdefault(akey, {"id": akey, "label": artist, "type": "artist", "era": era, "count": 0})
                nodes[akey]["count"] += 1

            # Artwork node
            if artwork:
                wkey = f"artwork:{artwork}"
                nodes.setdefault(wkey, {"id": wkey, "label": artwork, "type": "artwork"})
                if artist:
                    edges.append({"from": f"artist:{artist}", "to": wkey, "label": "创作"})

            # Era node
            if era:
                ekey = f"era:{era}"
                nodes.setdefault(ekey, {"id": ekey, "label": era, "type": "era", "count": 0})
                nodes[ekey]["count"] += 1

            # Book node
            if book:
                bkey = f"book:{book}"
                nodes.setdefault(bkey, {"id": bkey, "label": book, "type": "book", "count": 0})
                nodes[bkey]["count"] += 1
                if era:
                    edges.append({"from": f"era:{era}", "to": bkey, "label": "所属"})

            # Section node
            if section:
                skey = f"section:{section}"
                label = section[:18].rstrip(" •")
                nodes.setdefault(skey, {"id": skey, "label": label, "type": "section"})
                if book:
                    edges.append({"from": f"book:{book}", "to": skey, "label": "章节"})

            # Figure type node
            if fig_type_cn:
                tkey = f"type:{fig_type}"
                nodes.setdefault(tkey, {"id": tkey, "label": fig_type_cn, "type": "technique", "count": 0})
                nodes[tkey]["count"] += 1
                if section:
                    edges.append({"from": f"section:{section}", "to": tkey, "label": "包含"})
                elif artist and artwork:
                    edges.append({"from": f"artwork:{artwork}", "to": tkey, "label": "类型"})

    return {
        "success": True,
        "nodes": list(nodes.values()),
        "edges": edges,
    }
