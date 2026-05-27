#!/usr/bin/env python3
"""
批量重分析 v3 情感引擎
────────────────────────────────────────
为所有尚未运行 v3 分析的记录运行词库基线引擎。
支持 --dry-run 预览，--force 强制重跑全部。

用法:
  python scripts/batch_reanalyze_v3.py                       # 增量模式
  python scripts/batch_reanalyze_v3.py --dry-run             # 预览
  python scripts/batch_reanalyze_v3.py --force               # 强制重跑全部
  python scripts/batch_reanalyze_v3.py --limit 50            # 只处理前 50 条
"""

import sys
import os
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_connection
from app.services.molin_engine import analyze as molin_analyze


def get_v3_status(cur) -> dict:
    """统计 v3 分析状态"""
    total = cur.execute("SELECT COUNT(*) FROM tubi_analyses WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2").fetchone()[0]
    v3 = cur.execute("""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
          AND content_analysis IS NOT NULL AND content_analysis != '' AND content_analysis != '{}'
          AND json_extract(content_analysis, '$.analysis_method') IN ('lexicon_only', 'llm_corrected')
    """).fetchone()[0]
    v2 = cur.execute("""
        SELECT COUNT(*) FROM tubi_analyses
        WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
          AND content_analysis IS NOT NULL AND content_analysis != '' AND content_analysis != '{}'
          AND (json_extract(content_analysis, '$.analysis_method') IS NULL
               OR json_extract(content_analysis, '$.analysis_method') = '')
    """).fetchone()[0]
    no_analysis = total - v3 - v2
    return {"total": total, "v3": v3, "v2": v2, "no_analysis": no_analysis}


def needs_v3(content_analysis: str, force: bool = False) -> bool:
    """判断记录是否需要 v3 分析"""
    if not content_analysis:
        return True
    try:
        ca = json.loads(content_analysis)
    except (json.JSONDecodeError, TypeError):
        return True
    if not ca:
        return True
    if force:
        return True
    # 已有 lexicon_scores + v3 analysis_method → 已完成
    if ca.get("lexicon_scores") and ca.get("analysis_method") in ("lexicon_only", "llm_corrected"):
        return False
    return True


def run_batch(conn, rows: list, dry_run: bool = False, batch_size: int = 10, delay: float = 2.0):
    """对一批记录运行 v3 分析"""
    cur = conn.cursor()
    processed = 0
    errors = 0

    for i, row in enumerate(rows):
        record_id = row["id"]
        text = row["inscription_content"] or ""
        year = row["year"]
        artist = row["artist"]
        width_cm = row["artwork_width_cm"]
        height_cm = row["artwork_height_cm"]
        seal_content = row["seal_content"]

        if not text or len(text.strip()) < 2:
            continue

        # 读取旧的 content_analysis 以保留 themes 等字段
        old_ca = {}
        if row["content_analysis"]:
            try:
                old_ca = json.loads(row["content_analysis"])
            except Exception:
                old_ca = {}

        # 从旧数据中提取主题（如果有）
        themes = old_ca.get("themes", []) if isinstance(old_ca, dict) else []

        if dry_run:
            print(f"  [DRY RUN] ID={record_id} year={year} artist={artist} text={text[:40]}...")
            continue

        try:
            result = molin_analyze(
                text=text,
                width_cm=width_cm,
                height_cm=height_cm,
                year=year,
                artist=artist,
                seal_content=seal_content,
                themes=themes,
            )

            # 构建 lexicon_scores
            lexicon_scores = {
                "version": "3.1",
                "text": {"raw": result.text.raw, "normalized": result.text.normalized, "confidence": result.text.confidence, "has_data": result.text.has_data},
                "spatial": {"raw": result.spatial.raw, "normalized": result.spatial.normalized, "confidence": result.spatial.confidence, "has_data": result.spatial.has_data},
                "painting": {"raw": result.painting.raw, "normalized": result.painting.normalized, "confidence": result.painting.confidence, "has_data": result.painting.has_data},
                "size": {"raw": result.size.raw, "normalized": result.size.normalized, "confidence": result.size.confidence, "has_data": result.size.has_data},
                "period": {"raw": result.period.raw, "normalized": result.period.normalized, "confidence": result.period.confidence, "has_data": result.period.has_data},
                "seal": {"raw": result.seal.raw, "normalized": result.seal.normalized, "confidence": result.seal.confidence, "has_data": result.seal.has_data},
                "theme": {"raw": result.theme.raw, "normalized": result.theme.normalized, "confidence": result.theme.confidence, "has_data": result.theme.has_data},
                "brush_ink": {"raw": result.brush_ink.raw, "normalized": result.brush_ink.normalized, "confidence": result.brush_ink.confidence, "has_data": result.brush_ink.has_data},
                "combined_raw": result.combined_raw,
                "combined_normalized": result.combined_normalized,
            }

            # 更新 content_analysis
            new_ca = dict(old_ca) if isinstance(old_ca, dict) else {}
            new_ca["lexicon_scores"] = lexicon_scores
            new_ca["analysis_method"] = "lexicon_only"
            new_ca["analysis_version"] = 3

            # 更新 combined_sentiment（保持与 analyze_single_record 一致的格式）
            new_ca["combined_sentiment"] = {
                "polarity": result.polarity,
                "reasoning": result.reasoning,
                "text_score": result.text.raw,
                "spatial_score": result.spatial.raw,
                "seal_score": result.seal.raw,
                "painting_score": result.painting.raw,
                "time_score": result.period.raw,
                "size_score": result.size.raw,
                "theme_score": result.theme.raw,
                "brush_ink_score": result.brush_ink.raw,
                "combined_score": round(result.combined_raw, 2),
                "vader_normalized": round(result.combined_normalized, 3),
                "vader_alpha": 8.0,
                "weights": result.weights_used,
                "method": "lexicon_only",
                "has_data": {
                    "text": result.text.has_data,
                    "spatial": result.spatial.has_data,
                    "painting": result.painting.has_data,
                    "size": result.size.has_data,
                    "period": result.period.has_data,
                    "seal": result.seal.has_data,
                    "theme": result.theme.has_data,
                    "brush_ink": result.brush_ink.has_data,
                },
                "dimension_details": {
                    "text": {"signals": result.text.signals},
                    "spatial": {"signals": result.spatial.signals},
                    "painting": {"signals": result.painting.signals},
                    "size": {},
                    "period": {},
                    "seal": {"signals": result.seal.signals},
                    "theme": {"signals": result.theme.signals},
                },
            }

            cur.execute("""
                UPDATE tubi_analyses
                SET content_analysis = ?
                WHERE id = ?
            """, (json.dumps(new_ca, ensure_ascii=False), record_id))

            if (i + 1) % batch_size == 0:
                conn.commit()
                print(f"  [{i+1}/{len(rows)}] Batched up to ID={record_id}")

            polarity_tag = "P" if result.polarity == "positive" else "N" if result.polarity == "negative" else "."
            print(f"  [{i+1}/{len(rows)}] ID={record_id} {result.combined_normalized:+.3f} {polarity_tag} {text[:30]}...")

        except Exception as e:
            errors += 1
            print(f"  [ERROR] ID={record_id}: {e}")

        processed += 1

    # 最终提交
    conn.commit()
    return processed, errors


def main():
    parser = argparse.ArgumentParser(description="批量重分析 v3 情感引擎")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不修改数据库")
    parser.add_argument("--force", action="store_true", help="强制重跑全部记录")
    parser.add_argument("--limit", type=int, default=0, help="限制处理数量")
    parser.add_argument("--batch-size", type=int, default=10, help="每批提交数（默认 10）")
    parser.add_argument("--delay", type=float, default=2.0, help="批次间延迟秒数（默认 2.0）")
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    # 统计状态
    status = get_v3_status(cur)
    print(f"=== v3 情感引擎批量重分析 ===")
    print(f"总记录: {status['total']}")
    print(f"已 v3: {status['v3']}")
    print(f"旧版  : {status['v2']}")
    print(f"无分析: {status['no_analysis']}")

    # 查询需要分析的记录
    if args.force:
        # 强制：所有有题跋的记录
        cur.execute("""
            SELECT id, inscription_content, year, artist,
                   artwork_width_cm, artwork_height_cm, seal_content,
                   content_analysis
            FROM tubi_analyses
            WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
            ORDER BY id
        """)
    else:
        # 增量：content_analysis 为空或无 analysis_method=3
        cur.execute("""
            SELECT id, inscription_content, year, artist,
                   artwork_width_cm, artwork_height_cm, seal_content,
                   content_analysis
            FROM tubi_analyses
            WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
              AND (content_analysis IS NULL
                   OR content_analysis = ''
                   OR content_analysis = '{}'
                   OR json_extract(content_analysis, '$.analysis_method') IS NULL
                   OR json_extract(content_analysis, '$.analysis_method') = ''
                   OR json_extract(content_analysis, '$.analysis_version') IS NULL
                   OR json_extract(content_analysis, '$.analysis_version') < 3)
            ORDER BY id
        """)

    rows = cur.fetchall()
    print(f"\n待处理: {len(rows)} 条")

    if not rows:
        print("没有需要处理的记录。")
        conn.close()
        return

    if args.limit > 0:
        rows = rows[:args.limit]
        print(f"限制为前 {args.limit} 条")

    # 处理
    processed, errors = run_batch(
        conn, rows,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        delay=args.delay,
    )

    print(f"\n=== 完成 ===")
    print(f"处理: {processed}, 错误: {errors}")
    if not args.dry_run:
        print("数据库已更新。")

    conn.close()


if __name__ == "__main__":
    main()
