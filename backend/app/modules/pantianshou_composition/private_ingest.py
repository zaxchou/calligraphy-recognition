"""
Phase 3: 私人文档处理管线
PyMuPDF 提取文本 → jieba 分句 → 500字chunk/50字overlap → DashScope embedding → Qdrant knowledge_private
"""

import os
import re
import hashlib
import uuid
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from .models import PdfBook, TextChunk
from .embedding_service import EmbeddingService
from . import qdrant_client

logger = logging.getLogger(__name__)

# 延迟导入 PyMuPDF 和 jieba（避免启动时加载）
_fitz = None
_jieba = None


def _get_fitz():
    global _fitz
    if _fitz is None:
        import fitz as _fitz
    return _fitz


def _get_jieba():
    global _jieba
    if _jieba is None:
        import jieba as _jieba
    return _jieba


def _extract_text_from_pdf(pdf_path: str) -> str:
    """使用 PyMuPDF 提取 PDF 全文"""
    fitz = _get_fitz()
    doc = fitz.open(pdf_path)
    full_text = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            full_text.append(text.strip())
    doc.close()
    return "\n\n".join(full_text)


def _split_sentences(text: str) -> List[str]:
    """使用 jieba 辅助 + 标点断句"""
    jieba = _get_jieba()
    # 先用标点断句
    raw_sentences = re.split(r'([。！？；\n]+)', text)
    sentences = []
    for part in raw_sentences:
        part = part.strip()
        if not part or re.match(r'^[。！？；\n]+$', part):
            continue
        # 对长句用 jieba 辅助再切分（超过 200 字无条件切）
        if len(part) > 200:
            # 使用 jieba 分词获取词边界，在标点/空格处优雅切分
            words = list(jieba.cut(part))
            current = ""
            for w in words:
                current += w
                if len(current) >= 180 and (w.endswith("，") or w.endswith("、") or w.endswith("；")):
                    sentences.append(current.strip())
                    current = ""
            if current.strip():
                sentences.append(current.strip())
        else:
            sentences.append(part)
    return [s for s in sentences if s]


def _chunk_sentences(sentences: List[str], chunk_size: int = 500, overlap: int = 50) -> List[Dict[str, Any]]:
    """将句子列表拼接为固定大小块（带 overlap）"""
    chunks = []
    idx = 0
    current_chunk = ""
    current_start_sent = 0

    for i, sent in enumerate(sentences):
        if not current_chunk:
            current_chunk = sent
            current_start_sent = i
        elif len(current_chunk) + len(sent) + 1 <= chunk_size:
            current_chunk += "\n" + sent
        else:
            # 保存当前块
            chunks.append({"content": current_chunk, "start_sentence": current_start_sent, "end_sentence": i})
            idx += 1
            # 新块：从上一块末尾回退 overlap 字
            if overlap > 0 and len(current_chunk) > overlap:
                overlap_text = current_chunk[-overlap:]
                # 从 overlap 后的第一个完整句子开始
                current_chunk = overlap_text + "\n" + sent
                current_start_sent = max(current_start_sent, i - 2)
            else:
                current_chunk = sent
                current_start_sent = i

    # 保存最后一块
    if current_chunk.strip():
        chunks.append({"content": current_chunk, "start_sentence": current_start_sent, "end_sentence": len(sentences)})

    # 添加 chunk_index
    for i, c in enumerate(chunks):
        c["chunk_index"] = i + 1

    return chunks


def _estimate_page_range(sentences: List[str], chunk: Dict[str, Any], total_chars: int, total_pages: int) -> (int, int):
    """根据字符位置估算页码范围"""
    if total_pages <= 1:
        return 1, 1
    # 粗略估算：字符位置比例 × 总页数
    chars_before = sum(len(s) for s in sentences[:chunk["start_sentence"]])
    chars_this = sum(len(s) for s in sentences[chunk["start_sentence"]:chunk["end_sentence"]])
    if total_chars <= 0:
        return 1, 1
    page_start = max(1, min(total_pages, int(chars_before / total_chars * total_pages) + 1))
    page_end = max(page_start, min(total_pages, int((chars_before + chars_this) / total_chars * total_pages) + 1))
    return page_start, page_end


def process_private_pdf_sync(
    pdf_path: str,
    book_id: str,
    user_id: int,
    db: Optional[Session] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """同步处理私人 PDF：提取→分块→embedding→存储

    Args:
        pdf_path: PDF 文件路径
        book_id: PdfBook.id (已创建)
        user_id: 用户 ID
        db: 数据库会话（若为 None 则在线程内自行创建）
        title: 自定义标题（可选）

    Returns:
        处理结果统计
    """
    result = {
        "book_id": book_id,
        "status": "success",
        "chunks_created": 0,
        "vectors_written": 0,
        "error": None,
    }

    # 若未传入 db，则自行创建（后台线程场景）
    _own_db = None
    if db is None:
        from .database import SessionLocal
        _own_db = SessionLocal()
        db = _own_db

    try:
        # 1. PDF 提取文本
        logger.info("开始处理私人文档: book_id=%s, user_id=%d", book_id, user_id)
        full_text = _extract_text_from_pdf(pdf_path)
        if not full_text.strip():
            raise ValueError("PDF 未提取到文本内容，可能是扫描版 PDF")

        total_chars = len(full_text)

        # 获取页数
        fitz = _get_fitz()
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()

        # 2. 分句
        sentences = _split_sentences(full_text)
        logger.info("私人文档分句: %d 句, %d 页", len(sentences), total_pages)

        # 3. 分块
        chunks = _chunk_sentences(sentences, chunk_size=500, overlap=50)
        result["chunks_created"] = len(chunks)
        logger.info("私人文档分块: %d 块", len(chunks))

        # 4. 更新书籍信息
        book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
        if book:
            book.total_pages = total_pages
            if title:
                book.title = title
            elif not book.title:
                book.title = os.path.splitext(os.path.basename(pdf_path))[0]
            db.commit()

        # 5. 向量化 + 入库
        embedding_service = EmbeddingService()

        # 确保 private collection 存在
        qdrant_client.ensure_knowledge_collections()

        # 为每个 chunk 添加上下文前缀后批量向量化
        book_title_for_ctx = book.title if book and book.title else "私人文档"
        enriched_texts = [f"[文档: {book_title_for_ctx}] {c['content']}" for c in chunks]
        emb_results = embedding_service.embed_texts_sync(enriched_texts)

        # 配对 (chunk, embedding_result)
        paired = [(c, emb) for c, emb in zip(chunks, emb_results) if emb and emb.embedding is not None]
        if len(paired) < len(chunks):
            logger.warning("部分向量化失败: %d/%d", len(chunks) - len(paired), len(chunks))

        # 6. 写入 SQLite + Qdrant
        chunk_records_and_vectors = []
        for c, emb in paired:
            chunk_record = TextChunk(
                book_id=book_id,
                chunk_index=c["chunk_index"],
                page_start=_estimate_page_range(sentences, c, total_chars, total_pages)[0],
                page_end=_estimate_page_range(sentences, c, total_chars, total_pages)[1],
                content=c["content"],
                content_hash=hashlib.md5(c["content"].encode()).hexdigest(),
                owner_id=user_id,
                visibility="private",
            )
            db.add(chunk_record)
            db.flush()

            vector_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"private_{book_id}_{chunk_record.id}"))
            chunk_records_and_vectors.append({
                "record": chunk_record,
                "vector_id": vector_id,
                "embedding": emb.embedding,
                "chunk": c,
            })

        # 7. 批量写入 Qdrant（在 commit 之前构建 batch）
        batch = []
        for item in chunk_records_and_vectors:
            batch.append({
                "id": item["vector_id"],
                "vector": item["embedding"],
                "content": item["chunk"]["content"],
                "chapter": "",
                "page_start": item["record"].page_start or 1,
                "page_end": item["record"].page_end or 1,
                "chunk_index": item["chunk"]["chunk_index"],
                "book_title": book.title if book else "",
                "metadata": {"book_title": book.title if book else "", "user_id": user_id},
            })

        if batch:
            ok = qdrant_client.upsert_private_chunks(batch, book_id, user_id)
            if ok:
                # 写入成功后更新 vector_id
                for item in chunk_records_and_vectors:
                    item["record"].vector_id = item["vector_id"]
                result["vectors_written"] = len(batch)
            else:
                logger.warning("写入 Qdrant 私人集合失败")

        # 8. 提交 SQLite（含 vector_id 更新）并更新书籍状态
        if book:
            book.status = "completed"
        db.commit()
        # 使搜索缓存失效
        from .hybrid_search import invalidate_bm25_cache
        try:
            invalidate_bm25_cache()
        except Exception:
            pass

        logger.info("私人文档处理完成: book_id=%s, chunks=%d, vectors=%d",
                   book_id, result["chunks_created"], result["vectors_written"])
        return result

    except Exception as e:
        import traceback
        logger.error("私人文档处理失败: %s\n%s", e, traceback.format_exc())
        result["status"] = "failed"
        result["error"] = str(e)
        # 更新状态
        try:
            book = db.query(PdfBook).filter(PdfBook.id == book_id).first()
            if book:
                book.status = "failed"
                db.commit()
        except Exception:
            pass
        return result
    finally:
        if _own_db is not None:
            _own_db.close()
