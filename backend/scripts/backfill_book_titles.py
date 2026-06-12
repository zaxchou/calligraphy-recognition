"""回填 Qdrant 中文献 chunks 的 book_title（从 SQLite 同步正确标题）"""
import sqlite3
import httpx

QDRANT_URL = "http://localhost:6333"
COLLECTION = "knowledge_texts"

def backfill():
    conn = sqlite3.connect("data/knowledge.db")

    # 获取 literature books 的正确标题
    books = conn.execute(
        "SELECT id, title, author FROM pdf_books WHERE document_type = 'literature'"
    ).fetchall()
    book_map = {b[0]: {"title": b[1], "author": b[2]} for b in books}

    # 获取所有 literature chunks 的 vector_id
    chunks = conn.execute("""
        SELECT tc.vector_id, tc.book_id
        FROM text_chunks tc
        JOIN pdf_books pb ON tc.book_id = pb.id
        WHERE pb.document_type = 'literature' AND tc.vector_id IS NOT NULL
    """).fetchall()
    conn.close()

    # 逐条更新 Qdrant payload
    updated = 0
    errors = 0
    for vector_id, book_id in chunks:
        if book_id not in book_map:
            continue
        meta = book_map[book_id]
        try:
            url = f"{QDRANT_URL}/collections/{COLLECTION}/points/payload"
            body = {
                "points": [vector_id],
                "payload": {
                    "book_title": meta["title"] or "",
                    "metadata": {"book_title": meta["title"] or ""},
                }
            }
            resp = httpx.post(url, json=body, timeout=10)
            if resp.status_code == 200:
                updated += 1
            else:
                errors += 1
                print(f"  Error {resp.status_code} for {vector_id[:8]}")
        except Exception as e:
            errors += 1
            print(f"  Exception: {e}")

    print(f"Done: {updated} updated, {errors} errors, {len(chunks)} total")

if __name__ == "__main__":
    backfill()
