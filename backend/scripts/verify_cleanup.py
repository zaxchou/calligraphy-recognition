"""验证清理结果"""
import requests
import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

QDRANT_URL = "http://localhost:6333"

# 检查 Qdrant 向量数量
print("=== Qdrant 向量统计 ===")
for collection in ["knowledge_texts", "knowledge_images", "knowledge_tables"]:
    r = requests.post(f"{QDRANT_URL}/collections/{collection}/points/count", json={})
    count = r.json().get("result", {}).get("count", 0)
    print(f"  {collection}: {count} 个点")

# 检查 SQLite 书籍数量
print("\n=== SQLite 书籍统计 ===")
conn = sqlite3.connect("data/knowledge.db")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM pdf_books")
count = cursor.fetchone()[0]
print(f"  pdf_books: {count} 本")

# 列出所有书籍
cursor.execute("SELECT id, title, file_name FROM pdf_books")
for row in cursor.fetchall():
    print(f"    - {row[1] or row[2]} (id={row[0]})")
conn.close()

# 验证没有孤立向量
print("\n=== 验证孤立向量 ===")
conn = sqlite3.connect("data/knowledge.db")
cursor = conn.cursor()
cursor.execute("SELECT id FROM pdf_books")
sqlite_book_ids = set(row[0] for row in cursor.fetchall())
conn.close()

for collection in ["knowledge_texts", "knowledge_images"]:
    r = requests.post(
        f"{QDRANT_URL}/collections/{collection}/points/scroll",
        json={"limit": 1000, "with_payload": ["book_id"], "with_vector": False}
    )
    points = r.json().get("result", {}).get("points", [])
    qdrant_book_ids = set(p.get("payload", {}).get("book_id") for p in points if p.get("payload", {}).get("book_id"))
    orphan_ids = qdrant_book_ids - sqlite_book_ids
    if orphan_ids:
        print(f"  {collection}: 发现 {len(orphan_ids)} 个孤立 book_id!")
        for bid in orphan_ids:
            print(f"    - {bid}")
    else:
        print(f"  {collection}: 无孤立向量 ✓")
