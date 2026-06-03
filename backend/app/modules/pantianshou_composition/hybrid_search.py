"""
混合搜索模块 — BM25 关键词搜索 + 向量语义搜索 + RRF 融合

核心思想 (来自 rag-retrieval skill):
- BM25 擅长精确关键词匹配（人名、图号、专业术语）
- 向量搜索擅长语义相似度（"笔墨情趣" ≈ "用墨技巧"）
- RRF (Reciprocal Rank Fusion) 融合两者，取长补短
- RRF 公式: score(d) = Σ 1/(k + rank(d))，其中 k=60 是推荐默认值
- 检索失败率可从 5.7% 降到 1.9%（参考数据）

Qdrant 原生支持 BM25 稀疏向量 (Qdrant 1.7+)，
但为兼容现有 Qdrant 1.17.0 版本，这里用内存倒排索引实现 BM25。
"""

from __future__ import annotations

import logging
import math
import os
import pickle
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.modules.pantianshou_composition.qdrant_client import (
    _base_url,
    _get_client,
    _headers,
    scroll_collection,
    search_collection,
)

logger = logging.getLogger(__name__)


class BM25Index:
    """轻量级 BM25 内存索引
    
    用于在 Qdrant 向量搜索之外提供关键词搜索能力。
    索引数据在首次搜索时从 Qdrant 加载并缓存。
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # 词频饱和参数
        self.b = b    # 文档长度归一化
        self._docs: Dict[str, Dict[str, Any]] = {}  # doc_id -> payload
        self._doc_tokens: Dict[str, List[str]] = {}  # doc_id -> token list
        self._doc_tf: Dict[str, Counter] = {}         # doc_id -> term frequency Counter
        self._doc_collection: Dict[str, str] = {}    # doc_id -> collection name
        self._df: Dict[str, int] = defaultdict(int)   # term -> document frequency
        self._avg_dl: float = 0.0
        self._loaded_collections: set = set()
        self._total_docs = 0
    
    def _tokenize(self, text: str) -> List[str]:
        """中文分词：按字符和常见分隔符切分"""
        if not text:
            return []
        # 提取中文词（2-4字组合）+ 英文词 + 数字
        tokens = []
        # 英文词和数字
        en_tokens = re.findall(r'[a-zA-Z]{2,}|[a-zA-Z0-9]+|[0-9]+', text.lower())
        tokens.extend(en_tokens)
        # 中文: 先按标点分割，再提取 2-gram 和 3-gram
        zh_segments = re.split(r'[^\u4e00-\u9fff]+', text)
        for seg in zh_segments:
            if not seg:
                continue
            # 单字
            for char in seg:
                tokens.append(char)
            # 2-gram
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i+2])
            # 3-gram (对短词组更有效)
            for i in range(len(seg) - 2):
                tokens.append(seg[i:i+3])
        return tokens
    
    def _load_collection(self, collection: str) -> bool:
        """从 Qdrant 加载集合数据到内存索引"""
        if collection in self._loaded_collections:
            return True
        
        logger.info("BM25 索引加载集合: %s ...", collection)
        
        offset = None
        loaded_count = 0
        while True:
            result = scroll_collection(
                collection, limit=500, offset=offset,
                with_payload=True, with_vector=False
            )
            points = result.get("points", [])
            if not points:
                break
            
            for pt in points:
                doc_id = str(pt.get("id", ""))
                payload = pt.get("payload", {})
                if not doc_id or not payload:
                    continue
                
                self._docs[doc_id] = payload
                
                # 记录文档所属集合
                self._doc_collection[doc_id] = collection
                
                # 从 payload 提取文本进行分词
                text_parts = []
                # knowledge_texts: content 字段
                if "content" in payload:
                    text_parts.append(payload["content"])
                # composition_rules: rule_name, condition, category
                if "rule_name" in payload:
                    text_parts.append(payload["rule_name"])
                if "condition" in payload:
                    text_parts.append(payload["condition"])
                if "category" in payload:
                    text_parts.append(payload["category"])
                if "subcategory" in payload:
                    text_parts.append(payload["subcategory"])
                if "rule_id" in payload:
                    text_parts.append(payload["rule_id"])
                # composition_cases/knowledge_images: figure_id, description, caption
                if "figure_id" in payload:
                    text_parts.append(payload["figure_id"])
                if "description" in payload:
                    text_parts.append(payload["description"])
                if "caption" in payload:
                    text_parts.append(payload["caption"])
                
                full_text = " ".join(text_parts)
                tokens = self._tokenize(full_text)
                self._doc_tokens[doc_id] = tokens
                self._doc_tf[doc_id] = Counter(tokens)
                
                # 更新文档频率
                seen_terms = set(tokens)
                for term in seen_terms:
                    self._df[term] += 1
                
                loaded_count += 1
            
            offset = result.get("next_page_offset")
            if not offset:
                break
        
        # 计算平均文档长度
        if self._doc_tokens:
            total_len = sum(len(tokens) for tokens in self._doc_tokens.values())
            self._avg_dl = total_len / len(self._doc_tokens)
            self._total_docs = len(self._doc_tokens)
        
        self._loaded_collections.add(collection)
        logger.info("BM25 索引加载完成: 集合=%s, 文档数=%d, 平均长度=%.1f", 
                    collection, loaded_count, self._avg_dl)
        return loaded_count > 0
    
    def _bm25_score(self, term: str, doc_id: str) -> float:
        """计算单个 term 对单个文档的 BM25 分数"""
        tf = self._doc_tf.get(doc_id, Counter()).get(term, 0)
        if tf == 0:
            return 0.0
        
        df = self._df.get(term, 0)
        idf = math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1.0)
        
        dl = len(self._doc_tokens.get(doc_id, []))
        avg_dl = max(self._avg_dl, 1.0)
        
        tf_norm = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / avg_dl))
        
        return idf * tf_norm
    
    def search(self, query: str, collection: str, limit: int = 10) -> List[Dict[str, Any]]:
        """BM25 关键词搜索
        
        Args:
            query: 搜索查询文本
            collection: Qdrant 集合名
            limit: 返回结果数量
        
        Returns:
            排序后的搜索结果列表，每项包含 doc_id, score, payload
        """
        if not self._load_collection(collection):
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        # 计算每个文档的 BM25 分数（只搜索指定集合）
        scores: Dict[str, float] = defaultdict(float)
        for term in query_tokens:
            for doc_id, tokens in self._doc_tokens.items():
                # 只搜索当前集合的文档
                if self._doc_collection.get(doc_id) != collection:
                    continue
                s = self._bm25_score(term, doc_id)
                scores[doc_id] += s
        
        # 按分数排序
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        
        results = []
        for doc_id, score in ranked[:limit]:
            if doc_id in self._docs:
                results.append({
                    "id": doc_id,
                    "score": score,
                    "payload": self._docs[doc_id],
                })
        
        return results
    
    def is_loaded(self, collection: str) -> bool:
        """检查指定集合的 BM25 索引是否已加载
        
        Args:
            collection: 集合名称
            
        Returns:
            是否已加载
        """
        return collection in self._loaded_collections
    
    def invalidate(self, collection: Optional[str] = None):
        """使缓存失效
        
        Args:
            collection: 指定集合，None 表示全部
        """
        if collection:
            if collection in self._loaded_collections:
                # 移除该集合的文档
                self._loaded_collections.discard(collection)
                docs_to_remove = [
                    doc_id for doc_id, payload in self._docs.items()
                    if self._get_collection_hint(payload) == collection
                ]
                for doc_id in docs_to_remove:
                    tokens = self._doc_tokens.pop(doc_id, [])
                    self._doc_tf.pop(doc_id, None)
                    for term in set(tokens):
                        self._df[term] = max(0, self._df[term] - 1)
                    del self._docs[doc_id]
                    self._doc_collection.pop(doc_id, None)
                logger.info("BM25 索引已失效: %s", collection)
        else:
            self._docs.clear()
            self._doc_tokens.clear()
            self._doc_tf.clear()
            self._doc_collection.clear()
            self._df.clear()
            self._loaded_collections.clear()
            self._avg_dl = 0.0
            self._total_docs = 0
            logger.info("BM25 全部索引已失效")
    
    def _get_collection_hint(self, payload: Dict[str, Any]) -> str:
        """从 payload 猜测文档属于哪个集合"""
        if "content" in payload and ("chapter" in payload or "page_start" in payload):
            return "knowledge_texts"
        if "content" in payload and ("name" in payload or "specialties" in payload):
            # Artist profiles also stored in knowledge_texts
            return "knowledge_texts"
        if "rule_id" in payload and "condition" in payload:
            # DEPRECATED: composition_rules is no longer used
            return "composition_rules"
        if "figure_id" in payload and ("figure_type" in payload or "image_url" in payload):
            # All figures now in knowledge_images (was composition_cases or knowledge_figures)
            return "knowledge_images"
        if "book_id" in payload and "caption" in payload:
            return "knowledge_images"
        if "source" in payload and payload.get("source") in ("uploaded_images", "bird_flower_tutorial"):
            return "knowledge_images"
        return "unknown"


# 全局 BM25 索引单例
_bm25_index: Optional[BM25Index] = None

_BM25_CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
_BM25_CACHE_FILE = os.path.join(_BM25_CACHE_DIR, 'bm25_index.pkl')


def _save_bm25_index():
    global _bm25_index
    if _bm25_index is None:
        return
    try:
        os.makedirs(_BM25_CACHE_DIR, exist_ok=True)
        with open(_BM25_CACHE_FILE, 'wb') as f:
            pickle.dump(_bm25_index, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass


def _load_bm25_index() -> Optional[BM25Index]:
    if not os.path.exists(_BM25_CACHE_FILE):
        return None
    try:
        with open(_BM25_CACHE_FILE, 'rb') as f:
            idx = pickle.load(f)
        if isinstance(idx, BM25Index):
            return idx
    except Exception:
        pass
    return None


def get_bm25_index() -> BM25Index:
    """获取全局 BM25 索引（优先从缓存加载）"""
    global _bm25_index
    if _bm25_index is None:
        cached = _load_bm25_index()
        if cached:
            _bm25_index = cached
        else:
            _bm25_index = BM25Index()
    return _bm25_index


def invalidate_bm25_cache(collection: Optional[str] = None):
    """使 BM25 缓存失效并持久化"""
    global _bm25_index
    if _bm25_index:
        _bm25_index.invalidate(collection)
        _save_bm25_index()


def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """RRF (Reciprocal Rank Fusion) 融合向量搜索和 BM25 搜索结果
    
    RRF 公式: score(d) = Σ weight_i / (k + rank_i(d))
    
    Args:
        vector_results: 向量搜索结果 (from search_collection)
        bm25_results: BM25 搜索结果
        k: RRF 常数（越大排名差异影响越小），推荐 60
        vector_weight: 向量搜索权重
        bm25_weight: BM25 搜索权重
        limit: 返回结果数量
    
    Returns:
        融合后的排序结果列表
    """
    scores: Dict[str, float] = defaultdict(float)
    payloads: Dict[str, Dict[str, Any]] = {}
    sources: Dict[str, Dict[str, Any]] = defaultdict(dict)
    
    # 向量搜索贡献
    for rank, result in enumerate(vector_results):
        doc_id = str(result.get("id", ""))
        if not doc_id:
            continue
        scores[doc_id] += vector_weight / (k + rank + 1)
        payloads[doc_id] = result.get("payload", {})
        sources[doc_id]["vector_score"] = result.get("score", 0)
        sources[doc_id]["vector_rank"] = rank + 1
    
    # BM25 搜索贡献
    for rank, result in enumerate(bm25_results):
        doc_id = str(result.get("id", ""))
        if not doc_id:
            continue
        scores[doc_id] += bm25_weight / (k + rank + 1)
        if doc_id not in payloads:
            payloads[doc_id] = result.get("payload", {})
        sources[doc_id]["bm25_score"] = result.get("score", 0)
        sources[doc_id]["bm25_rank"] = rank + 1
    
    # 按 RRF 分数排序
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    
    results = []
    for doc_id, rrf_score in ranked[:limit]:
        entry = {
            "id": doc_id,
            "score": rrf_score,
            "payload": payloads.get(doc_id, {}),
            "fusion_meta": {
                "vector_rank": sources[doc_id].get("vector_rank"),
                "bm25_rank": sources[doc_id].get("bm25_rank"),
                "vector_score": sources[doc_id].get("vector_score"),
                "bm25_score": sources[doc_id].get("bm25_score"),
            },
        }
        results.append(entry)
    
    return results


async def hybrid_search(
    query_text: str,
    query_vector: List[float],
    collection: str,
    limit: int = 10,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
    score_threshold: Optional[float] = None,
    query_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """混合搜索：向量搜索 + BM25 关键词搜索 + RRF 融合
    
    Args:
        query_text: 搜索查询文本（用于 BM25）
        query_vector: 查询向量（用于向量搜索）
        collection: Qdrant 集合名
        limit: 返回结果数量
        vector_weight: 向量搜索权重 (默认 0.6)
        bm25_weight: BM25 搜索权重 (默认 0.4)
        score_threshold: 最低 RRF 分数阈值
        query_filter: Qdrant 过滤条件（仅应用于向量搜索）
    
    Returns:
        融合后的排序结果列表
    """
    # ---- 自适应融合权重 ----
    # 短查询（专有名词/关键词）提高 BM25 权重，长查询（问题/描述）保持向量权重
    actual_vector_weight = vector_weight
    actual_bm25_weight = bm25_weight
    
    zh_chars = re.findall(r'[\u4e00-\u9fff]', query_text)
    is_short_query = (
        len(zh_chars) <= 6 and
        not re.search(r'[怎么如何什么为什么哪哪里多少]', query_text) and
        len(query_text.strip()) <= 12
    )
    
    if is_short_query:
        actual_vector_weight = 0.3
        actual_bm25_weight = 0.7
        logger.debug("自适应权重: 短查询模式, BM25↑=%.1f, vector↓=%.1f", 
                    actual_bm25_weight, actual_vector_weight)

    # 1. 向量搜索（多取一些，融合时排序更准确）
    vector_limit = min(limit * 3, 30)
    vector_results = search_collection(
        collection, query_vector,
        limit=vector_limit,
        query_filter=query_filter,
    )
    
    # 2. BM25 搜索（同步加载索引，确保首次搜索也有 BM25 融合）
    bm25 = get_bm25_index()
    bm25_results = []
    
    # 同步加载 BM25 索引（首次搜索可能需要几秒钟）
    if not bm25.is_loaded(collection):
        logger.info("BM25 索引首次加载: %s ...", collection)
    bm25_limit = min(limit * 3, 30)
    bm25_results = bm25.search(query_text, collection, limit=bm25_limit)
    logger.debug("混合搜索 [%s]: 向量结果=%d, BM25结果=%d", 
                collection, len(vector_results), len(bm25_results))
    
    # 3. RRF 融合
    fused = reciprocal_rank_fusion(
        vector_results=vector_results,
        bm25_results=bm25_results,
        vector_weight=actual_vector_weight,
        bm25_weight=actual_bm25_weight,
        limit=limit,
    )
    
    # 记录融合统计信息
    has_bm25 = any(r.get("fusion_meta", {}).get("bm25_rank") is not None for r in fused[:5])
    logger.info("混合搜索完成 [%s]: query='%s...', 向量=%d条, BM25=%d条, 融合=%d条, BM25生效=%s", 
                collection, query_text[:20], len(vector_results), len(bm25_results), len(fused), has_bm25)
    
    # 4. 分数阈值过滤
    if score_threshold is not None:
        fused = [r for r in fused if r.get("score", 0) >= score_threshold]
    
    return fused
