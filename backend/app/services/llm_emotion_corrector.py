"""
LLM 逐维度情感校正服务
────────────────────────────────────────
对词库引擎（molin_engine）的 8 维基线分数做逐维度审核修正。

架构定位：
  - 是"校正层"而非替代层
  - 词库基线保证护城河 + 低延迟，LLM 修复词库盲区
  - LLM 调用失败 → 全 0 delta，降级到纯词库

输出格式：
  {
    "corrections": {
      "text":     { "delta": 0.5, "confidence": 0.8, "reasoning": "..." },
      "spatial":  { "delta": 0.0, "confidence": 0.7, "reasoning": "..." },
      ...
    },
    "combined": { "delta": 0.17, "polarity": "positive", "summary": "..." },
    "meta": { "model": "...", "token_count": 1234, "time_ms": 3200 }
  }
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any
from app.services.qwen_llm_client import call_qwen_chat_async

logger = logging.getLogger(__name__)

# ── Prompt 模板 ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位精通中国古代书画的鉴赏专家，负责审核情感分析引擎对书画题跋的评分结果。

词库引擎已对题跋的 8 个维度给出基线分数（未归一化 raw score，范围通常在 -10 到 +10），
你的任务是：逐维度判断词库评分是否准确，并给出校正量（delta，范围 -1.0 到 +1.0）。

注意：
1. 每维度的 delta 加到基线 raw score 上得到最终分
2. delta 为正表示"词库得分偏低需要上调"，负表示"词库得分偏高需要下调"
3. 置信度低于 0.5 时请返回 delta=0（不校正）
4. 重点修复多字词组整体情感（如"枯木逢春"被拆成单字）、否定词未正确处理、
   程度副词未加权、咏物/写景类题跋的情感误判
5. 书画语境中"狂"、"醉"、"痴"、"顽"、"怪"等通常为正面（艺术创作的自由状态）
6. 输出必须是合法 JSON"""


def _build_user_prompt(
    text: str,
    dimension_scores: Dict[str, Dict],
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> str:
    """构建用户提示，包含词库基线分数和上下文"""
    lines = [f"## 题跋文本\n{text}\n"]

    if artist:
        lines.append(f"## 作者\n{artist}")
    if year:
        lines.append(f"## 年代\n{year}年")
    if themes:
        theme_names = [t.get("name", "") for t in themes[:3]]
        lines.append(f"## 主题\n{'、'.join(theme_names)}")
    if spatial_info:
        lines.append(f"## 空间布局\n{spatial_info}")
    if seal_info:
        lines.append(f"## 印章\n{seal_info}")

    lines.append("\n## 词库基线分数（各维度 raw score）")
    for dim_name, dim_data in dimension_scores.items():
        raw = dim_data.get("raw", 0)
        norm = dim_data.get("normalized", 0)
        conf = dim_data.get("confidence", 1.0)
        has_data = dim_data.get("has_data", False)
        status = "有数据" if has_data else "无数据"
        lines.append(f"  {dim_name}: raw={raw:+.2f}, norm={norm:+.3f}, conf={conf:.1f} [{status}]")

    lines.append(f"""
## 输出格式（必须严格 JSON，不要附带任何解释）
```json
{{
  "corrections": {{
    "text":     {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "spatial":  {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "painting": {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "size":     {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "period":   {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "seal":     {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "theme":    {{"delta": <float>, "confidence": <float 0-1>, "reasoning": "<why>"}},
    "brush_ink":{{"delta": 0, "confidence": 0, "reasoning": "预留维度"}}
  }},
  "combined": {{
    "delta": <float>,
    "polarity": "positive|negative|neutral",
    "summary": "<one-sentence summary of the main correction>"
  }}
}}
```""")

    return "\n".join(lines)


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 回复中提取 JSON 对象（处理 markdown 代码块包裹）"""
    text = text.strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 中提取
    import re
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试从 { 开始 } 结束提取
    m = re.search(r'(\{.*\})', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _validate_corrections(data: dict) -> bool:
    """验证 LLM 输出结构是否完整"""
    if not isinstance(data, dict):
        return False
    corrections = data.get("corrections")
    if not isinstance(corrections, dict):
        return False
    expected_dims = {"text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"}
    if not expected_dims.issubset(corrections.keys()):
        return False
    for dim_name, dim_data in corrections.items():
        if not isinstance(dim_data, dict):
            return False
        if "delta" not in dim_data or "confidence" not in dim_data:
            return False
        delta = dim_data.get("delta", 0)
        if not isinstance(delta, (int, float)) or delta < -1.0 or delta > 1.0:
            return False
    combined = data.get("combined")
    if not isinstance(combined, dict) or "delta" not in combined:
        return False
    return True


def _empty_corrections() -> dict:
    """返回空的校正结果（LLM 失败时降级使用）"""
    empty_dim = {"delta": 0.0, "confidence": 0.0, "reasoning": "LLM校正不可用"}
    return {
        "corrections": {
            "text": dict(empty_dim),
            "spatial": dict(empty_dim),
            "painting": dict(empty_dim),
            "size": dict(empty_dim),
            "period": dict(empty_dim),
            "seal": dict(empty_dim),
            "theme": dict(empty_dim),
            "brush_ink": {"delta": 0.0, "confidence": 0.0, "reasoning": "预留维度"},
        },
        "combined": {
            "delta": 0.0,
            "polarity": "neutral",
            "summary": "LLM校正不可用，使用纯词库基线",
        },
        "meta": {
            "model": "",
            "token_count": 0,
            "time_ms": 0,
            "error": "LLM调用失败或超时",
        },
    }


async def correct_dimensions(
    text: str,
    lexicon_result: Dict[str, Any],
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> dict:
    """
    主入口：对词库引擎的 8 维基线分数进行 LLM 逐维度校正

    Args:
        text: 题跋全文
        lexicon_result: molin_engine.analyze() 返回的 EngineResult 的维度数据
        artist: 作者名
        year: 创作年份
        themes: 主题列表
        spatial_info: 空间布局描述文本
        seal_info: 印章描述文本

    Returns:
        结构化校正结果 dict（含 corrections, combined, meta）
        失败时返回 _empty_corrections()（全 0 delta）
    """
    start = time.time()

    # 提取各维度基线分数
    dimension_scores = {}
    dim_keys = ["text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"]
    for key in dim_keys:
        dim = lexicon_result.get(key, {})
        if hasattr(dim, "raw"):  # DimensionResult 对象
            dimension_scores[key] = {
                "raw": getattr(dim, "raw", 0),
                "normalized": getattr(dim, "normalized", 0),
                "confidence": getattr(dim, "confidence", 1.0),
                "has_data": getattr(dim, "has_data", False),
            }
        elif isinstance(dim, dict):  # 字典格式
            dimension_scores[key] = {
                "raw": dim.get("raw", 0),
                "normalized": dim.get("normalized", 0),
                "confidence": dim.get("confidence", 1.0),
                "has_data": dim.get("has_data", False),
            }
        else:
            dimension_scores[key] = {"raw": 0, "normalized": 0, "confidence": 0, "has_data": False}

    # 构建 prompt
    user_prompt = _build_user_prompt(
        text=text,
        dimension_scores=dimension_scores,
        artist=artist,
        year=year,
        themes=themes,
        spatial_info=spatial_info,
        seal_info=seal_info,
    )

    try:
        response = await call_qwen_chat_async(
            max_tokens=2000,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        logger.warning(f"LLM emotion corrector call failed: {e}")
        return _empty_corrections()

    elapsed = time.time() - start

    # 检查 LLM 返回是否有错误
    if "error" in response:
        logger.warning(f"LLM emotion corrector returned error: {response['error']}")
        result = _empty_corrections()
        result["meta"]["error"] = response["error"]
        return result

    # 提取回复文本
    choices = response.get("choices", [])
    if not choices:
        logger.warning("LLM emotion corrector: no choices in response")
        return _empty_corrections()

    reply_text = choices[0].get("message", {}).get("content", "")
    if not reply_text:
        logger.warning("LLM emotion corrector: empty reply")
        return _empty_corrections()

    # 解析 JSON
    parsed = _extract_json(reply_text)
    if not parsed:
        logger.warning(f"LLM emotion corrector: failed to parse JSON from reply")
        return _empty_corrections()

    # 验证结构
    if not _validate_corrections(parsed):
        logger.warning(f"LLM emotion corrector: invalid structure in parsed output")
        return _empty_corrections()

    # 补充 meta 信息
    usage = response.get("usage", {})
    parsed["meta"] = {
        "model": response.get("model", "unknown"),
        "token_count": usage.get("total_tokens", 0),
        "time_ms": int(elapsed * 1000),
    }

    return parsed


async def apply_corrections(
    engine_result: Any,
    llm_corrections: dict,
    weights: Dict[str, float] = None,
) -> dict:
    """
    将 LLM 校正量应用到引擎结果上，返回最终分数。

    Args:
        engine_result: molin_engine.analyze() 返回的 EngineResult
        llm_corrections: correct_dimensions() 返回的校正结果
        weights: 各维度权重（与 molin_engine 一致）

    Returns:
        {
            "dimensions": { dim_name: { "lexicon": ..., "delta": ..., "final": ... } },
            "combined_raw": float,
            "combined_normalized": float,
            "polarity": str,
            "analysis_method": "llm_corrected" | "lexicon_only",
        }
    """
    from app.services.molin_engine import vader_normalize, classify_polarity, DEFAULT_WEIGHTS

    if weights is None:
        weights = DEFAULT_WEIGHTS

    corrections = llm_corrections.get("corrections", {})
    has_corrections = any(
        c.get("delta", 0) != 0 and c.get("confidence", 0) >= 0.5
        for c in corrections.values()
    )

    analysis_method = "llm_corrected" if has_corrections else "lexicon_only"

    dim_keys = ["text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"]
    dimensions = {}

    for key in dim_keys:
        dim = getattr(engine_result, key, None)
        if dim is None:
            dim = type('obj', (object,), {"raw": 0, "normalized": 0, "confidence": 0})()

        lexicon_raw = getattr(dim, "raw", 0)
        corr = corrections.get(key, {})
        delta = corr.get("delta", 0)
        conf = corr.get("confidence", 0)

        # 置信度低于 0.5 时不校正
        effective_delta = delta if conf >= 0.5 else 0.0
        final_raw = lexicon_raw + effective_delta

        dim_entry = {
            "dim_name": key,
            "lexicon_raw": lexicon_raw,
            "delta": effective_delta,
            "final_raw": final_raw,
            "confidence": max(getattr(dim, "confidence", 1.0), conf),
        }
        dimensions[key] = dim_entry

    # 加权融合
    weighted_sum = 0.0
    weight_total = 0.0
    for key, entry in dimensions.items():
        w = weights.get(key, 0)
        effective_weight = w * entry["confidence"]
        weighted_sum += effective_weight * entry["final_raw"]
        weight_total += effective_weight

    if weight_total == 0:
        combined_raw = 0.0
    else:
        combined_raw = weighted_sum / weight_total

    combined_normalized = vader_normalize(combined_raw)
    polarity = classify_polarity(combined_normalized)

    return {
        "dimensions": dimensions,
        "combined_raw": combined_raw,
        "combined_normalized": combined_normalized,
        "polarity": polarity,
        "analysis_method": analysis_method,
    }
