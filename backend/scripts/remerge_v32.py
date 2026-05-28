#!/usr/bin/env python3
"""
重新合并 v3.2 词库 + 已有 LLM 裁判结果
─────────────────────────────────────
对所有有 llm_judge 的记录：
  1. 用当前 v3.2 词库重新跑 molin_analyze()
  2. 取已有 llm_judge 的评分
  3. 合并 → 更新 combined_sentiment
  4. 更新 lexicon_scores 版本

不调用 LLM API，纯本地运算。
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_connection
from app.services.molin_engine import (
    analyze as molin_analyze,
    vader_normalize,
    classify_polarity,
    classify_complex_polarity,
    compute_conflict_score,
    DimensionResult,
)


def _best_raw(key, dim_dict, lexicon_raw):
    """判断是否使用 LLM 裁判的分数"""
    j = dim_dict.get(key) or {}
    jr = j.get("raw", 0) or 0
    jc = j.get("confidence", 0) or 0
    if abs(jr) > 0.1 and jc >= 0.5:
        return jr
    return lexicon_raw


def rebuild_merged(record, lex_result, judge_result):
    """用 v3.2 词库结果 + 已有 LLM 裁判结果 重建 combined_sentiment"""
    old_ca = {}
    if record["content_analysis"]:
        try:
            old_ca = json.loads(record["content_analysis"])
        except Exception:
            old_ca = {}

    # 构建新的 lexicon_scores
    lexicon_scores = {
        "version": "3.2",
        "text": {"raw": lex_result.text.raw, "normalized": lex_result.text.normalized,
                 "confidence": lex_result.text.confidence, "has_data": lex_result.text.has_data},
        "spatial": {"raw": lex_result.spatial.raw, "normalized": lex_result.spatial.normalized,
                    "confidence": lex_result.spatial.confidence, "has_data": lex_result.spatial.has_data},
        "painting": {"raw": lex_result.painting.raw, "normalized": lex_result.painting.normalized,
                     "confidence": lex_result.painting.confidence, "has_data": lex_result.painting.has_data},
        "size": {"raw": lex_result.size.raw, "normalized": lex_result.size.normalized,
                 "confidence": lex_result.size.confidence, "has_data": lex_result.size.has_data},
        "period": {"raw": lex_result.period.raw, "normalized": lex_result.period.normalized,
                   "confidence": lex_result.period.confidence, "has_data": lex_result.period.has_data},
        "seal": {"raw": lex_result.seal.raw, "normalized": lex_result.seal.normalized,
                 "confidence": lex_result.seal.confidence, "has_data": lex_result.seal.has_data},
        "theme": {"raw": lex_result.theme.raw, "normalized": lex_result.theme.normalized,
                  "confidence": lex_result.theme.confidence, "has_data": lex_result.theme.has_data},
        "brush_ink": {"raw": lex_result.brush_ink.raw, "normalized": lex_result.brush_ink.normalized,
                      "confidence": lex_result.brush_ink.confidence, "has_data": lex_result.brush_ink.has_data},
        "combined_raw": lex_result.combined_raw,
        "combined_normalized": lex_result.combined_normalized,
    }

    new_ca = dict(old_ca) if isinstance(old_ca, dict) else {}

    if judge_result and judge_result.get("dimension_scores"):
        jd = judge_result["dimension_scores"]
        jc = judge_result.get("combined", {})

        dim_map = {"text": lex_result.text, "spatial": lex_result.spatial,
                   "painting": lex_result.painting, "size": lex_result.size,
                   "period": lex_result.period, "seal": lex_result.seal,
                   "theme": lex_result.theme, "brush_ink": lex_result.brush_ink}

        dim_raws = {}
        dim_pols = {}
        judge_dims = []

        for key in ["text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"]:
            lr = getattr(dim_map[key], "raw", 0) or 0
            raw = _best_raw(key, jd, lr)
            dim_raws[key] = raw
            norm = vader_normalize(raw)
            dim_pols[key] = classify_polarity(norm)
            has_data = dim_map[key].has_data or abs(raw) > 0.01
            judge_dims.append(DimensionResult(name=key, raw=raw, normalized=norm,
                                              has_data=has_data))

        conflict = compute_conflict_score(judge_dims)

        # 重加权
        w = lex_result.weights_used
        ws, wt = 0.0, 0.0
        for key in dim_raws:
            ew = w.get(key, 0) * getattr(dim_map[key], "confidence", 0.5)
            ws += ew * dim_raws[key]
            wt += ew
        merged_raw = ws / wt if wt > 0 else 0
        merged_norm = vader_normalize(merged_raw)
        merged_polarity = classify_complex_polarity(merged_norm, dim_pols)

        analysis_method = "llm_corrected"

        new_ca["lexicon_scores"] = lexicon_scores
        new_ca["llm_judge"] = judge_result
        new_ca["llm_analysis"] = judge_result
        new_ca["analysis_method"] = analysis_method
        new_ca["analysis_version"] = 3
        new_ca["combined_sentiment"] = {
            "polarity": merged_polarity,
            "reasoning": lex_result.reasoning,
            "text_score": jd.get("text", {}).get("raw", lex_result.text.raw),
            "spatial_score": jd.get("spatial", {}).get("raw", lex_result.spatial.raw),
            "painting_score": jd.get("painting", {}).get("raw", lex_result.painting.raw),
            "size_score": jd.get("size", {}).get("raw", lex_result.size.raw),
            "time_score": jd.get("period", {}).get("raw", lex_result.period.raw),
            "seal_score": jd.get("seal", {}).get("raw", lex_result.seal.raw),
            "theme_score": jd.get("theme", {}).get("raw", lex_result.theme.raw),
            "brush_ink_score": jd.get("brush_ink", {}).get("raw", lex_result.brush_ink.raw),
            "combined_score": round(merged_raw, 2),
            "vader_normalized": round(merged_norm, 3),
            "vader_alpha": 8.0,
            "weights": lex_result.weights_used,
            "method": analysis_method,
            "dimension_polarities": dim_pols,
            "conflict_score": conflict,
            "has_data": {
                "text": abs(dim_raws.get("text", 0)) > 0.01 or lex_result.text.has_data,
                "spatial": abs(dim_raws.get("spatial", 0)) > 0.01 or lex_result.spatial.has_data,
                "painting": abs(dim_raws.get("painting", 0)) > 0.01 or lex_result.painting.has_data,
                "size": lex_result.size.has_data,
                "period": lex_result.period.has_data,
                "seal": lex_result.seal.has_data,
                "theme": lex_result.theme.has_data,
                "brush_ink": lex_result.brush_ink.has_data,
            },
            "dimension_details": {
                "text": {"signals": lex_result.text.signals},
                "spatial": {"signals": lex_result.spatial.signals},
                "painting": {"signals": lex_result.painting.signals},
                "size": {"width": record["artwork_width_cm"], "height": record["artwork_height_cm"]},
                "period": {"year": record["year"]},
                "seal": {"signals": lex_result.seal.signals},
                "theme": {"signals": lex_result.theme.signals},
            },
        }
        return new_ca, merged_raw, merged_norm, merged_polarity, analysis_method
    else:
        # 没有 llm_judge → 纯词库
        new_ca["lexicon_scores"] = lexicon_scores
        new_ca["analysis_method"] = "lexicon_only"
        new_ca["analysis_version"] = 3
        new_ca["combined_sentiment"] = {
            "polarity": lex_result.polarity,
            "reasoning": lex_result.reasoning,
            "text_score": lex_result.text.raw,
            "spatial_score": lex_result.spatial.raw,
            "painting_score": lex_result.painting.raw,
            "size_score": lex_result.size.raw,
            "time_score": lex_result.period.raw,
            "seal_score": lex_result.seal.raw,
            "theme_score": lex_result.theme.raw,
            "brush_ink_score": lex_result.brush_ink.raw,
            "combined_score": round(lex_result.combined_raw, 2),
            "vader_normalized": round(lex_result.combined_normalized, 3),
            "vader_alpha": 8.0,
            "weights": lex_result.weights_used,
            "method": "lexicon_only",
            "dimension_polarities": lex_result.dimension_polarities,
            "conflict_score": lex_result.conflict_score,
            "has_data": {
                "text": lex_result.text.has_data,
                "spatial": lex_result.spatial.has_data,
                "painting": lex_result.painting.has_data,
                "size": lex_result.size.has_data,
                "period": lex_result.period.has_data,
                "seal": lex_result.seal.has_data,
                "theme": lex_result.theme.has_data,
                "brush_ink": lex_result.brush_ink.has_data,
            },
            "dimension_details": {
                "text": {"signals": lex_result.text.signals},
                "spatial": {"signals": lex_result.spatial.signals},
                "painting": {"signals": lex_result.painting.signals},
                "size": {},
                "period": {},
                "seal": {"signals": lex_result.seal.signals},
                "theme": {"signals": lex_result.theme.signals},
            },
        }
        return new_ca, lex_result.combined_raw, lex_result.combined_normalized, lex_result.polarity, "lexicon_only"


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # 查所有有 inscription 的记录
    cur.execute("""
        SELECT id, inscription_content, year, artist,
               artwork_width_cm, artwork_height_cm, seal_content,
               content_analysis, title
        FROM tubi_analyses
        WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0
        ORDER BY id
    """)
    rows = cur.fetchall()
    total = len(rows)

    t0 = time.time()
    updated = 0
    errors = 0
    skipped = 0

    print(f"共 {total} 条记录需要处理\n")

    for i, row in enumerate(rows):
        record = dict(row)
        record_id = record["id"]
        text = record["inscription_content"] or ""
        artist = record["artist"] or ""
        year = record["year"]

        old_ca = {}
        if record["content_analysis"]:
            try:
                old_ca = json.loads(record["content_analysis"])
            except Exception:
                old_ca = {}

        themes = old_ca.get("themes", []) if isinstance(old_ca, dict) else []
        spatial_emotion = old_ca.get("spatial_emotion") if isinstance(old_ca, dict) else None
        v4s = old_ca.get("v4_signals", {}) if isinstance(old_ca, dict) else {}
        painting_matches = v4s.get("painting", []) if isinstance(v4s, dict) else []
        if not painting_matches:
            sigs = old_ca.get("signals", {}) if isinstance(old_ca, dict) else {}
            painting_matches = sigs.get("painting", []) if isinstance(sigs, dict) else []

        # 取已有的 llm_judge
        judge_result = old_ca.get("llm_judge") if isinstance(old_ca, dict) else None

        try:
            # 1. 用 v3.2 词库重新分析
            lex_result = molin_analyze(
                text=text,
                spatial_emotion=spatial_emotion,
                painting_matches=painting_matches,
                width_cm=record["artwork_width_cm"],
                height_cm=record["artwork_height_cm"],
                year=year,
                artist=artist,
                seal_content=record["seal_content"],
                themes=themes,
            )

            # 2. 合并
            new_ca, merged_raw, merged_norm, merged_polarity, method = rebuild_merged(
                record, lex_result, judge_result
            )

            # 3. 保存
            conn.execute(
                "UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
                (json.dumps(new_ca, ensure_ascii=False), record_id),
            )
            updated += 1

        except Exception as e:
            print(f"  [{i+1}/{total}] ID={record_id} ERROR: {e}")
            errors += 1

        if (i + 1) % 100 == 0:
            conn.commit()
            elapsed = time.time() - t0
            print(f"  [{i+1}/{total}] 已处理 {updated} 条, 耗时 {elapsed:.0f}s")

    conn.commit()
    conn.close()

    t_total = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  完成!")
    print(f"  更新: {updated} 条")
    print(f"  错误: {errors} 条")
    print(f"  总耗时: {t_total:.0f}s")


if __name__ == "__main__":
    main()
