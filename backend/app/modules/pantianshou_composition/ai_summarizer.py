"""AI 摘要回答模块 — 基于搜索结果生成结构化知识卡片

用 LLM 对搜索结果进行归纳总结，输出结构化的 AI 摘要，
包含要点列表、相关概念和关联图像，帮助用户快速了解知识库中的相关内容。

输出 JSON:
{
    "answer": "综合回答文本",
    "key_points": ["要点1", "要点2", ...],
    "related_concepts": ["概念1", "概念2", ...],
    "confidence": 0.85,
    "sources": [{"book": "书名", "page": 45, "snippet": "关键引用"}]
}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

# UUID 模式，用于过滤无效的哈希标题
_UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
def _valid(t):
    return t and not _UUID_RE.match(t)

import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 模型配置（DeepSeek Flash 优先，Qwen 兜底）
def _get_llm_config() -> tuple:
    """获取 LLM 配置 (api_key, base_url, model) — DeepSeek Flash 优先"""
    from app.services.qwen_llm_client import get_text_llm_config
    return get_text_llm_config()

# 摘要 prompt
SYSTEM_PROMPT = """你是一位精通中国画的专业知识助手。你的任务是基于知识库的搜索结果，为用户的问题生成深入、结构化的知识卡片。

规则:
1. 综合多篇文档给出完整回答，深度提炼书中核心观点和思想，不要只依赖单篇
2. answer 应系统阐述该主题的关键知识，包含理论要点和实践指导，控制在 400-800 字
3. 提取4-8个核心要点，每个要点30-60字，包含具体观点或方法，用 [来源编号] 标注出处
4. 提取3-6个相关概念/术语，帮助用户拓展理解
5. 如果搜索结果不足以完整回答，在已有内容基础上诚实说明知识库中还缺少哪些方面
6. 使用专业但易懂的语言，体现中国画的专业深度
7. 不要编造搜索结果中没有的信息
8. 必须输出合法 JSON，不要输出其他内容

输出格式:
{"answer": "综合回答（400-800字，深入阐述核心观点）", "key_points": ["要点1（含具体观点或方法）[1]", "要点2[2]", ...], "related_concepts": ["概念1", "概念2", ...], "confidence": 0.85, "sources": [{"index": 1, "book": "书名（不加书名号）", "page": 45, "snippet": "关键引用片段"}]}"""


def _parse_summary_response(text: str) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON，容错处理截断、引号等问题"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()

    # 提取 JSON 块（允许截断：没有闭合的 } 也能匹配）
    json_match = re.search(r'\{.*', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    def _ensure_fields(result):
        if "answer" not in result:
            result["answer"] = ""
        if "confidence" not in result:
            result["confidence"] = 0.5
        if "sources" not in result:
            result["sources"] = []
        if not isinstance(result["sources"], list):
            result["sources"] = []
        if "key_points" not in result:
            result["key_points"] = []
        if not isinstance(result["key_points"], list):
            result["key_points"] = []
        if "related_concepts" not in result:
            result["related_concepts"] = []
        if not isinstance(result["related_concepts"], list):
            result["related_concepts"] = []
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        return result

    # 尝试直接解析
    try:
        result = json.loads(text)
        return _ensure_fields(result)
    except json.JSONDecodeError:
        # 容错1：替换中文引号
        text_fixed = text.replace('\u201c', '\\"').replace('\u201d', '\\"')
        try:
            result = json.loads(text_fixed)
            return _ensure_fields(result)
        except json.JSONDecodeError:
            # 容错2：尝试补全截断的 JSON
            # 如果文本以未闭合的状态结束，尝试补全
            if text_fixed.rstrip().endswith(','):
                text_fixed = text_fixed.rstrip()[:-1]
            if not text_fixed.rstrip().endswith('}'):
                text_fixed = text_fixed.rstrip()
                # 尝试补全缺失的闭合
                open_brackets = text_fixed.count('{') - text_fixed.count('}')
                open_brackets += text_fixed.count('[') - text_fixed.count(']')
                text_fixed += ']' * max(0, -open_brackets) if open_brackets < 0 else ''
                text_fixed += '}' * max(0, open_brackets)
            try:
                result = json.loads(text_fixed)
                return _ensure_fields(result)
            except json.JSONDecodeError:
                # 兜底：正则提取 answer 字段
                answer_match = re.search(r'"answer"\s*:\s*"(.+?)"', text, re.DOTALL)
                if answer_match:
                    answer = answer_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                    return {"answer": answer, "key_points": [], "related_concepts": [], "confidence": 0.5, "sources": []}
                logger.warning("AI 摘要 JSON 解析失败, 原文: %.200s", text)
                return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}


def _build_context(results: List[Dict[str, Any]], max_items: int = 12) -> str:
    """将搜索结果构建为 LLM 可读的上下文，包含文本和图像信息
    
    max_items=12: 取更多搜索结果以提供更完整的上下文
    每条文本截取前 1200 字符（原 800），让 LLM 能提取更丰富的核心观点
    """
    parts = []
    for i, r in enumerate(results[:max_items], 1):
        payload = r.get("payload", {})
        doc_type = payload.get("type", "")

        # 图像类型结果：提供描述信息
        if doc_type in ("knowledge_figure", "pantianshou_illustration"):
            artist = payload.get("artist", "")
            artwork = payload.get("artwork_title", "")
            desc = payload.get("description", "") or payload.get("caption", "")
            era = payload.get("era", "")
            parts.append(f"[{i}] 【图像】{era+'·'+artist if era else artist or '未知作者'}《{artwork or '未命名'}》{desc}")
            continue

        # 使用统一的书名提取逻辑（和搜索结果展示保持一致）
        metadata = payload.get("metadata")
        book_title = None
        if isinstance(metadata, dict):
            raw_title = metadata.get("book_title", "")
            if raw_title and "中国写意花鸟画教程" in raw_title:
                book_title = "写意教程"  # 简写，节省 token
            elif _valid(raw_title):
                book_title = raw_title
        if not book_title:
            raw_bt = payload.get("book", "")
            if _valid(raw_bt):
                book_title = raw_bt
            else:
                book_title = "未知书籍"
        page = payload.get("page_start", 0)
        content = payload.get("content", "")
        chapter = payload.get("chapter", "")

        snippet = content[:1200] if content else ""
        if len(content) > 1200:
            snippet += "..."

        part = f"[{i}] 《{book_title}》第{page}页"
        if chapter and chapter.strip() and chapter.strip() != "正文":
            part += f"（{chapter.strip()}）"
        part += f":\n{snippet}"
        parts.append(part)

    return "\n\n".join(parts)


async def generate_summary(
    query: str,
    search_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """基于搜索结果生成 AI 摘要"""
    if not query or not search_results:
        return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}

    try:
        settings = get_settings()
        api_key, base_url, model = _get_llm_config()

        if not api_key:
            logger.warning("AI 摘要: API Key 未配置，跳过")
            return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}

        context = _build_context(search_results)
        if not context.strip():
            return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}

        url = f"{base_url}/chat/completions"
        user_content = f"搜索结果如下:\n\n{context}\n\n用户问题: {query}\n\n请基于以上搜索结果生成综合回答。"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # 使用 requests（同步）+ asyncio.to_thread，避免 httpx 在 asyncio 事件循环中的 read 超时问题
        t0 = time.time()
        logger.info("[摘要] 开始请求: model=%s", model)

        def _do_request():
            body = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4096,
            }
            # DeepSeek 需要关闭 thinking 模式
            if settings.DEEPSEEK_API_KEY:
                body["thinking"] = {"type": "disabled"}
            return requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
        
        r = await asyncio.to_thread(_do_request)
        elapsed = time.time() - t0
        logger.info("AI 摘要 API 响应: status=%d, 耗时=%.1fs", r.status_code, elapsed)
        r.raise_for_status()
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not text:
            return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}

        result = _parse_summary_response(text)

        logger.info("AI 摘要生成完成: answer_len=%d, key_points=%d, concepts=%d, confidence=%.2f, sources=%d, 总耗时=%.1fs",
                   len(result.get("answer", "")),
                   len(result.get("key_points", [])),
                   len(result.get("related_concepts", [])),
                   result.get("confidence", 0),
                   len(result.get("sources", [])),
                   elapsed)
        return result

    except requests.Timeout as e:
        logger.warning("AI 摘要超时: %s", e)
        return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}
    except requests.HTTPError as e:
        logger.warning("AI 摘要 API HTTP 错误: %d, body=%s", e.response.status_code, e.response.text[:200])
        return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}
    except Exception as e:
        logger.error("AI 摘要异常: %s: %s", type(e).__name__, e, exc_info=True)
        return {"answer": "", "key_points": [], "related_concepts": [], "confidence": 0.0, "sources": []}
