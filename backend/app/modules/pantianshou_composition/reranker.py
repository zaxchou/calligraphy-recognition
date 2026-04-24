"""
Reranking 模块 — 搜索结果精排

核心思想 (来自 rag-retrieval skill):
- 先用向量/BM25 粗排 N 条（如 30 条）
- 再用 LLM 或 Cross-Encoder 精排到 K 条（如 10 条）
- 精排模型考虑 query-document 的交互特征，而非独立的向量相似度
- 召回率可提升 20-40%，尤其对复杂查询效果显著

由于我们没有独立的 cross-encoder 模型，这里用两种策略:
1. LLM-based rerank: 调用 Qwen VL 对 query-context 对进行打分
2. Heuristic rerank: 基于规则的启发式精排（快速、免费）

注意: LLM rerank 会增加 API 调用开销，建议仅在高价值场景使用。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def heuristic_rerank(
    query: str,
    results: List[Dict[str, Any]],
    top_k: int = 10,
    content_field: str = "content",
) -> List[Dict[str, Any]]:
    """启发式精排
    
    基于多个信号对搜索结果重新排序:
    1. 原始向量相似度（来自 Qdrant）
    2. 关键词命中率（query 中的词在结果中出现多少）
    3. 位置奖励（结果中的关键词出现位置越前越好）
    4. 长度奖励（适中的长度更好，太短缺乏信息，太长可能不相关）
    5. 章节相关性（如果有章节信息）
    
    Args:
        query: 用户查询文本
        results: 搜索结果列表（来自 hybrid_search 或 vector search）
        top_k: 精排后返回的数量
        content_field: payload 中内容字段的键名
    
    Returns:
        精排后的结果列表
    """
    if not results or not query:
        return results[:top_k]
    
    # 提取查询关键词
    import re
    query_terms = set()
    # 中文单字和词组
    zh_terms = re.findall(r'[\u4e00-\u9fff]{1,4}', query)
    query_terms.update(zh_terms)
    # 英文词
    en_terms = re.findall(r'[a-zA-Z]{2,}', query.lower())
    query_terms.update(en_terms)
    # 数字
    num_terms = re.findall(r'[0-9]+', query)
    query_terms.update(num_terms)
    
    if not query_terms:
        return results[:top_k]
    
    # ---- 检测 query 是否为专有名词（短查询 + 高 IDF 特征）----
    # 专有名词特征：中文 ≥2 字且 ≤6 字，或英文词组合
    zh_chars = re.findall(r'[\u4e00-\u9fff]', query)
    is_proper_noun = (
        2 <= len(zh_chars) <= 6 and       # 短中文查询
        not re.search(r'[怎么如何什么为什么哪哪里多少]', query)  # 不包含疑问词
    )

    # 专有名词模式：命中权重大幅提升，原始分数权重降低
    if is_proper_noun:
        w_original = 0.10
        w_hit = 0.50
        w_position = 0.25
        w_length = 0.05
        w_chapter = 0.10
    else:
        w_original = 0.30
        w_hit = 0.30
        w_position = 0.20
        w_length = 0.10
        w_chapter = 0.10

    logger.debug("reranker: is_proper_noun=%s, query='%s'", is_proper_noun, query)

    scored_results = []
    for result in results:
        payload = result.get("payload", {})
        content = payload.get(content_field, "") or ""
        
        # 1. 原始分数（归一化）
        original_score = result.get("score", 0) or result.get("fusion_meta", {}).get("vector_score", 0)
        
        # 2. 关键词命中率
        content_lower = content.lower()
        hit_count = sum(1 for term in query_terms if term.lower() in content_lower)
        hit_rate = hit_count / len(query_terms) if query_terms else 0
        
        # 专有名词模式：完整命中 query 有额外加分
        exact_match_bonus = 0.0
        if is_proper_noun:
            if query in content:
                exact_match_bonus = 1.0  # 完整匹配直接拉满
            # 检查 payload 其他字段（chapter, title 等）
            meta_text = " ".join([
                payload.get("chapter", ""),
                payload.get("metadata", {}).get("book_title", "") if isinstance(payload.get("metadata"), dict) else "",
            ])
            if query in meta_text and query not in content:
                exact_match_bonus = 0.7  # 元数据中命中也加分
        
        # 3. 位置奖励：关键词越靠前分数越高
        first_hit_pos = len(content)
        for term in query_terms:
            pos = content_lower.find(term.lower())
            if 0 <= pos < first_hit_pos:
                first_hit_pos = pos
        position_score = max(0, 1.0 - first_hit_pos / max(len(content), 1))
        
        # 4. 长度奖励：100-1000 字符最佳
        content_len = len(content)
        if content_len < 100:
            length_score = content_len / 100 * 0.5
        elif content_len <= 1000:
            length_score = 1.0
        else:
            length_score = max(0.5, 1.0 - (content_len - 1000) / 2000)
        
        # 5. 章节相关性
        chapter_score = 0
        chapter = payload.get("chapter", "")
        if chapter:
            chapter_hit = sum(1 for term in query_terms if term in chapter)
            chapter_score = chapter_hit / len(query_terms) * 0.3
        
        # 综合分数
        final_score = (
            original_score * w_original +
            hit_rate * w_hit +
            position_score * w_position +
            length_score * w_length +
            chapter_score * w_chapter +
            exact_match_bonus * 0.3  # 额外加分（专有名词模式才生效）
        )
        
        scored_results.append((final_score, result))
    
    # 按综合分数排序
    scored_results.sort(key=lambda x: -x[0])
    
    # ---- 动态阈值过滤 ----
    # 策略：取 top-1 分数的一定比例作为阈值，如果 top-1 本身就很低则不过滤
    if scored_results:
        top_score = scored_results[0][0]
        # 阈值 = top_score * 0.25，最低不低于 0.05
        dynamic_threshold = max(top_score * 0.25, 0.05)
        before_count = len(scored_results)
        scored_results = [(s, r) for s, r in scored_results if s >= dynamic_threshold]
        filtered_count = before_count - len(scored_results)
        if filtered_count > 0:
            logger.info("动态阈值过滤: 阈值=%.3f, 移除 %d 条低分结果", dynamic_threshold, filtered_count)
    
    # 添加 rerank 分数到结果
    out = []
    for rank, (score, result) in enumerate(scored_results[:top_k]):
        enriched = dict(result)
        enriched["rerank_score"] = score
        enriched["rerank_rank"] = rank + 1
        out.append(enriched)
    
    return out


async def llm_rerank(
    query: str,
    results: List[Dict[str, Any]],
    top_k: int = 5,
    content_field: str = "content",
) -> List[Dict[str, Any]]:
    """LLM 精排 — 使用 Qwen API 对结果进行语义相关性打分
    
    成本较高，建议仅在最终结果展示时使用。
    
    Args:
        query: 用户查询
        results: 搜索结果列表
        top_k: 精排后返回的数量
        content_field: payload 中内容字段的键名
    
    Returns:
        精排后的结果列表
    """
    if not results or not query:
        return results[:top_k]
    
    # 先用启发式精排缩减候选集
    candidates = heuristic_rerank(query, results, top_k=min(len(results), top_k * 3), content_field=content_field)
    
    if not candidates:
        return []
    
    try:
        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.QWEN_API_KEY or settings.DASHSCOPE_API_KEY
        if not api_key:
            logger.warning("LLM rerank: API Key 未配置，回退到启发式精排")
            return heuristic_rerank(query, results, top_k, content_field)
        
        import httpx
        
        # 构建 prompt
        context_parts = []
        for i, r in enumerate(candidates[:10]):
            content = r.get("payload", {}).get(content_field, "") or ""
            snippet = content[:300]
            context_parts.append(f"[文档{i+1}] {snippet}")
        
        prompt = f"""请根据以下查询，对文档列表进行相关性评分（0-10分）。

查询：{query}

文档列表：
{chr(10).join(context_parts)}

请按以下格式输出，每行一个文档编号和分数：
文档编号:分数

只输出最相关的 {top_k} 个文档，按相关性从高到低排列。"""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen3.5-plus",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 200,
                    "enable_thinking": settings.QWEN_THINKING_ENABLED,
                }
            )
            
            if response.status_code != 200:
                logger.warning("LLM rerank API 失败: %d", response.status_code)
                return heuristic_rerank(query, results, top_k, content_field)
            
            data = response.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 解析 LLM 输出
            import re
            rankings = []
            for line in text.strip().split("\n"):
                m = re.match(r"文档(\d+)[：:]\s*(\d+(?:\.\d+)?)", line.strip())
                if m:
                    doc_idx = int(m.group(1)) - 1  # 转为 0-based
                    score = float(m.group(2))
                    if 0 <= doc_idx < len(candidates):
                        rankings.append((doc_idx, score))
            
            if rankings:
                # 按分数排序
                rankings.sort(key=lambda x: -x[1])
                out = []
                for rank, (idx, score) in enumerate(rankings[:top_k]):
                    enriched = dict(candidates[idx])
                    enriched["llm_rerank_score"] = score
                    enriched["llm_rerank_rank"] = rank + 1
                    out.append(enriched)
                return out
            
            # 解析失败，回退
            return heuristic_rerank(query, results, top_k, content_field)
            
    except Exception as e:
        logger.error("LLM rerank 异常: %s，回退到启发式精排", e)
        return heuristic_rerank(query, results, top_k, content_field)
