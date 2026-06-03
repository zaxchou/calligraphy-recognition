"""
知识库 RAG 聊天 — DeepSeek Flash 流式 SSE

替代 bailian_service.py，用 Qdrant 向量搜索 + DeepSeek Flash 实现快速流式问答。

流程:
    用户提问 + 对话历史 → Qdrant 搜索相关文本块 → 构建 RAG 上下文 →
    DeepSeek Flash 流式生成 → SSE 逐字输出
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from sqlalchemy import text as sql_text

from app.core.config import get_settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# 单例 httpx.AsyncClient（复用连接池，避免每次请求建新连接）
_async_client: Optional[httpx.AsyncClient] = None


def _get_async_client() -> httpx.AsyncClient:
    """获取全局 AsyncClient 单例"""
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
    return _async_client

# RAG 聊天 system prompt
SYSTEM_PROMPT = """你是一位精通中国画的专业知识助手，专注于写意花鸟画、构图法则、笔墨技法等问题解答。

规则:
1. 基于提供的知识库内容回答问题，引用原文时标注来源编号如 [1]、[2]
2. 如果搜索结果中有画作/艺术家/印章的实体信息（标记为【画作】【艺术家】【印章】），请直接提供它们的链接地址
3. 如果搜索结果足以回答，给出深入、结构化的解释，控制在 300-600 字
4. 如果搜索结果不足以完整回答，在已有内容基础上诚实说明知识库中还缺少哪些方面
5. 使用专业但易懂的语言，体现中国画的专业深度
6. 不要编造搜索结果中没有的信息
7. 使用 Markdown 格式化回答（标题、列表、加粗等），让回答清晰易读"""


async def _search_for_chat(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """执行 Qdrant 搜索，返回相关文本块（复用现有搜索基础设施）"""
    from .embedding_service import EmbeddingService
    from . import qdrant_client
    from .hybrid_search import hybrid_search as do_hybrid_search

    # EmbeddingService 内部已做单例，这里直接复用
    embed_result = await EmbeddingService().embed_text(query)
    q_embedding = embed_result.embedding if embed_result else None
    if not q_embedding:
        return []

    results = await do_hybrid_search(
        query_text=query,
        query_vector=q_embedding,
        collection=qdrant_client.KNOWLEDGE_TEXTS_COLLECTION,
        limit=limit,
    )

    # 过滤掉非文本内容（章节元数据等）
    filtered = []
    for r in results:
        payload = r.get("payload", {})
        doc_type = payload.get("type", "")
        if doc_type in ("knowledge_chapter", "knowledge_artist", "pantianshou_rule"):
            continue
        filtered.append(r)

    # ---- DB entity search ----
    try:
        db_results = qdrant_client.search_knowledge_db(
            vector=q_embedding,
            limit=limit,
            score_threshold=0.5,
        )
        seen_db_ids = set()
        for r in db_results:
            entity_id = r.get("payload", {}).get("entity_id", "")
            if entity_id and entity_id not in seen_db_ids:
                seen_db_ids.add(entity_id)
                filtered.append(r)
        logger.info("Chat DB search: %d unique entities found", len(seen_db_ids))
    except Exception as e:
        logger.warning("Chat DB search failed: %s", e)

    # 合并后按分数排序（确保 DB 实体和文本结果公平竞争 top-8 位置）
    filtered.sort(key=lambda r: r.get("score", 0), reverse=True)
    return filtered
    except Exception as e:
        logger.warning("Chat DB search failed: %s", e)

    return filtered


def _build_rag_context(
    search_results: List[Dict[str, Any]],
    max_items: int = 8,
    max_chars_per_item: int = 500,
) -> str:
    """将搜索结果构建为 RAG 上下文，支持 DB 实体和书本片段"""
    parts = []
    for i, r in enumerate(search_results[:max_items], 1):
        payload = r.get("payload", {})
        source = payload.get("source", "")

        # DB 实体（画作/艺术家/印章）
        if source == "database":
            entity_type = payload.get("type", "")
            name = payload.get("name", "") or payload.get("title", "")
            url = payload.get("url", "")
            artist = payload.get("artist", "")
            year = payload.get("year", "")
            content = payload.get("content", "")[:max_chars_per_item]

            type_label = {"artwork": "画作", "artist": "艺术家", "seal": "印章"}.get(entity_type, "实体")
            part = f"[{i}] 【{type_label}】{name}"
            if artist:
                part += f" — {artist}"
            if year:
                part += f" ({year}年)"
            if url:
                part += f"\n链接: {url}"
            part += f"\n{content}"
            parts.append(part)
            continue

        # 书本片段
        metadata = payload.get("metadata") or {}
        book_title = ""
        if isinstance(metadata, dict):
            raw_title = metadata.get("book_title", "")
            if raw_title and "中国写意花鸟画教程" in raw_title:
                book_title = "写意教程"
            elif raw_title:
                book_title = raw_title
        if not book_title:
            book_title = payload.get("book", "") or payload.get("book_title", "") or "知识库"

        page = payload.get("page_start", 0)
        chapter = payload.get("chapter", "") or payload.get("chapter_title", "")
        content = payload.get("content", "")

        snippet = content[:max_chars_per_item]
        if len(content) > max_chars_per_item:
            snippet += "..."

        part = f"[{i}] 《{book_title}》"
        if page:
            part += f" 第{page}页"
        if chapter and chapter.strip() and chapter.strip() != "正文":
            part += f"（{chapter.strip()}）"
        part += f":\n{snippet}"
        parts.append(part)

    return "\n\n".join(parts)


def _build_messages(
    query: str,
    rag_context: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """构建发送给 LLM 的完整消息列表"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 添加历史消息（最近 N 轮）
    if history:
        for msg in history[-20:]:  # 最多 10 轮 (20 条消息)
            role = msg.get("role", "user")
            content = msg.get("content", "")[:1000]  # 单条截断防爆
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    # 当前问题 + 上下文
    user_content = f"知识库搜索结果:\n\n{rag_context}\n\n用户问题: {query}\n\n请基于以上知识库内容回答问题。"
    messages.append({"role": "user", "content": user_content})

    return messages


async def chat_stream(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    RAG 聊天流式 SSE 生成器

    1. 搜索 Qdrant 获取相关文本块
    2. 构建 RAG 上下文 + 对话历史
    3. 调用 DeepSeek Flash 流式生成
    4. 逐 token 产出 SSE 事件
    5. 完成后自动保存消息到 chat_messages（如果提供了 user_id + session_id）

    Args:
        query: 用户当前问题
        history: 对话历史 [{"role":"user","content":"..."}, ...]
        user_id: 用户ID（用于持久化）
        session_id: 会话ID（用于持久化）
    """
    settings = get_settings()
    api_key = settings.DEEPSEEK_API_KEY
    base_url = settings.DEEPSEEK_BASE_URL
    model = settings.DEEPSEEK_TEXT_MODEL

    if not api_key:
        yield _sse_event("error", {"message": "DeepSeek API Key 未配置"})
        return

    # ① 搜索 Qdrant
    t0 = time.time()
    try:
        search_results = await _search_for_chat(query, limit=10)
    except Exception as e:
        logger.error("RAG 聊天搜索失败: %s", e, exc_info=True)
        search_results = []

    search_elapsed = time.time() - t0
    logger.info(
        "[RAG聊天] 搜索完成: query='%s', results=%d, 耗时=%.2fs",
        query[:50], len(search_results), search_elapsed,
    )

    # ② 构建 RAG 上下文
    rag_context = _build_rag_context(search_results)
    if not rag_context.strip():
        msg = "抱歉，未在知识库中找到相关信息。请尝试换个关键词或更具体的问题。"
        yield _sse_event("text", {"content": msg})
        yield _sse_event("done", {"sources": [], "session_id": session_id})
        # 保存本轮消息（即使无搜索结果，也要记录对话）
        if user_id is not None and session_id is not None:
            _save_chat_messages(user_id, session_id, query, msg, [])
        return

    # ③ 构建完整消息
    messages = _build_messages(query, rag_context, history)

    # ④ 调用 DeepSeek Flash 流式
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": True,
        "thinking": {"type": "disabled"},
    }

    t_llm = time.time()
    full_text = []

    try:
        client = _get_async_client()
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                error_body = ""
                try:
                    error_body = (await resp.aread()).decode()[:500]
                except Exception:
                    pass
                logger.error(
                    "DeepSeek API 错误: status=%d, body=%s",
                    resp.status_code, error_body,
                )
                yield _sse_event("error", {
                    "message": f"API 调用失败 (HTTP {resp.status_code})",
                })
                return

            first_token = True
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    if first_token:
                        ttft = (time.time() - t_llm) * 1000
                        logger.info(
                            "[RAG聊天] 首 token: query='%s', ttft=%.0fms, "
                            "搜索=%.2fs",
                            query[:50], ttft, search_elapsed,
                        )
                        first_token = False
                    full_text.append(content)
                    yield _sse_event("text", {"content": content})

    except httpx.TimeoutException:
        logger.warning("DeepSeek API 超时")
        yield _sse_event("error", {"message": "请求超时，请重试"})
        return
    except Exception as e:
        logger.error("DeepSeek API 流式调用异常: %s", e, exc_info=True)
        yield _sse_event("error", {"message": f"服务异常: {str(e)}"})
        return

    llm_elapsed = time.time() - t_llm
    total_text = "".join(full_text)
    logger.info(
        "[RAG聊天] 完成: query='%s', tokens=%d, llm=%.2fs, total=%.2fs",
        query[:50], len(total_text), llm_elapsed, time.time() - t0,
    )

    # ⑤ 构建来源列表（先 text 事件发引用卡片，再发 done）
    sources = []
    for i, r in enumerate(search_results[:8], 1):
        payload = r.get("payload", {})
        metadata = payload.get("metadata") or {}
        book_title = ""
        if isinstance(metadata, dict):
            raw_title = metadata.get("book_title", "")
            book_title = "写意教程" if ("写意花鸟画教程" in raw_title) else raw_title
        if not book_title:
            book_title = payload.get("book", "") or payload.get("book_title", "") or "知识库"
        page = payload.get("page_start", 0)
        chapter = payload.get("chapter", "") or payload.get("chapter_title", "")
        snippet = (payload.get("content", "") or "")[:120]

        slot = {
            "index": i,
            "book": book_title,
            "page": page,
            "chapter": chapter.strip() if chapter and chapter.strip() != "正文" else "",
            "snippet": snippet,
        }
        src = payload.get("_source", "")
        if src == "database":
            slot["_source"] = "database"
            slot["type"] = payload.get("type", "")
            slot["url"] = payload.get("url", "")
            slot["name"] = payload.get("name", "") or payload.get("title", "")
        sources.append(slot)

    yield _sse_event("done", {
        "sources": sources,
        "session_id": session_id,
    })

    # ⑥ 持久化消息到数据库
    if user_id is not None and session_id is not None and total_text:
        _save_chat_messages(user_id, session_id, query, total_text, sources)


def _save_chat_messages(user_id: int, session_id: str, user_query: str, assistant_answer: str, sources: list):
    """保存本轮对话到 chat_messages + 更新 chat_sessions"""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # 获取当前最大 token_index
        row = db.execute(
            sql_text("SELECT COALESCE(MAX(token_index), -1) FROM chat_messages WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()
        next_idx = (row[0] or -1) + 1

        # 插入 user 消息
        db.execute(
            sql_text(
                "INSERT INTO chat_messages (id, session_id, role, content, sources, token_index, created_at) "
                "VALUES (:id, :sid, 'user', :content, NULL, :idx, :now)"
            ),
            {"id": str(uuid.uuid4()), "sid": session_id, "content": user_query, "idx": next_idx, "now": now},
        )
        next_idx += 1

        # 插入 assistant 消息
        db.execute(
            sql_text(
                "INSERT INTO chat_messages (id, session_id, role, content, sources, token_index, created_at) "
                "VALUES (:id, :sid, 'assistant', :content, :sources, :idx, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "sid": session_id,
                "content": assistant_answer,
                "sources": json.dumps(sources, ensure_ascii=False) if sources else None,
                "idx": next_idx,
                "now": now,
            },
        )

        # 更新会话：title（首条消息前30字）、message_count、updated_at
        db.execute(
            sql_text(
                "UPDATE chat_sessions SET "
                "title = CASE WHEN message_count = 0 THEN :title ELSE title END, "
                "message_count = message_count + 2, "
                "updated_at = :now "
                "WHERE id = :sid"
            ),
            {"title": user_query[:30], "now": now, "sid": session_id},
        )
        db.commit()
        logger.info("[RAG聊天] 消息已保存: session=%s, user=%d", session_id, user_id)
    except Exception as e:
        db.rollback()
        logger.error("[RAG聊天] 保存消息失败: %s", e, exc_info=True)
    finally:
        db.close()


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
