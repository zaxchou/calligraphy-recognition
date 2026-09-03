"""
v2.0 §2.8 — 知识库命令行工具。

用法（在 backend/ 目录或容器内 /app 下）：
    python -m app.cli reindex-qdrant [--db PATH] [--yes]

设计约定（2026-09-04）：
- 权威源是 SQLite（knowledge.db 的 text_chunks 表）；
- 本命令按 SQLite 全量重建 Qdrant 集合，用于修复"重建向量库后
  text_chunks.vector_id 与 Qdrant id 失配"导致的搜索 0 结果问题
  （原 deploy/fast_reindex.py 的收编版本，路径不再硬编码 /app）。
"""
import argparse
import json
import sqlite3
import sys


def cmd_reindex_qdrant(args: argparse.Namespace) -> int:
    from app.modules.pantianshou_composition.database import DB_PATH
    from app.modules.pantianshou_composition.embedding_service import EmbeddingService
    from app.modules.pantianshou_composition import qdrant_client as qc

    db_path = args.db or DB_PATH

    if not args.yes:
        print("此操作将删除并重建 Qdrant 知识库集合（knowledge_texts）。")
        answer = input("确认继续? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消")
            return 1

    emb = EmbeddingService()
    qc.ensure_collection(qc.KNOWLEDGE_TEXTS_COLLECTION, vector_size=1024, recreate=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, book_id, page_start, content, meta_data, chapter_title, chunk_index "
        "FROM text_chunks ORDER BY book_id, page_start, id"
    )
    rows = cur.fetchall()
    conn.close()
    print(f"权威源 {db_path}: 共 {len(rows)} 个文本块")

    batch: list[dict] = []
    last_bid = None
    done = 0

    def _flush(batch, bid):
        if batch:
            qc.upsert_text_chunks(batch, bid)

    for i, (cid, bid, ps, text, md, ch, ci) in enumerate(rows):
        if not text or len(text.strip()) < 5:
            continue
        meta = json.loads(md) if md else {}
        try:
            r = emb.embed_text_sync(text[:2000])
            if not r or not r.embedding:
                continue
            # 按 book_id 分组批量写入，避免跨书归属
            if last_bid is not None and bid != last_bid:
                _flush(batch, last_bid)
                batch = []
            last_bid = bid
            batch.append({"id": str(cid), "vector": r.embedding, "content": text,
                          "chapter": ch or "", "page_start": ps or 0, "page_end": ps or 0,
                          "chunk_index": ci or 0, "metadata": meta})
        except Exception as e:
            print(f"  [{i}] error: {e}")
            continue
        if len(batch) >= 50:
            _flush(batch, bid)
            batch = []
    _flush(batch, last_bid)

    cnt = qc.count_collection(qc.KNOWLEDGE_TEXTS_COLLECTION)
    print(f"DONE: Qdrant knowledge_texts 共 {cnt} 点")
    if cnt != len(rows):
        print(f"⚠️ 计数不一致（SQLite {len(rows)} vs Qdrant {cnt}），请检查空文本块与 embedding 失败项")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="墨林百科运维命令行")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reindex = sub.add_parser("reindex-qdrant", help="按 SQLite 全量重建 Qdrant 知识库集合")
    p_reindex.add_argument("--db", help="knowledge.db 路径（默认取模块配置）")
    p_reindex.add_argument("--yes", action="store_true", help="跳过确认")

    args = parser.parse_args(argv)
    if args.command == "reindex-qdrant":
        return cmd_reindex_qdrant(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
