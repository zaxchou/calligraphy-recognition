#!/usr/bin/env python3
"""
批量 LLM 裁判 — 逐条调用 LLM judge 并存入数据库，同时与词库对比
────────────────────────────────────────
用法:
  python scripts/batch_llm_judge.py                  # 处理 15 条随机李鱓
  python scripts/batch_llm_judge.py --limit 30       # 处理 30 条
  python scripts/batch_llm_judge.py --artist 李鱓     # 指定画家
  python scripts/batch_llm_judge.py --all-artists     # 不限画家
  python scripts/batch_llm_judge.py --dry-run         # 仅预览，不调用 LLM
"""

import sys
import os
import json
import asyncio
import time
import argparse
import random

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
from app.services.llm_emotion_corrector import judge_independently


def query_records(artist_filter="李鱓", limit=15, all_artists=False):
    """查询需要处理的记录（随机）"""
    conn = get_db_connection()
    cur = conn.cursor()

    where = "inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0"
    if not all_artists and artist_filter:
        where += f" AND artist = '{artist_filter}'"
    # 只取还没跑 LLM judge 的
    where += " AND (content_analysis IS NULL OR json_extract(content_analysis, '$.llm_judge') IS NULL)"

    # 先统计
    cur.execute(f"SELECT COUNT(*) FROM tubi_analyses WHERE {where}")
    total = cur.fetchone()[0]

    # 随机取
    sql = f"""
        SELECT id, inscription_content, year, artist,
               artwork_width_cm, artwork_height_cm, seal_content,
               content_analysis, title
        FROM tubi_analyses
        WHERE {where}
        ORDER BY RANDOM()
        LIMIT {limit}
    """
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return rows, total


def _best_raw(key, dim_dict, lexicon_raw):
    """判断是否使用 LLM 裁判的分数"""
    j = dim_dict.get(key) or {}
    jr = j.get("raw", 0) or 0
    jc = j.get("confidence", 0) or 0
    if abs(jr) > 0.1 and jc >= 0.5:
        return jr
    return lexicon_raw


def merge_save_structure(record, lex_result, judge_result):
    """构造与 admin.py 一致的 save dict"""
    old_ca = {}
    if record["content_analysis"]:
        try:
            old_ca = json.loads(record["content_analysis"])
        except Exception:
            old_ca = {}

    # 构建 lexicon_scores
    lexicon_scores = {
        "version": "3.1",
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
            # 单个维度用三分类
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
        # LLM 失败 → 纯词库
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


async def process_record(record, dry_run=False):
    """处理一条记录：词库 + LLM 裁判 + 保存"""
    record_id = record["id"]
    text = record["inscription_content"] or ""
    artist = record["artist"]
    year = record["year"]

    # 从旧 content_analysis 提取辅助数据
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

    # 1. 词库分析（同步）
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

    # 2. LLM 裁判（异步）
    if dry_run:
        judge_result = None
    else:
        try:
            judge_result = await judge_independently(
                text=text, artist=artist, year=year, themes=themes
            )
        except Exception as e:
            print(f"    LLM judge failed: {e}")
            judge_result = None

    # 3. 构建保存结构
    new_ca, merged_raw, merged_norm, merged_polarity, method = merge_save_structure(
        record, lex_result, judge_result
    )

    # 4. 保存到 DB
    if not dry_run:
        conn = get_db_connection()
        conn.execute(
            "UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
            (json.dumps(new_ca, ensure_ascii=False), record_id),
        )
        conn.commit()
        conn.close()

    # 5. 返回对比数据
    comp = {
        "id": record_id,
        "title": (record["title"] or "")[:18],
        "text_preview": (text[:60] + "...") if len(text) > 60 else text,
        "lex_text_raw": round(lex_result.text.raw, 2),
        "lex_combined_norm": round(lex_result.combined_normalized, 3),
        "lex_polarity": lex_result.polarity,
        "llm_text_raw": None,
        "llm_combined_raw": None,
        "llm_polarity": None,
        "gap": None,
        "method": method,
    }

    if judge_result and judge_result.get("dimension_scores"):
        jd = judge_result["dimension_scores"]
        jc = judge_result.get("combined", {})
        comp["llm_text_raw"] = round(jd.get("text", {}).get("raw", 0), 2)
        comp["llm_combined_raw"] = round(jc.get("combined_raw", 0), 2)
        comp["llm_polarity"] = jc.get("polarity", "?")
        comp["gap"] = round(lex_result.text.raw - (jd.get("text", {}).get("raw", 0) or 0), 2)

    return comp


async def main():
    parser = argparse.ArgumentParser(description="批量 LLM 裁判")
    parser.add_argument("--limit", type=int, default=15, help="处理条数（默认 15）")
    parser.add_argument("--artist", type=str, default="李鱓", help="画家筛选（默认 李鱓）")
    parser.add_argument("--all-artists", action="store_true", help="不限画家")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不调 LLM 也不保存")
    args = parser.parse_args()

    rows, total_available = query_records(
        artist_filter=args.artist,
        limit=args.limit,
        all_artists=args.all_artists,
    )

    if args.all_artists:
        group_label = "全部画家"
    else:
        group_label = f"画家: {args.artist}"

    print(f"\n{'='*110}")
    print(f"  批量 LLM 裁判 — {group_label}  |  可用: {total_available} 条  |  本批: {len(rows)} 条")
    if args.dry_run:
        print(f"  [DRY RUN] 仅预览，不调 LLM 也不保存")
    print(f"{'='*110}")

    if not rows:
        print("  没有待处理记录。")
        return

    results = []
    t0 = time.time()

    for i, row in enumerate(rows):
        t_start = time.time()
        comp = await process_record(row, dry_run=args.dry_run)
        elapsed = time.time() - t_start

        results.append(comp)

        # 单行输出
        gap_str = f"{comp['gap']:+.2f}" if comp['gap'] is not None else "  N/A"
        llm_text = f"{comp['llm_text_raw']:+.2f}" if comp['llm_text_raw'] is not None else "  SKIP" if args.dry_run else " FAIL"

        polarity_icon = {
            "positive": "P", "negative": "N", "neutral": "·",
            "complex_positive": "cP", "complex_negative": "cN", "complex_balanced": "cB",
        }
        lp = polarity_icon.get(comp["lex_polarity"], "?")
        jp = polarity_icon.get(comp["llm_polarity"], "?") if comp["llm_polarity"] else ("?" if args.dry_run else "?")

        print(f"  [{i+1:>2}/{len(rows)}] ID={comp['id']:>4} 词:{comp['lex_text_raw']:>+6.2f}{lp:>3}  "
              f"LLM:{llm_text:>6}{jp:>3}  gap:{gap_str:>6}  "
              f"{(comp.get('title') or '?'):<14}  {elapsed:4.0f}s")

    # ── 汇总表 ─────────────────────────────────────────
    t_total = time.time() - t0
    print(f"\n{'='*110}")
    print(f"  {'ID':>5} {'标题':<16} {'词库text':>8} {'词库norm':>8} {'词库极性':<12} "
          f"{'LLM text':>8} {'LLM raw':>8} {'LLM极性':<12} {'Gap':>6}")
    print(f"  {'-'*105}")

    polarity_labels = {
        "positive": "积极", "negative": "消极", "neutral": "中性",
        "complex_positive": "复杂积极", "complex_negative": "复杂消极", "complex_balanced": "复杂平衡",
    }

    llm_success = 0
    for r in results:
        lt = f"{r['llm_text_raw']:+.2f}" if r['llm_text_raw'] is not None else ("  SKIP" if args.dry_run else "  FAIL")
        lr = f"{r['llm_combined_raw']:+.2f}" if r['llm_combined_raw'] is not None else ("    -" if args.dry_run else "  FAIL")
        jp = polarity_labels.get(r['llm_polarity'], r['llm_polarity'] or "?")
        gap = f"{r['gap']:+.2f}" if r['gap'] is not None else ("    -" if args.dry_run else "  N/A")
        lp = polarity_labels.get(r['lex_polarity'], r['lex_polarity'])
        print(f"  {r['id']:>5} {(r.get('title') or '?'):<16} {r['lex_text_raw']:>+8.2f} {r['lex_combined_norm']:>+8.3f} {lp:<12} "
              f"{lt:>8} {lr:>8} {jp:<12} {gap:>6}")
        if r['llm_polarity']:
            llm_success += 1

    # ── 统计 ─────────────────────────────────────────
    if not args.dry_run:
        polarity_diff = sum(1 for r in results if r["lex_polarity"] != r["llm_polarity"] and r["llm_polarity"])
        positive_bias = sum(1 for r in results if r["gap"] is not None and r["gap"] > 2)
        negative_bias = sum(1 for r in results if r["gap"] is not None and r["gap"] < -2)

        print(f"\n{'='*110}")
        print(f"  本批统计")
        print(f"  LLM 成功: {llm_success}/{len(results)}")
        print(f"  极性分歧: {polarity_diff} 条（词库与 LLM 极性不同）")
        print(f"  词库偏正: {positive_bias} 条（gap > +2，词库比 LLM 积极）")
        print(f"  词库偏负: {negative_bias} 条（gap < -2，词库比 LLM 消极）")
        print(f"  总耗时: {t_total:.0f}s  |  平均: {t_total/len(results):.1f}s/条")

        if llm_success > 0:
            avg_gap = sum(r["gap"] for r in results if r["gap"] is not None) / llm_success
            max_gap = max((r["gap"] for r in results if r["gap"] is not None), default=0)
            min_gap = min((r["gap"] for r in results if r["gap"] is not None), default=0)
            print(f"  平均 gap: {avg_gap:+.2f}  |  最大 gap: {max_gap:+.2f}  |  最小 gap: {min_gap:+.2f}")
    else:
        print(f"\n  [DRY RUN] 未执行 LLM 调用和保存。")


if __name__ == "__main__":
    asyncio.run(main())
