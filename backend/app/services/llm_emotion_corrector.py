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

SYSTEM_PROMPT = """你是一位中国古代书画研究者。请根据给出的事实性信息，独立判断题跋的情感。

对以下7个维度分别给出分数（-8到+8）和简短理由：text（文字情感）、period（时期心境）、theme（主题情感）、painting（画材情感）、spatial（空间情感）、seal（印章情感）、size（尺寸情感）。

评分参考：-8~-5强烈消极 | -5~-2明显消极 | -2~+2中性 | +2~+5明显积极 | +5~+8强烈积极

summary字段必须严格按以下三段式结构。引用题跋原文词句为证，结合画家生平、创作年代、画幅尺寸等元数据进行深度解读：
积极面：80-120字。提取正向情绪、自我肯定、坚持、美感、生命意志等。引用原文词句，说明其积极含义。
消极面：80-120字。指出孤独、被拒、命运不顺、苦涩、自嘲、幻灭等。引用原文词句，说明其消极含义。
综合判断：120-200字。给出总体定性（如：偏积极/偏消极/悲凉中的倔强/热烈下的虚无等），说明两面如何共存，结合画家此时期的心境、人生阶段、艺术风格做整体评价。这一段应当是最有深度的总结。

输出严格JSON，不要markdown包裹：
{"scores":{"text":{"score":0,"reasoning":"..."},...},"polarity":"neutral","summary":"积极面：（80-120字）...\\n消极面：（80-120字）...\\n综合判断：（120-200字，最有深度的总结）...","reasoning":"..."}"""


def _build_user_prompt(
    text: str,
    dimension_scores: Dict[str, Dict],
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
    size_info: str = None,
) -> str:
    """构建用户提示，只给事实性信息，不给判断性暗示"""
    lines = [f"## 题跋全文\n{text}\n"]

    # 画家和年代：只给事实
    if artist:
        lines.append(f"## 画家\n{artist}")
    if year:
        lines.append(f"## 创作年份\n{year}年")
    if themes:
        theme_names = [t.get("name", "") for t in themes[:5]]
        lines.append(f"## 主题分类\n{'、'.join(theme_names)}")
    if size_info:
        lines.append(f"## 画幅尺寸\n{size_info}")
    if spatial_info:
        lines.append(f"## 空间布局\n{spatial_info}")
    if seal_info:
        lines.append(f"## 印章\n{seal_info}")

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
    """验证 LLM 输出结构是否完整（支持新 scores 格式和旧 corrections 格式）"""
    if not isinstance(data, dict):
        logger.warning(f"_validate_corrections: not a dict, type={type(data).__name__}")
        return False

    # 新格式：scores（每个维度可以是数字或 {score, reasoning} 字典）
    scores = data.get("scores")
    if isinstance(scores, dict):
        expected_dims = {"text", "period", "theme", "painting", "spatial", "seal", "size"}
        if expected_dims.issubset(scores.keys()):
            for dim_name, val in scores.items():
                if dim_name == "brush_ink":
                    continue
                if isinstance(val, dict):
                    if not isinstance(val.get("score", 0), (int, float)):
                        return False
                elif not isinstance(val, (int, float)):
                    return False
            logger.info(f"_validate_corrections: PASSED (scores format), polarity={data.get('polarity','?')}")
            return True

    # 旧格式：corrections（向后兼容）
    corrections = data.get("corrections")
    if isinstance(corrections, dict):
        expected_dims = {"text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"}
        if expected_dims.issubset(corrections.keys()):
            logger.info(f"_validate_corrections: PASSED (corrections format)")
            return True

    logger.warning("_validate_corrections: invalid format")
    return False


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
    size_info: str = None,
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
    logger.info(f"correct_dimensions: text_len={len(text)}, artist={artist}, year={year}, dims={list(dimension_scores.keys())}")
    user_prompt = _build_user_prompt(
        text=text,
        dimension_scores=dimension_scores,
        artist=artist,
        year=year,
        themes=themes,
        spatial_info=spatial_info,
        seal_info=seal_info,
        size_info=size_info,
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
        logger.warning(f"LLM emotion corrector: failed to parse JSON from reply (len={len(reply_text)}). First 200 chars: {reply_text[:200]}")
        return _empty_corrections()
    logger.info(f"LLM emotion corrector: parsed JSON OK, keys={list(parsed.keys())}")

    # 验证结构
    if not _validate_corrections(parsed):
        logger.warning(f"LLM emotion corrector: invalid structure. keys={list(parsed.keys())}")
        return _empty_corrections()

    # 如果是新格式 scores，转换为 corrections（delta = llm_score - lexicon_score）
    if "scores" in parsed and "corrections" not in parsed:
        llm_scores = parsed["scores"]
        corrections = {}
        for dim in ["text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"]:
            entry = llm_scores.get(dim, {})
            if isinstance(entry, dict):
                llm_val = entry.get("score", 0) or 0
                reasoning = entry.get("reasoning", "")
            else:
                llm_val = entry or 0
                reasoning = ""
            lex_raw = dimension_scores.get(dim, {}).get("raw", 0) or 0
            delta = llm_val - lex_raw
            corrections[dim] = {
                "delta": round(delta, 2),
                "confidence": 0.8 if dim != "brush_ink" else 0,
                "reasoning": reasoning,
            }
        parsed["corrections"] = corrections
        parsed["combined"] = {
            "delta": 0,
            "polarity": parsed.get("polarity", "neutral"),
            "summary": parsed.get("summary", ""),
        }

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


# ═══════════════════════════════════════════════════════════════════
# v3.2: LLM 主裁判模式 — 独立解读，不看词库分数
# ═══════════════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """你是诗词情感分析师。对输入的诗句，按以下三项输出，每项写成一整段。

**一、评分**（写入 dimension_scores 和 combined）：

独立判断每个维度的情感分（raw -10~+10），注意：
- 看反讽、对比、条件句式。不要只看单个词的字面意思
- "甘芳物无限，辣味嫌人餐" → 甘芳是反衬，不是说甜的好
- "任使含咀乃得志" → 重点是"忍受"，不是"得志"
- 书画语境："狂""醉""痴""顽""怪"常为正面（艺术自由）；"辣""拙""丑""枯"可能是艺术主张

**二、解读**（写入 combined.summary，严格按以下三段式，每项写成一整段，引用词句为证）：

积极面：提取正向情绪、自我肯定、坚持、美感、生命意志等，引用词句为证。

消极面：指出孤独、被拒、命运不顺、苦涩、自嘲、幻灭等，引用词句为证。

综合判断：基于以上两面，给出一个总体定性（如：偏积极 / 偏消极 / 悲凉中的倔强 / 热烈下的虚无等），并说明两面如何共存。

要求：语言凝练有分析感，避免流水账。"""

JUDGE_OUTPUT_FORMAT = """
## 输出格式（严格 JSON）
{
  "dimension_scores": {
    "text":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "spatial":   {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "painting":  {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "size":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "period":    {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "seal":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "theme":     {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "brush_ink": {"raw": 0, "confidence": 0, "reasoning": "无数据"}
  },
  "combined": {
    "polarity": "positive|negative|neutral|complex",
    "combined_raw": <float>,
    "summary": "积极面：
...

消极面：
...

综合判断：
..."
  }
}
"""

def _build_judge_prompt(
    text: str,
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> str:
    """构建 LLM 裁判的输入提示——只给题跋和上下文，不给词库分数"""
    lines = [f"## 题跋全文\n{text}\n"]

    artist_hints = {
        "李鱓": "扬州八怪之一。早年供奉内廷→中期扬州卖画→晚期归隐。题跋常带自嘲、不驯、苦涩中的倔强。",
        "郑燮": "扬州八怪之一，号板桥。题跋多含为民请命、不媚权贵之意。",
        "徐渭": "大写意开创者，一生坎坷潦倒。题跋常狂放与悲愤交织。",
        "朱耷": "明宗室后裔，国破家亡后出家。画中鱼鸟白眼向人，题跋晦涩隐晦。",
    }
    if artist:
        lines.append(f"## 作者\n{artist}")
        if artist in artist_hints:
            lines.append(f"背景：{artist_hints[artist]}")

    if year:
        lines.append(f"## 年代\n{year}年")
    if themes:
        theme_names = [t.get("name", "") for t in themes[:5]]
        lines.append(f"## 主题标签\n{'、'.join(theme_names)}")
    if spatial_info:
        lines.append(f"## 空间布局参考\n{spatial_info}")
    if seal_info:
        lines.append(f"## 印章参考\n{seal_info}")

    lines.append(JUDGE_OUTPUT_FORMAT)
    return "\n".join(lines)


async def judge_independently(
    text: str,
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> dict:
    """
    v3.2: LLM 主裁判模式——独立解读题跋，不受词库分数影响。

    只接收题跋和元数据，不接收词库基线分。
    返回独立的情感判断（dimension_scores + combined）。
    失败时返回 None（调用方降级到词库）。
    """
    start = time.time()
    user_prompt = _build_judge_prompt(
        text=text, artist=artist, year=year,
        themes=themes, spatial_info=spatial_info, seal_info=seal_info,
    )

    try:
        response = await call_qwen_chat_async(
            max_tokens=2000,
            temperature=0.4,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        logger.warning(f"LLM judge call failed: {e}")
        return None

    if "error" in response:
        logger.warning(f"LLM judge returned error: {response['error']}")
        return None

    choices = response.get("choices", [])
    if not choices:
        logger.warning("LLM judge: no choices in response")
        return None

    reply_text = choices[0].get("message", {}).get("content", "")
    if not reply_text:
        logger.warning("LLM judge: empty reply")
        return None

    parsed = _extract_json(reply_text)
    if not parsed:
        logger.warning(f"LLM judge: failed to parse JSON (len={len(reply_text)}). First 200: {reply_text[:200]}")
        return None

    dims = parsed.get("dimension_scores")
    if not isinstance(dims, dict) or len(dims) < 7:
        logger.warning(f"LLM judge: invalid dimension_scores")
        return None

    combined = parsed.get("combined")
    if not isinstance(combined, dict) or "summary" not in combined:
        logger.warning("LLM judge: invalid combined")
        return None

    elapsed = time.time() - start
    usage = response.get("usage", {})
    parsed["meta"] = {
        "model": response.get("model", "unknown"),
        "token_count": usage.get("total_tokens", 0),
        "time_ms": int(elapsed * 1000),
    }

    logger.info(f"LLM judge: polarity={combined.get('polarity')}, text_raw={dims.get('text',{}).get('raw')}, elapsed={elapsed:.1f}s")
    return parsed
