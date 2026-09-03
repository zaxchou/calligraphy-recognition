#!/usr/bin/env python3
"""
AI 分析内容英文翻译全量回填。

扫描 tiba_analysis 表的 content_analysis（JSON）与 analysis_note，
提取全部中文串，调 DeepSeek 批量翻译，写入 ai_text_translations 表。

用法（本仓库根目录 / 后端容器内均可）:
  python backfill_ai_translations.py --dry        # 只统计待翻译条数
  python backfill_ai_translations.py              # 全量回填
  python backfill_ai_translations.py --batch-size 20 --limit-rows 100
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只统计，不翻译")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit-rows", type=int, default=None, help="只扫前 N 行（调试用）")
    args = parser.parse_args()

    from app.core.database import SessionLocal, Base, engine
    import app.models  # noqa: F401 — 注册全部模型后才能 create_all
    Base.metadata.create_all(engine)
    from app.services.ai_translation import backfill

    db = SessionLocal()
    try:
        stats = backfill(db, batch_size=args.batch_size,
                         limit_rows=args.limit_rows, dry=args.dry)
        print("DONE:", stats)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
