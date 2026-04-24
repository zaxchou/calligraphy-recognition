"""
Context Prepending 模块 — 为文本块预填文档上下文

核心思想 (来自 rag-retrieval skill):
- 单独的文本块缺少上下文，导致向量表示不够精确
- 在每个块前面预填所属文档/章节的元信息，提升语义表示质量
- 研究表明可以降低 35% 的检索失败率
- 上下文格式: "[书名 | 章节 | 页码] 原始内容"

示例:
  原始: "用笔宜干不宜湿，墨色要淡雅"
  预填后: "刘海勇《中国写意花鸟画教程》| 第四章 用墨技法 | 第87页 用笔宜干不宜湿，墨色要淡雅"

使用方式:
  在 knowledge_ingest_v2.py 的文本入库流程中，
  对每个 TextChunk 调用 prepend_context() 后再进行向量化。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def prepend_context(
    content: str,
    book_title: Optional[str] = None,
    chapter_title: Optional[str] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
    author: Optional[str] = None,
    extra_context: Optional[str] = None,
    max_context_length: int = 200,
) -> str:
    """为文本块预填文档上下文
    
    Args:
        content: 原始文本块内容
        book_title: 书名
        chapter_title: 章节标题
        page_start: 起始页码
        page_end: 结束页码
        author: 作者
        extra_context: 额外上下文信息
        max_context_length: 上下文前缀的最大长度（避免上下文过长稀释正文）
    
    Returns:
        预填上下文后的文本（用于向量化）
    """
    if not content:
        return content
    
    parts = []
    
    # 书名 + 作者
    if book_title:
        if author:
            parts.append(f"{author}《{book_title}》")
        else:
            parts.append(f"《{book_title}》")
    
    # 章节标题
    if chapter_title:
        parts.append(chapter_title)
    
    # 页码范围
    if page_start is not None:
        if page_end is not None and page_end != page_start:
            parts.append(f"第{page_start}-{page_end}页")
        else:
            parts.append(f"第{page_start}页")
    
    # 额外上下文
    if extra_context:
        parts.append(extra_context)
    
    if not parts:
        return content
    
    context_prefix = " | ".join(parts)
    
    # 限制上下文长度，避免稀释正文内容
    if len(context_prefix) > max_context_length:
        context_prefix = context_prefix[:max_context_length] + "..."
    
    return f"{context_prefix} {content}"


def prepend_context_for_chunk(
    chunk: Dict[str, Any],
    book_info: Optional[Dict[str, Any]] = None,
) -> str:
    """为 TextChunk dict 预填上下文（便捷函数）
    
    Args:
        chunk: 文本块字典，包含 content, chapter_title, page_start, page_end 等
        book_info: 书籍信息字典，包含 title, author 等
    
    Returns:
        预填上下文后的文本
    """
    return prepend_context(
        content=chunk.get("content", ""),
        book_title=(book_info or {}).get("title") or chunk.get("book_title"),
        chapter_title=chunk.get("chapter_title"),
        page_start=chunk.get("page_start"),
        page_end=chunk.get("page_end"),
        author=(book_info or {}).get("author"),
    )


def batch_prepend_context(
    chunks: List[Dict[str, Any]],
    book_info: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """批量预填上下文
    
    Args:
        chunks: 文本块列表
        book_info: 书籍信息
    
    Returns:
        预填上下文后的文本列表
    """
    return [prepend_context_for_chunk(chunk, book_info) for chunk in chunks]


def strip_context_prefix(text: str) -> str:
    """去除上下文前缀，返回原始内容
    
    用于在展示搜索结果时去掉上下文前缀。
    """
    # 查找 " | " 或 "] " 分隔符，取最后一部分
    # 格式: "... | ... | content" 或 "...content"
    separators = [" | ", "] "]
    for sep in separators:
        idx = text.rfind(sep)
        if idx >= 0:
            return text[idx + len(sep):]
    return text
