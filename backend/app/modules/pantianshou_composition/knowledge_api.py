"""
知识管理 API 路由
提供 PDF 上传、任务管理、搜索等功能
"""

import os
import json
import uuid
import asyncio
from datetime import datetime
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .models import PdfBook, TextChunk, ExtractedImage, CompositionRule, CompositionFigure

from app.core.auth import require_admin_role, get_current_user
from app.core.quota import check_ai_quota
from app.models.user import User

router = APIRouter()

# 子模块路由注册
from .knowledge_tasks import router as tasks_router
router.include_router(tasks_router, tags=["tasks"])

from .knowledge_books import router as books_router
router.include_router(books_router, tags=["books"])

from .knowledge_search import router as search_router
router.include_router(search_router, tags=["search"])

from .artist_literature import router as literature_router
router.include_router(literature_router, tags=["artist-literature"])

logger = logging.getLogger(__name__)


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


# ======================================================================
# Phase 3a: 私人文档上传与管理 API
# ======================================================================

# 私人文档存储目录
_PRIVATE_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "user_documents")
os.makedirs(_PRIVATE_UPLOAD_DIR, exist_ok=True)


class PrivateDocumentResponse(BaseModel):
    """私人文档响应模型"""
    id: str
    title: Optional[str]
    file_name: str
    status: str  # processing / completed / failed
    total_chunks: int = 0
    created_at: str
    visibility: str = "private"


@router.post("/documents")
async def upload_private_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _q=Depends(check_ai_quota),
):
    """
    上传私人 PDF 文档（Phase 3a）

    鉴权：必须登录。免费用户返回 403。
    文件保存到 data/user_documents/{user_id}/ 目录。
    异步处理：PyMuPDF 提取→分块→embedding→Qdrant knowledge_private。
    """
    # 免费用户禁止上传
    if user.subscription_tier == "free":
        raise HTTPException(403, "升级Pro后可上传文档")

    # 验证文件类型
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "只支持 PDF 文件")

    # 创建用户目录
    user_dir = os.path.join(_PRIVATE_UPLOAD_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    safe_name = file_id + "_" + file.filename
    file_path = os.path.join(user_dir, safe_name)

    # 保存文件
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(file_path)

    # 更新用户存储配额
    db_user = db.query(User).filter(User.id == user.id).first()
    if db_user:
        db_user.storage_used_bytes = (db_user.storage_used_bytes or 0) + file_size

    # 创建书籍记录
    doc_title = title or os.path.splitext(file.filename)[0]
    book = PdfBook(
        id=file_id,
        file_name=safe_name,
        stored_path=file_path,
        stored_url=f"/api/v1/knowledge/documents/{file_id}/pdf",
        title=doc_title,
        status="processing",
        owner_id=user.id,
        visibility="private",
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    # 启动后台线程处理
    import threading

    def _run_process():
        try:
            from .private_ingest import process_private_pdf_sync
            result = process_private_pdf_sync(
                pdf_path=file_path,
                book_id=file_id,
                user_id=user.id,
                db=None,  # 在线程内自行创建 session
                title=doc_title,
            )
            if result.get("status") == "failed":
                logger.error("私人文档处理失败: %s", result.get("error"))
        except Exception as e:
            import traceback
            logger.error("私人文档后台线程异常: %s\n%s", e, traceback.format_exc())
            # 更新状态为 failed
            from .database import SessionLocal
            try:
                with SessionLocal() as s:
                    bk = s.query(PdfBook).filter(PdfBook.id == file_id).first()
                    if bk:
                        bk.status = "failed"
                        s.commit()
            except Exception:
                pass

    thread = threading.Thread(target=_run_process, daemon=True)
    thread.start()

    return {
        "document_id": file_id,
        "status": "processing",
        "message": "PDF 上传成功，正在处理中",
    }


@router.get("/documents")
async def list_private_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取当前用户的私人文档列表（Phase 3a）
    """
    books = (
        db.query(PdfBook)
        .filter(PdfBook.owner_id == user.id, PdfBook.visibility == "private")
        .order_by(PdfBook.created_at.desc())
        .all()
    )

    results = []
    for b in books:
        chunk_count = db.query(TextChunk).filter(
            TextChunk.book_id == b.id, TextChunk.owner_id == user.id
        ).count()
        results.append({
            "id": b.id,
            "title": b.title or b.file_name,
            "file_name": b.file_name,
            "status": b.status,
            "total_chunks": chunk_count,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "visibility": b.visibility or "private",
        })

    return results


@router.get("/documents/{document_id}/chunks")
async def get_private_document_chunks(
    document_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    获取私人文档的文本块预览（Phase 3a）
    """
    # 验证所有权
    book = db.query(PdfBook).filter(
        PdfBook.id == document_id, PdfBook.owner_id == user.id
    ).first()
    if not book:
        raise HTTPException(404, "文档不存在")

    chunks = (
        db.query(TextChunk)
        .filter(TextChunk.book_id == document_id)
        .order_by(TextChunk.chunk_index)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [{
        "id": c.id,
        "chunk_index": c.chunk_index,
        "page_start": c.page_start,
        "page_end": c.page_end,
        "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
        "content_full": c.content,
    } for c in chunks]


@router.delete("/documents/{document_id}")
async def delete_private_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    删除私人文档（Phase 3a）
    级联删除：Qdrant 向量 + text_chunks 行 + 原始文件 + pdf_books 行
    """
    from .qdrant_client import delete_private_document_vectors

    book = db.query(PdfBook).filter(
        PdfBook.id == document_id, PdfBook.owner_id == user.id
    ).first()
    if not book:
        raise HTTPException(404, "文档不存在")

    doc_title = book.title or book.file_name
    logger.info("删除私人文档: %s (id=%s, user=%d)", doc_title, document_id, user.id)

    # 1. 删除 Qdrant 向量
    try:
        delete_private_document_vectors(document_id)
    except Exception as e:
        logger.error("删除私人文档向量失败: %s", e)

    # 2. 删除 SQLite text_chunks 行
    db.query(TextChunk).filter(
        TextChunk.book_id == document_id
    ).delete()

    # 3. 删除磁盘文件
    if book.stored_path and os.path.exists(book.stored_path):
        try:
            os.remove(book.stored_path)
        except Exception as e:
            logger.error("删除私人文档文件失败: %s", e)

    # 4. 删除 pdf_books 行
    db.delete(book)
    db.commit()

    return {"message": f"文档 '{doc_title}' 已删除"}


@router.get("/documents/{document_id}/pdf")
async def get_private_document_pdf(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取私人文档的 PDF 文件"""
    book = db.query(PdfBook).filter(
        PdfBook.id == document_id, PdfBook.owner_id == user.id
    ).first()
    if not book:
        raise HTTPException(404, "文档不存在")

    file_path = book.stored_path
    if not os.path.exists(file_path):
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            raise HTTPException(404, "PDF 文件不存在")
        file_path = abs_path

    import urllib.parse
    ascii_name = urllib.parse.quote(os.path.basename(book.file_name or file_path), safe='_.-')
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{ascii_name}\""}
    )


# ============ RAG 聊天端点（DeepSeek Flash 流式 + 鉴权 + 持久化） ============

class ChatRequest(BaseModel):
    """RAG 聊天请求"""
    prompt: str
    history: Optional[List[Dict[str, str]]] = None
    session_id: Optional[str] = None
    artist_id: Optional[int] = None
    artist_name: Optional[str] = None


@router.post("/chat")
async def rag_chat(request: ChatRequest, user: User = Depends(get_current_user)):
    """
    RAG 聊天 — DeepSeek Flash 流式 SSE 响应（需登录）

    流程:
    1. Qdrant 搜索相关文本块
    2. 构建 RAG 上下文 + 对话历史（从 DB 或前端传入）
    3. DeepSeek Flash 流式生成
    4. SSE 逐字输出
    5. 自动保存消息到数据库

    支持多轮对话：传 session_id 时从 DB 加载历史（防前端篡改）
    """
    from .knowledge_chat import chat_stream as _chat_stream
    from sqlalchemy import text as _sql_text
    from app.core.database import SessionLocal as _SessionLocal

    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    # 会话管理
    session_id = request.session_id
    session_type = 'artist_expert' if request.artist_id else 'global'
    if not session_id:
        # 自动创建新会话
        session_id = str(uuid.uuid4())
        db = _SessionLocal()
        try:
            now = datetime.utcnow()
            db.execute(
                _sql_text(
                    "INSERT INTO chat_sessions (id, user_id, title, message_count, session_type, artist_id, created_at, updated_at) "
                    "VALUES (:id, :uid, :title, 0, :stype, :aid, :now, :now)"
                ),
                {"id": session_id, "uid": user.id, "title": request.prompt[:30], "stype": session_type, "aid": request.artist_id, "now": now},
            )
            db.commit()
        finally:
            db.close()

    # 如果有 session_id，从 DB 加载历史（替代前端传来的 history，防篡改）
    # 同时验证 session 所有权
    history = request.history or []
    if request.session_id:
        db = _SessionLocal()
        try:
            owner = db.execute(
                _sql_text("SELECT user_id FROM chat_sessions WHERE id = :sid"),
                {"sid": session_id},
            ).fetchone()
            if not owner:
                raise HTTPException(status_code=404, detail="会话不存在")
            if owner[0] != user.id:
                raise HTTPException(status_code=403, detail="无权访问此会话")

            rows = db.execute(
                _sql_text(
                    "SELECT role, content FROM chat_messages "
                    "WHERE session_id = :sid ORDER BY token_index LIMIT 20"
                ),
                {"sid": session_id},
            ).fetchall()
            if rows:
                history = [{"role": r[0], "content": r[1]} for r in rows]
        finally:
            db.close()

    return StreamingResponse(
        _chat_stream(request.prompt, history, user_id=user.id, session_id=session_id,
                     artist_id=request.artist_id, artist_name=request.artist_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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


@router.post("/db/reindex")
async def reindex_db_entities(
    type: Optional[str] = Query(None, description="??: artists/artworks/seals, ?????"),
    user: User = Depends(get_current_user),
):
    """?????????? Qdrant???????"""
    if user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="???????")
    
    import asyncio, threading
    
    def _run_reindex():
        import subprocess, sys, os
        backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
        cmd = [sys.executable, "-m", "app.modules.pantianshou_composition.knowledge_ingest_db", "--clear"]
        if type:
            cmd.append(f"--{type}-only")
        
        try:
            result = subprocess.run(cmd, cwd=backend_dir, capture_output=True, text=True, timeout=600)
            return result.stdout + "\n" + result.stderr
        except subprocess.TimeoutExpired:
            return "reindex timed out"
        except Exception as e:
            return str(e)
    
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(None, _run_reindex)
    return {"success": True, "output": output[:2000]}


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
def delete_rule(rule_id: str, db: Session = Depends(get_db), admin=Depends(require_admin_role)):
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
