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
SYSTEM_PROMPT = """你是「小墨」，一位精通中国画的专业知识助手，专注于写意花鸟画、构图法则、笔墨技法等问题解答。

规则:
1. 基于提供的知识库内容回答问题，引用原文时标注来源编号如 [1]、[2]
2. 搜索结果中有画作/艺术家/印章（标记为【画作】【艺术家】【印章】）时，直接提供链接。链接格式必须为：[点击查看](/tiba/图片ID) 或 [查看详情](/artist/画家名)，其中图片ID是搜索结果中提供的UUID（如 /tiba/abc123-def456），绝对不要用中文作品名作为路径
3. 如果搜索结果足以回答，给出深入、结构化的解释，控制在 1500-2000 字
4. 如果搜索结果不足以完整回答，诚实说明知识库中还缺少哪些方面
5. 使用专业但易懂的语言，体现中国画的专业深度
6. 不要编造搜索结果中没有的信息
7. 使用 Markdown 格式化回答（标题、列表、加粗等），让回答清晰可读
8. 统计类问题时，以搜索结果中实际出现的作品为准（搜索结果列表），不要仅依赖作品统计摘要中的数字
9. 如果用户指出你的回答有误，重新检查搜索结果并纠正，不要坚持错误
10. 你的名字是小墨，如果用户问起，可以用这个名字自我介绍
11. 多轮对话时，注意用户说的"他""这个""那幅"等代词指代的是上一轮讨论的艺术家或作品，务必保持上下文连贯
12. 用户说"还有呢""继续""更多"时，是在要求补充上一轮的回答，不要切换到完全无关的话题
13. 搜索结果中的画作如果包含"缩略图:"行（格式如 `缩略图: /static/thumbnails/xxx.jpg`），必须在该作品介绍末尾用 Markdown 嵌入该图片。格式为 [![作品名](缩略图的URL)](链接的URL)。例如搜索结果有"链接: /tiba/abc"和"缩略图: /static/thumbnails/abc.jpg"时，输出 [![作品名](/static/thumbnails/abc.jpg)](/tiba/abc)。没有"缩略图:"行的作品不要编造图片URL"""


# 画家专家模式 system prompt
ARTIST_EXPERT_PROMPT = """你是「{artist_name}研究专家」，一位专注于{artist_name}研究的学术专家。

规则:
1. 你的知识基于{artist_name}相关的学术文献和研究资料
2. 回答时引用具体文献来源，标注来源编号如 [1]、[2]
3. 给出深入、结构化的解释，控制在 500-800 字
4. 使用专业但易懂的学术语言
5. 不要编造文献中没有的信息
6. 使用 Markdown 格式化回答
7. 如果搜索结果不足以完整回答，诚实说明文献中还缺少哪些方面
8. 用户问到{artist_name}的艺术特色、生平、技法等问题时，优先引用学术文献中的观点和论据"""


# ── 意图分类 + 画家上下文注入（Phase 2）──

import re

_AGGREGATE_KW = re.compile(r'几幅|多少幅|多少张|共画|画过几|数量|总数|统计|有哪些作品|哪些画|有哪些')
_TEMPORAL_KW = re.compile(r'最后几年|晚年|晚期|早期|最近|最后|前期|中期|什么时候|哪个时期')
_KNOWN_ARTISTS = [
    '李鱓', '郑燮', '朱耷', '潘天寿', '刘海勇', '吴昌硕', '齐白石',
    '徐渭', '陈淳', '八大山人', '石涛', '扬州八怪', '文征明', '任伯年',
    '林良', '吕纪', '沈周', '唐寅', '仇英',
]

# 画家名 DB 缓存（name list, expire time）
_artist_cache: Optional[List[str]] = None
_artist_cache_ts: float = 0
_ARTIST_CACHE_TTL = 300  # 5 min


def _detect_intent(query: str) -> str:
    """轻量意图分类（关键词检测，不调 LLM）"""
    if _AGGREGATE_KW.search(query):
        return "aggregate"
    if _TEMPORAL_KW.search(query):
        return "temporal"
    return "normal"


def _extract_artist(query: str) -> Optional[str]:
    """从查询中提取画家名（先查硬编码列表，再查带缓存的 DB）"""
    global _artist_cache, _artist_cache_ts
    for name in _KNOWN_ARTISTS:
        if name in query:
            return name
    # DB 回退（缓存 5 分钟）
    now = time.time()
    if _artist_cache is None or now - _artist_cache_ts > _ARTIST_CACHE_TTL:
        try:
            db = SessionLocal()
            try:
                rows = db.execute(
                    sql_text("SELECT name FROM artists WHERE LENGTH(name) >= 2")
                ).fetchall()
                _artist_cache = [row[0] for row in rows if row[0]]
                _artist_cache_ts = now
            finally:
                db.close()
        except Exception:
            _artist_cache = []
    for name in _artist_cache or []:
        if name in query:
            return name
    return None


def _get_artist_context(artist_name: str, intent: str) -> str:
    """从 SQLite 查询画家统计数据，注入 RAG 上下文

    注意：意象统计用 LIKE 匹配 content 字段（而非 objects_mentioned），
    因为 objects_mentioned 可能不完整，而 content 是完整的索引文本。
    """
    db = SessionLocal()
    parts = []
    try:
        # 基本统计（不限 year IS NOT NULL，避免漏掉 PDF 索引的作品）
        row = db.execute(
            sql_text("SELECT COUNT(*), MIN(year), MAX(year) FROM tubi_analyses WHERE artist = :a"),
            {"a": artist_name},
        ).fetchone()
        if row and row[0]:
            year_info = f"，创作年份 {row[1]}-{row[2]}" if row[1] and row[2] else ""
            parts.append(f"【{artist_name}作品统计】共 {row[0]} 幅{year_info}")

        # 动态年份段：只在有足够年份数据时计算
        if intent in ("temporal", "aggregate") and row and row[0]:
            year_row = db.execute(
                sql_text("SELECT COUNT(*), MIN(year), MAX(year) FROM tubi_analyses WHERE artist = :a AND year IS NOT NULL"),
                {"a": artist_name},
            ).fetchone()
            if year_row and year_row[0] >= 5:
                min_year, max_year = int(year_row[1]), int(year_row[2])
                span = max_year - min_year
                if span > 10:
                    t1 = min_year + span // 3
                    t2 = min_year + 2 * span // 3
                    rows = db.execute(
                        sql_text(
                            "SELECT CASE "
                            "  WHEN year < :t1 THEN :early "
                            "  WHEN year < :t2 THEN :mid "
                            "  ELSE :late END as period, COUNT(*) as cnt "
                            "FROM tubi_analyses WHERE artist = :a AND year IS NOT NULL "
                            "GROUP BY period ORDER BY MIN(year)"
                        ),
                        {"a": artist_name, "t1": t1, "t2": t2,
                         "early": f"早期({min_year}-{t1})", "mid": f"中期({t1}-{t2})", "late": f"晚期({t2}-{max_year})"},
                    ).fetchall()
                    if rows:
                        periods = [f"{r[0]}: {r[1]}幅" for r in rows]
                        parts.append(f"年份分布: {', '.join(periods)}")

        # 意象统计：注释掉，因为 title LIKE 匹配太宽（如题跋含"菊"但非菊花主题的画）
        # 让 LLM 从搜索结果列表中直接统计，更准确
        # if intent == "aggregate":
        #     for obj in ['竹', '梅', '兰', '菊', '荷', '牡丹', '松', '山水']:
        #         ...

        # 情感分布
        rows = db.execute(
            sql_text(
                "SELECT json_extract(content_analysis, '$.combined_sentiment.polarity') as pol, COUNT(*) as cnt "
                "FROM tubi_analyses "
                "WHERE artist = :a AND content_analysis IS NOT NULL "
                "AND json_extract(content_analysis, '$.combined_sentiment.polarity') IS NOT NULL "
                "GROUP BY pol"
            ),
            {"a": artist_name},
        ).fetchall()
        if rows:
            dist = [f"{r[0]}: {r[1]}幅" for r in rows]
            parts.append(f"情感分布: {', '.join(dist)}")

    except Exception as e:
        logger.warning("Artist context query failed: %s", e)
    finally:
        db.close()

    return "\n".join(parts)


async def _search_for_chat(query: str, limit: int = 10, artist_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """执行 Qdrant 搜索，返回相关文本块（复用现有搜索基础设施）"""
    from .embedding_service import EmbeddingService
    from . import qdrant_client
    from .hybrid_search import hybrid_search as do_hybrid_search

    # EmbeddingService 内部已做单例，这里直接复用
    embed_result = await EmbeddingService().embed_text(query)
    q_embedding = embed_result.embedding if embed_result else None
    if not q_embedding:
        return []

    # 构建 Qdrant filter
    query_filter = None
    if artist_id:
        query_filter = {"must": [{"key": "artist_id", "match": {"value": artist_id}}]}

    results = await do_hybrid_search(
        query_text=query,
        query_vector=q_embedding,
        collection=qdrant_client.KNOWLEDGE_TEXTS_COLLECTION,
        limit=limit,
        query_filter=query_filter,
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

    # 合并后混合排序：文献 70% + DB 实体 30%，保证多样性和丰富性
    # 当有 artist_id 时，文献 chunks 优先，并确保每本书至少有 1 条代表性结果
    if artist_id:
        lit_results = [r for r in filtered if r.get('payload', {}).get('artist_id') == artist_id]
        other_results = [r for r in filtered if r.get('payload', {}).get('artist_id') != artist_id]

        # 按 book_title 分组
        from collections import defaultdict
        book_groups = defaultdict(list)
        for r in lit_results:
            bt = r.get('payload', {}).get('book_title', '') or r.get('payload', {}).get('metadata', {}).get('book_title', '') or 'unknown'
            book_groups[bt].append(r)
        for bt in book_groups:
            book_groups[bt].sort(key=lambda r: r.get("score", 0), reverse=True)

        # 第一步：每本书取 top 1 作为代表（保证多样性）
        lit_interleaved = []
        remaining = []
        for bt in sorted(book_groups.keys()):
            lit_interleaved.append(book_groups[bt][0])
            remaining.extend(book_groups[bt][1:])

        # 第二步：剩余文献按分数排序，round-robin 交替填充
        remaining.sort(key=lambda r: r.get("score", 0), reverse=True)
        remaining_by_book = defaultdict(list)
        for r in remaining:
            bt = r.get('payload', {}).get('book_title', '') or 'unknown'
            remaining_by_book[bt].append(r)

        max_remaining = max((len(v) for v in remaining_by_book.values()), default=0)
        for idx in range(max_remaining):
            for bt in sorted(remaining_by_book.keys()):
                if idx < len(remaining_by_book[bt]):
                    lit_interleaved.append(remaining_by_book[bt][idx])

        # DB 实体按分数排序
        other_results.sort(key=lambda r: r.get("score", 0), reverse=True)

        # 混合：文献 7 成 + DB 实体 3 成（目标 12 条）
        total_slots = 12
        lit_slots = max(2, round(total_slots * 0.7))  # 至少 2 条文献
        db_slots = total_slots - lit_slots

        filtered = lit_interleaved[:lit_slots] + other_results[:db_slots]
    else:
        filtered.sort(key=lambda r: r.get("score", 0), reverse=True)
    return filtered


def _extract_book_title(payload: Dict[str, Any]) -> str:
    """从 payload 提取书名（搜索结果和 sources 共用）"""
    metadata = payload.get("metadata") or {}
    if isinstance(metadata, dict):
        raw_title = metadata.get("book_title", "")
        if raw_title and "中国写意花鸟画教程" in raw_title:
            return "写意教程"
        if raw_title:
            return raw_title
    return payload.get("book", "") or payload.get("book_title", "") or "知识库"


def _parse_entity_int_id(eid: str) -> Optional[int]:
    """从 entity_id（如 'artwork-123'）提取整数 ID"""
    try:
        return int(eid.split("-", 1)[1]) if "-" in eid else int(eid)
    except (ValueError, TypeError):
        return None


def _build_rag_context(
    search_results: List[Dict[str, Any]],
    max_items: int = 12,
    max_chars_per_item: int = 500,
) -> tuple:
    """将搜索结果构建为 RAG 上下文，支持 DB 实体和书本片段"""
    # 预查询画作缩略图（entity_id 格式: "artwork-123"，需去掉前缀）
    artwork_ids = []
    for r in search_results[:max_items]:
        payload = r.get("payload", {})
        if payload.get("source") == "database" and payload.get("type") == "artwork":
            eid = payload.get("entity_id", "")
            if eid:
                int_id = _parse_entity_int_id(eid)
                if int_id is not None:
                    artwork_ids.append(int_id)

    thumb_map: Dict[int, str] = {}
    if artwork_ids:
        try:
            db = SessionLocal()
            try:
                param_dict = {f"id{i}": v for i, v in enumerate(artwork_ids)}
                placeholders = ",".join([f":id{i}" for i in range(len(artwork_ids))])
                rows = db.execute(
                    sql_text(f"SELECT id, thumbnail_path FROM tubi_analyses WHERE id IN ({placeholders})"),
                    param_dict,
                ).fetchall()
                for row in rows:
                    if row[1]:
                        fn = row[1].replace("\\", "/").split("/")[-1]
                        thumb_map[row[0]] = f"/static/thumbnails/{fn}"
            finally:
                db.close()
        except Exception as e:
            logger.warning("Thumbnail lookup failed: %s", e)

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

            # 画作附加缩略图
            if entity_type == "artwork":
                eid = payload.get("entity_id", "")
                int_id = _parse_entity_int_id(eid)
                if int_id is not None:
                    thumb_url = thumb_map.get(int_id, "")
                else:
                    thumb_url = ""
                if thumb_url:
                    part += f"\n缩略图: {thumb_url}"

            part += f"\n{content}"
            parts.append(part)
            continue

        # 书本片段
        book_title = _extract_book_title(payload)
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

    return "\n\n".join(parts), thumb_map


def _build_messages(
    query: str,
    rag_context: str,
    history: Optional[List[Dict[str, str]]] = None,
    artist_name: Optional[str] = None,
) -> List[Dict[str, str]]:
    """构建发送给 LLM 的完整消息列表"""
    if artist_name:
        system_prompt = ARTIST_EXPERT_PROMPT.format(artist_name=artist_name)
    else:
        system_prompt = SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]

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
    artist_id: Optional[int] = None,
    artist_name: Optional[str] = None,
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

    # ① 搜索 Qdrant — 追问时补充上一轮主题词
    t0 = time.time()
    search_query = query
    if history:
        # 从历史中提取最近的用户问题主题词
        last_user_q = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_q = msg.get("content", "")
                break
        # 短追问（<20字）或含代词时，合并上一轮问题作为搜索词
        has_pronoun = any(w in query for w in ['他','她','它','这个','那个','还有','继续','更多','那幅','这幅'])
        if last_user_q and (len(query) < 20 or has_pronoun):
            search_query = f"{last_user_q} {query}"
            logger.info("[RAG聊天] 追问补充搜索: '%s'", search_query[:60])

    try:
        search_results = await _search_for_chat(search_query, limit=10, artist_id=artist_id)
    except Exception as e:
        logger.error("RAG 聊天搜索失败: %s", e, exc_info=True)
        search_results = []

    search_elapsed = time.time() - t0
    logger.info(
        "[RAG聊天] 搜索完成: query='%s', results=%d, 耗时=%.2fs",
        query[:50], len(search_results), search_elapsed,
    )

    # ② 构建 RAG 上下文
    rag_context, thumb_map = _build_rag_context(search_results)
    if not rag_context.strip():
        msg = "抱歉，未在知识库中找到相关信息。请尝试换个关键词或更具体的问题。"
        yield _sse_event("text", {"content": msg})
        yield _sse_event("done", {"sources": [], "session_id": session_id})
        # 保存本轮消息（即使无搜索结果，也要记录对话）
        if user_id is not None and session_id is not None:
            _save_chat_messages(user_id, session_id, query, msg, [])
        return

    # ②.5 意图分类 + 画家上下文注入
    intent = _detect_intent(query)
    if not artist_id:  # 非画家专家模式时，从查询中提取画家名
        extracted = _extract_artist(query)
        if extracted:
            artist_name = extracted
    if intent != "normal" and artist_name:
        artist_ctx = _get_artist_context(artist_name, intent)
        if artist_ctx:
            rag_context = f"{artist_ctx}\n\n{rag_context}"
            logger.info("[RAG聊天] 画家上下文注入: artist=%s, intent=%s", artist_name, intent)

    # ③ 构建完整消息
    messages = _build_messages(query, rag_context, history, artist_name=artist_name)

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
        "max_tokens": 4096,
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

    # ⑤ 构建来源列表（和 RAG context 保持一致的条数）
    sources = []
    for i, r in enumerate(search_results[:12], 1):
        payload = r.get("payload", {})
        source = payload.get("source", "")

        # DB 实体（画作/艺术家/印章）
        if source == "database":
            entity_type = payload.get("type", "")
            name = payload.get("name", "") or payload.get("title", "")
            url = payload.get("url", "")
            artist = payload.get("artist", "")
            type_label = {"artwork": "画作", "artist": "艺术家", "seal": "印章"}.get(entity_type, "实体")
            slot = {
                "index": i,
                "book": f"{type_label}: {name}" + (f" — {artist}" if artist else ""),
                "page": 0,
                "chapter": "",
                "snippet": (payload.get("content", "") or "")[:120],
                "_source": "database",
                "type": entity_type,
                "url": url,
                "name": name,
            }
            # 画作附缩略图
            if entity_type == "artwork":
                eid = payload.get("entity_id", "")
                int_id = _parse_entity_int_id(eid)
                if int_id is not None:
                    slot["thumbnail_url"] = thumb_map.get(int_id, "")
            sources.append(slot)
            continue

        # 书本片段
        book_title = _extract_book_title(payload)
        page = payload.get("page_start", 0)
        chapter = payload.get("chapter", "") or payload.get("chapter_title", "")
        snippet = (payload.get("content", "") or "")[:120]

        # 拼接详细引用标签：书名 + 页码 + 章节
        label = book_title
        if page:
            label += f" 第{page}页"
        if chapter and chapter.strip() and chapter.strip() != "正文":
            label += f"（{chapter.strip()}）"

        slot = {
            "index": i,
            "book": label,
            "page": page,
            "chapter": chapter.strip() if chapter and chapter.strip() != "正文" else "",
            "snippet": snippet,
        }
        sources.append(slot)

    yield _sse_event("done", {
        "sources": sources,
        "session_id": session_id,
    })

    # ⑥ 持久化消息到数据库（异步，不阻塞流式）
    if user_id is not None and session_id is not None and total_text:
        import asyncio
        await asyncio.to_thread(_save_chat_messages, user_id, session_id, query, total_text, sources)


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
