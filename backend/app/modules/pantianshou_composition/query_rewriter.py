"""Query 改写模块 — 用 LLM 扩展和优化用户查询

策略:
- 专有名词（人名、图号）: 不改写，保持原样
- 技法类查询（"怎么画竹子"）: 扩展同义词和相关概念
- 概念类查询（"留白"）: 关联到上下位概念
- 问题类查询（"构图法则有哪些"）: 提取核心主题词

输出 JSON:
{
    "original": "原始查询",
    "rewrites": ["改写1", "改写2", ...],
    "intent": "技法|理论|人物|概念|综合"
}
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 模型配置：DeepSeek 优先
def _get_model() -> str:
    from app.services.qwen_llm_client import get_text_llm_config
    _, _, model = get_text_llm_config()
    return model

# 改写 prompt
SYSTEM_PROMPT = """你是中国画专业知识领域的搜索查询优化助手。用户会在知识库中搜索中国画相关内容，你的任务是改写和扩展搜索查询，帮助搜索到更相关的结果。

规则:
1. 专有名词（人名、书名、图号如"图十二"）: 不要改写，原样保留
2. 技法查询（"怎么画竹子""墨法"）: 扩展同义词和相关概念
3. 概念查询（"留白""开合"）: 关联上下位和相关概念
4. 问题查询（"构图法则有哪些"）: 提取核心主题词
5. 短查询（2-3字）更应扩展，长查询保持原意即可
6. 每个改写后的查询应该是独立的、可用于搜索的短语
7. 改写查询数量: 2-3 个
8. 必须输出合法 JSON，不要输出其他内容

输出格式:
{"original": "原始查询", "rewrites": ["改写1", "改写2"], "intent": "技法|理论|人物|概念|综合"}"""


def _is_proper_noun(query: str) -> bool:
    """检测是否为专有名词（人名、短标识符等），不改写"""
    query = query.strip()
    zh_chars = re.findall(r'[\u4e00-\u9fff]', query)
    # 2-6字中文且无疑问词，可能是人名或专有名词
    if 2 <= len(zh_chars) <= 6:
        if not re.search(r'[怎么如何什么为什么哪哪里多少方法技巧步骤]', query):
            return True
    # 纯图号
    if re.match(r'^图[一二三四五六七八九十百千万\d]+$', query):
        return True
    return False


def _parse_rewrite_response(text: str) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON"""
    text = text.strip()
    # 处理可能的 ```json 包裹
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()

    # 尝试提取 JSON（可能有多余文本）
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        result = json.loads(text)
        if "rewrites" not in result:
            result["rewrites"] = []
        if not isinstance(result["rewrites"], list):
            result["rewrites"] = []
        if "intent" not in result:
            result["intent"] = "综合"
        result["original"] = result.get("original", "")
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Query 改写 JSON 解析失败: %s, 原文: %.200s", e, text)
        return {"original": "", "rewrites": [], "intent": "综合"}


def _call_llm_sync(url: str, api_key: str, messages: list) -> Optional[str]:
    """同步调用 Qwen API（和 composition_llm.py 相同模式，已验证可用）"""
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0, read=30.0, write=15.0)) as client:
        r = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _get_model(),
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 300,
            },
        )
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def rewrite_query(query: str) -> Dict[str, Any]:
    """改写搜索查询"""
    if not query or not query.strip():
        return {"original": query, "rewrites": [], "intent": "综合"}

    query = query.strip()

    # 专有名词不改写
    if _is_proper_noun(query):
        logger.info("专有名词跳过改写: '%s'", query)
        return {"original": query, "rewrites": [], "intent": "人物"}

    try:
        from app.services.qwen_llm_client import get_text_llm_config
        api_key, base_url, model = get_text_llm_config()

        if not api_key:
            logger.warning("Query 改写: API Key 未配置，跳过改写")
            return {"original": query, "rewrites": [], "intent": "综合"}

        url = f"{base_url}/chat/completions"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请改写以下搜索查询: {query}"},
        ]

        # 用 asyncio.to_thread 在线程池中跑同步 httpx 调用
        text = await asyncio.to_thread(_call_llm_sync, url, api_key, messages)

        if not text:
            return {"original": query, "rewrites": [], "intent": "综合"}

        result = _parse_rewrite_response(text)
        result["original"] = query

        logger.info("Query 改写完成: '%s' -> %d 个改写, 意图=%s",
                   query, len(result.get("rewrites", [])), result.get("intent", "综合"))
        return result

    except httpx.HTTPStatusError as e:
        logger.warning("Query 改写 API HTTP 错误: %d", e.response.status_code)
        return {"original": query, "rewrites": [], "intent": "综合"}
    except httpx.TimeoutException:
        logger.warning("Query 改写超时，跳过改写")
        return {"original": query, "rewrites": [], "intent": "综合"}
    except Exception as e:
        logger.error("Query 改写异常: %s", e)
        return {"original": query, "rewrites": [], "intent": "综合"}
