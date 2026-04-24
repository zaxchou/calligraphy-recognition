"""重新向量化并入库 PDF 提取的图片

用法:
    python re_embed_pdf_images.py [--book-id ID] [--dry-run] [--batch-size 10] [--start 0]
"""
import asyncio
import argparse
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ENV_FILE", ".env")

# 修改事件循环策略（Windows 上避免 ProactorEventLoop 问题）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def re_embed_images(book_id: str, dry_run: bool = False, batch_size: int = 10, start: int = 0):
    from app.modules.pantianshou_composition.embedding_service import EmbeddingService
    from app.modules.pantianshou_composition.qdrant_client import upsert_images
    import sqlite3
    import requests

    svc = EmbeddingService()
    print(f"multimodal_enabled: {svc.multimodal_enabled}")
    if not svc.multimodal_enabled:
        print("ERROR: DashScope multimodal embedding 未启用！")
        return

    # 从 SQLite 获取图片记录
    conn = sqlite3.connect("data/knowledge.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM extracted_images WHERE book_id=? ORDER BY page, figure_id",
              (book_id,))
    rows = c.fetchall()
    print(f"Total images in SQLite: {len(rows)}")

    # 获取书名
    c.execute("SELECT title FROM pdf_books WHERE id=?", (book_id,))
    book_row = c.fetchone()
    book_title = book_row["title"] if book_row else "Unknown"
    print(f"Book: {book_title}")

    # 检查已有向量
    resp = requests.post("http://localhost:6333/collections/knowledge_images/points/count",
        json={"filter": {"must": [{"key": "book_id", "match": {"value": book_id}}]}, "exact": True})
    existing = resp.json().get("result", {}).get("count", 0)
    print(f"Existing vectors in Qdrant: {existing}")

    # 过滤已入库的
    rows_to_process = rows[start:]
    print(f"Images to process: {len(rows_to_process)} (starting from offset {start})")

    if dry_run:
        print("\n[DRY RUN] Would process:")
        for i, row in enumerate(rows_to_process[:5]):
            print(f"  {i+1}. {row['figure_id']} page={row['page']} file={row['file_name']}")
        print(f"  ... and {max(0, len(rows_to_process)-5)} more")
        conn.close()
        return

    success = 0
    failed = 0
    batch_points = []
    t0 = time.time()

    for idx, row in enumerate(rows_to_process):
        img_path = row["stored_path"]
        figure_id = row["figure_id"] or f"img_p{row['page']}"
        page = row["page"]
        file_name = row["file_name"]
        caption = row["caption"] or ""

        if not os.path.exists(img_path):
            print(f"  SKIP (file not found): {img_path}")
            failed += 1
            continue

        try:
            emb_result = await svc.embed_image(img_path)
            vector_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"knowledge_img:{book_id}_{row['id']}"))

            point = {
                "id": vector_id,
                "vector": emb_result.embedding,
                "payload": {
                    "type": "pdf_extracted_image",
                    "source": "pdf_upload",
                    "book_id": book_id,
                    "book_title": book_title,
                    "figure_id": figure_id,
                    "caption": caption,
                    "page_number": page,
                    "image_path": row["stored_url"] or f"/api/v1/knowledge/images/{book_id}/{file_name}",
                    "bbox": row["bbox"] if row["bbox"] else {},
                    "related_chunk_ids": [],
                    "metadata": {
                        "book_title": book_title,
                        "file_name": file_name,
                    },
                },
            }

            # 更新 SQLite vector_id
            c.execute("UPDATE extracted_images SET vector_id=? WHERE id=?",
                      (vector_id, row["id"]))

            batch_points.append(point)
            success += 1

            if len(batch_points) >= batch_size:
                upsert_images(batch_points, book_id)
                conn.commit()
                elapsed = time.time() - t0
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                eta = (len(rows_to_process) - idx - 1) / rate if rate > 0 else 0
                print(f"  Batch upserted: {len(batch_points)} | "
                      f"Progress: {idx+1}/{len(rows_to_process)} | "
                      f"Success: {success} Failed: {failed} | "
                      f"Rate: {rate:.1f}/s | ETA: {eta/60:.1f}min")
                batch_points = []

        except Exception as e:
            print(f"  FAIL: {figure_id} page={page}: {type(e).__name__}: {e}")
            failed += 1

    # 最后一批
    if batch_points:
        upsert_images(batch_points, book_id)
        conn.commit()

    elapsed = time.time() - t0
    print(f"\n=== Done ===")
    print(f"Success: {success}, Failed: {failed}, Time: {elapsed:.1f}s")

    # 最终确认
    resp2 = requests.post("http://localhost:6333/collections/knowledge_images/points/count",
        json={"filter": {"must": [{"key": "book_id", "match": {"value": book_id}}]}, "exact": True})
    final_count = resp2.json().get("result", {}).get("count", 0)
    print(f"Final Qdrant vectors for this book: {final_count}")

    # 更新 knowledge_tasks.result 中的 images_vectorized
    import json
    c.execute("SELECT id, result FROM knowledge_tasks WHERE book_id=? AND status='completed' ORDER BY updated_at DESC LIMIT 1", (book_id,))
    task_row = c.fetchone()
    if task_row:
        task_id = task_row[0]
        result_data = json.loads(task_row[1]) if task_row[1] else {}
        result_data["images_vectorized"] = final_count
        c.execute("UPDATE knowledge_tasks SET result=? WHERE id=?",
                  (json.dumps(result_data, ensure_ascii=False), task_id))
        conn.commit()
        print(f"Updated task {task_id} images_vectorized={final_count}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id", default="532c7064-b1ba-4cc3-a330-e633eaef0d3d")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--start", type=int, default=0)
    args = parser.parse_args()

    asyncio.run(re_embed_images(args.book_id, args.dry_run, args.batch_size, args.start))
