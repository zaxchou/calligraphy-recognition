"""
知识搜索 API 路由
语义搜索、图片搜索、搜索历史、表格搜索
"""

import os
import re
import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db
from .models import PdfBook, TextChunk, ExtractedImage, SearchHistory, SummaryCache
from app.core.auth import get_optional_user
from app.models.user import User
from .knowledge_books import _parse_caption_for_display

router = APIRouter()

logger = logging.getLogger(__name__)

# 输出安全层：移除 LaTeX 数学标记（处理旧数据中残留的 $...$）
_STRIP_LATEX_RE = re.compile(r'\$\$[^$]*\$\$|\$[^$]*\$|\\(?:begin|end)\{[^}]*\}')


# ============ 数据模型 ============


class SearchRequest(BaseModel):
    query: str
    book_ids: Optional[List[str]] = None
    limit: int = 10
    include_private: bool = False  # Phase 3b: 是否包含私人文档搜索结果


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    chapter_title: Optional[str]
    page_start: Optional[int]
    page_end: Optional[int]
    book_title: Optional[str]
    score: float


# ============ 内容查看 API ============


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
async def get_image(book_id: str, image_name: str, db: Session = Depends(get_db)):
    """
    获取图像文件
    支持两个存储位置：
    1. data/knowledge/books/images/{book_id}/{image_name} (MinerU 解析)
    2. data/uploads/images/{book_id}/{image_name} (PyMuPDF 解析)
    也可仅传 image_id 作为 book_id（单段路径），自动查库定位。
    """
    # 如果 book_id 看起来像 UUID 且 image_name 为空 → 当作 image_id 查库
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


@router.get("/images/{image_id}")
async def get_image_by_id(image_id: str, db: Session = Depends(get_db)):
    """通过 ExtractedImage.id 直接获取图片（兼容旧版前端或用 UUID 作 URL）"""
    from app.modules.pantianshou_composition.models import ExtractedImage
    img = db.query(ExtractedImage).filter(ExtractedImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "图像不存在")
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    path = os.path.join(base_dir, "knowledge", "books", "images", img.book_id, img.file_name)
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    path2 = os.path.join(base_dir, "uploads", "images", img.book_id, img.file_name)
    if os.path.exists(path2):
        return FileResponse(path2, media_type="image/png")
    raise HTTPException(404, "图像文件不存在")


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

    # UUID/哈希类无效标题过滤
    UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    def _valid(t):
        return t and not UUID_RE.match(t)

    # 1. PDF 上传: metadata.book_title
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        book_title = metadata.get("book_title")
        if _valid(book_title):
            return book_title

    # 2. 章节/分类字段
    book = payload.get("book")
    if _valid(book):
        return book

    # 3. 书名字段
    bt = payload.get("book_title")
    if _valid(bt):
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


# 搜索内存缓存（query_key -> {t, data}）
_search_mem_cache = {}


@router.post("/search")
async def search(request: SearchRequest, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    """
    语义搜索 - 基于 Qdrant 向量搜索
    集成 Query 改写 + 混合搜索 + AI 摘要回答
    """
    # 内存缓存（TTL 5 分钟）：相同搜索秒回，完全不走 Qdrant 和 AI
    # Phase 3b: include_private 不缓存（私人结果随用户变化）
    if not request.include_private:
        query_key = f"{re.sub(r'\\s+', '', request.query).lower()}|{','.join(sorted(request.book_ids)) if request.book_ids else 'all'}"
        mem_hit = _search_mem_cache.get(query_key)
        if mem_hit and time.time() - mem_hit["t"] < 300:
            logger.info("搜索内存缓存命中: query='%s'", request.query)
            return mem_hit["data"]

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

        # ---- ②.6 Phase 3b: 私人知识库搜索 ----
        if request.include_private and user is not None:
            try:
                for q in all_queries[:2]:  # 最多2个查询，控制 API 调用
                    embed_result = await embedding_service.embed_text(q)
                    q_embedding = embed_result.embedding if embed_result else None
                    if not q_embedding:
                        continue
                    private_results = qdrant_client.search_private(
                        vector=q_embedding,
                        user_id=user.id,
                        limit=request.limit,
                        score_threshold=0.6,
                    )
                    for r in private_results:
                        vid = r.get("id")
                        if vid and vid not in seen_ids:
                            seen_ids.add(vid)
                            # 标记为私人来源
                            payload = r.get("payload", {})
                            payload["_source"] = "private"
                            payload["_user_id"] = user.id
                            merged_results.append(r)
                logger.info("私人搜索完成: %d 结果", sum(1 for r in merged_results if r.get("payload", {}).get("_source") == "private"))
            except Exception as e:
                logger.warning("私人知识库搜索失败: %s", e)
        search_results = []
        if request.book_ids:
            for r in merged_results:
                book_id = r.get("payload", {}).get("book_id")
                if book_id in request.book_ids:
                    search_results.append(r)
        else:
            search_results = merged_results

        # ---- ?.7 ??????? ----
        try:
            for q in all_queries[:2]:
                embed_result = await embedding_service.embed_text(q)
                q_embedding = embed_result.embedding if embed_result else None
                if not q_embedding:
                    continue
                db_results = qdrant_client.search_knowledge_db(
                    vector=q_embedding,
                    limit=request.limit,
                    score_threshold=0.5,
                )
                for r in db_results:
                    vid = r.get("id")
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        payload = r.get("payload", {})
                        payload["_source"] = "database"
                        merged_results.append(r)
            logger.info("DB??????: %d ?", sum(1 for r in merged_results if r.get("payload", {}).get("_source") == "database"))
        except Exception as e:
            logger.warning("DB??????: %s", e)


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
            source_type = payload.pop("_source", "public")  # Phase 3b: "public" / "private"
            # 支持多种 book_id 字段名（PDF上传用 book_id，花鸟教程用 book）
            # 私人文档用 document_id
            book_id = payload.get("book_id") or payload.get("book") or payload.get("document_id")
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

                    # 查书名
                    bt = _extract_book_title(payload)
                    bid = book_id
                    if not bt or bt == "知识库":
                        try:
                            bk = db.query(PdfBook).filter(PdfBook.id == bid).first()
                            if bk and bk.title:
                                bt = bk.title
                        except Exception:
                            pass

                    results.append({
                        "chunk_id": None,
                        "vector_id": vector_id,
                        "book_id": book_id,
                        "book_title": bt,
                        "content": truncated_content,
                        "content_full": raw_content,
                        "chapter_title": payload.get("chapter_title", ""),
                        "page_start": payload.get("page_start", 0),
                        "page_end": payload.get("page_end", 0),
                        "chunk_index": 0,
                        "score": max(0, min(1.0, r.get("rerank_score", r.get("score", 0)))),
                        "associated_images": [],
                        "context_before": "",
                        "context_after": "",
                        "has_prev": False,
                        "has_next": False,
                        "bbox": payload.get("bbox"),  # 添加 bbox 字段
                        "source": source_type,  # Phase 3b: public / private
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

                    # 查书名
                    img_bt = _extract_book_title(payload)
                    if book_id and (not img_bt or img_bt == "知识库"):
                        try:
                            bk = db.query(PdfBook).filter(PdfBook.id == book_id).first()
                            if bk and bk.title:
                                img_bt = bk.title
                        except Exception:
                            pass

                    results.append({
                        "chunk_id": None,
                        "vector_id": vector_id,
                        "book_id": book_id,
                        "book_title": img_bt,
                        "content": content_text[:200],
                        "content_full": content_text,
                        "chapter_title": chapter,
                        "page_start": payload.get("page_number") or payload.get("page", 0),
                        "page_end": payload.get("page_number") or payload.get("page", 0),
                        "chunk_index": 0,
                        "score": max(0, min(1.0, r.get("rerank_score", r.get("score", 0)))),
                        "associated_images": [{"url": image_url, "stored_url": image_url, "figure_id": fig_id}] if image_url else [],
                        "context_before": "",
                        "context_after": "",
                        "has_prev": False,
                        "has_next": False,
                        "result_type": "image",  # 标记为图像结果，前端可区分展示
                        "bbox": payload.get("bbox"),  # 添加 bbox 字段
                        "source": source_type,  # Phase 3b: public / private
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
                    # 孤立向量：Qdrant 重建后 vector_id 与 SQLite 不匹配，
                    # 直接从 payload 构建结果（含书名、配图、上下文）
                    raw_content = payload.get("content", "") or payload.get("text_preview", "")
                    truncated_content = _truncate_to_sentence_boundary(raw_content, 200, direction="head")

                    # 查书名（孤立向量中的标题可能是 UUID 文件名，用 DB 覆盖）
                    book_title = _extract_book_title(payload)
                    if book_id and (not book_title or book_title == "知识库" or re.match(r'^[0-9a-f]{32}$', book_title)):
                        try:
                            bk = db.query(PdfBook).filter(PdfBook.id == book_id).first()
                            if bk and bk.title:
                                book_title = bk.title
                        except Exception:
                            pass

                    # 查关联图片（按 book_id + 页面范围）
                    assoc_images = []
                    page = payload.get("page_start") or payload.get("page_number") or payload.get("page", 0)
                    if book_id and page:
                        try:
                            page_num = int(page)
                            imgs = db.query(ExtractedImage).filter(
                                ExtractedImage.book_id == book_id,
                                ExtractedImage.page >= page_num - 1,
                                ExtractedImage.page <= page_num + 1,
                            ).limit(4).all()
                            for img in imgs:
                                url = img.stored_url or img.url or ""
                                assoc_images.append({
                                    "id": img.id,
                                    "file_name": img.file_name,
                                    "url": url,
                                    "stored_url": url,
                                    "page": img.page,
                                    "figure_id": img.figure_id,
                                    "caption": img.caption or "",
                                    "display_label": _parse_caption_for_display(img.caption) or img.figure_id or f"图{img.page}" if img.page else "",
                                })
                                # 也收集到 related_images
                                if url and len(collected_assoc_images) < MAX_RELATED_IMAGES and url not in seen_assoc_urls:
                                    seen_assoc_urls.add(url)
                                    collected_assoc_images.append(assoc_images[-1])
                        except Exception:
                            pass

                    # 查相邻 chunk 作为上下文
                    ctx_before = ""
                    ctx_after = ""
                    chunk_idx = payload.get("chunk_index")
                    if book_id and chunk_idx is not None:
                        try:
                            ci = int(chunk_idx)
                            before = db.query(TextChunk).filter(
                                TextChunk.book_id == book_id,
                                TextChunk.chunk_index == ci - 1,
                            ).first()
                            if before:
                                ctx_before = before.content or ""
                            after = db.query(TextChunk).filter(
                                TextChunk.book_id == book_id,
                                TextChunk.chunk_index == ci + 1,
                            ).first()
                            if after:
                                ctx_after = after.content or ""
                        except Exception:
                            pass

                    results.append({
                        "chunk_id": None,
                        "vector_id": vector_id,
                        "book_id": book_id,
                        "book_title": book_title,
                        "content": truncated_content,
                        "content_full": raw_content,
                        "chapter_title": payload.get("chapter_title", "") or payload.get("chapter", ""),
                        "page_start": payload.get("page_start") or payload.get("page_number") or payload.get("page", 0),
                        "page_end": payload.get("page_end") or payload.get("page_number") or payload.get("page", 0),
                        "chunk_index": chunk_idx or 0,
                        "score": max(0, min(1.0, r.get("rerank_score", r.get("score", 0)))),
                        "associated_images": assoc_images,
                        "context_before": ctx_before,
                        "context_after": ctx_after,
                        "has_prev": bool(ctx_before),
                        "has_next": bool(ctx_after),
                        "bbox": payload.get("bbox"),
                        "source": source_type,  # Phase 3b: public / private
                    })
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

            # 关联图片不足时，从邻近 chunk 补充（系统性补齐，所有 PDF 通用）
            if len(associated_images) < 5 and chunk:
                seen_img_ids = {a["id"] for a in associated_images}
                nearby_chunks = db.query(TextChunk).filter(
                    TextChunk.book_id == book_id,
                    TextChunk.chunk_index >= chunk.chunk_index - 3,
                    TextChunk.chunk_index <= chunk.chunk_index + 3,
                    TextChunk.id != chunk.id
                ).order_by(TextChunk.chunk_index).all()
                for nc in nearby_chunks:
                    if len(associated_images) >= 6:
                        break
                    if not nc.associated_images:
                        continue
                    extra_images = db.query(ExtractedImage).filter(
                        ExtractedImage.id.in_(nc.associated_images)
                    ).all()
                    for ei in extra_images:
                        if ei.id in seen_img_ids:
                            continue
                        seen_img_ids.add(ei.id)
                        associated_images.append({
                            "id": ei.id,
                            "file_name": ei.file_name,
                            "url": ei.stored_url,
                            "stored_url": ei.stored_url,
                            "page": ei.page,
                            "figure_id": ei.figure_id,
                            "caption": ei.caption,
                            "display_label": _parse_caption_for_display(ei.caption) or ei.figure_id or f"图{ei.page}" if ei.page else ei.figure_id or "",
                        })

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
                    context_before = _truncate_to_sentence_boundary(_STRIP_LATEX_RE.sub('', prev_chunk.content), 200, direction="tail")
                if next_chunk:
                    # 智能截取：从开头截取到最近的句子边界
                    context_after = _truncate_to_sentence_boundary(_STRIP_LATEX_RE.sub('', next_chunk.content), 200, direction="head")

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
            full_content = _STRIP_LATEX_RE.sub('', payload.get("content", ""))

            # 书名：优先从 SQLite 取（Qdrant payload 可能是旧的 UUID 文件名）
            db_book_title = None
            if book_id:
                try:
                    bk = db.query(PdfBook).filter(PdfBook.id == book_id).first()
                    if bk and bk.title:
                        db_book_title = bk.title
                except Exception:
                    pass
            final_book_title = db_book_title or _extract_book_title(payload)

            results.append({
                "chunk_id": chunk.id if chunk else None,
                "vector_id": vector_id,
                "book_id": book_id,
                "book_title": final_book_title,
                "content": truncated_content,
                "content_full": full_content,  # 完整内容供详情弹窗使用
                "chapter_title": chapter_title,
                "page_start": payload.get("page_start", 0),
                "page_end": payload.get("page_end", 0),
                "chunk_index": chunk.chunk_index if chunk else 0,
                "score": max(0, min(1.0, r.get("rerank_score", r.get("score", 0)))),
                "associated_images": associated_images,
                "context_before": context_before,
                "context_after": context_after,
                "has_prev": bool(context_before),
                "has_next": bool(context_after),
                "bbox": payload.get("bbox"),  # 添加 bbox 字段
                "source": source_type,  # Phase 3b: public / private
            })

        # ---- 内容级去重：同一段文字可能被不同 query/collection 命中，按 (book_id, content_fingerprint) 去重 ----
        seen_content = set()
        deduped_results = []
        for r in results:
            if r.get("result_type") == "image":
                img_url = (r.get("image") or {}).get("url") or (r.get("associated_images") or [{}])[0].get("url", "")
                key = f"img:{img_url}" if img_url else f"img:{r.get('vector_id')}"
            else:
                content_key = (r.get("content") or "")[:80].strip()
                book_id = r.get("book_id", "")
                key = f"txt:{book_id}:{content_key}"
            if key not in seen_content:
                seen_content.add(key)
                deduped_results.append(r)
        logger.info("内容去重: before=%d, after=%d", len(results), len(deduped_results))
        results = deduped_results

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

        _resp_data = {
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
        # 写入内存缓存（TTL 300s），下次同查询秒回
        # Phase 3b: 含私人文档时不写入共享缓存
        if not request.include_private:
            _search_mem_cache[query_key] = {"t": time.time(), "data": _resp_data}
        # Phase 1: 已登录用户附加私有数据（不写入缓存）
        if user:
            _resp_data["user_data"] = {
                "user_id": user.id,
                "role": user.role,
            }
        return _resp_data
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
