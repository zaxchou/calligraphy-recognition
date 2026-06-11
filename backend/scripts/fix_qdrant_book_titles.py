"""
修复 Qdrant 向量中 book_title 为 UUID 的问题
用 SQLite 中正确的 book.title 覆盖 Qdrant payload 中的 book_title
"""
import os
import sys
import json
import re
import logging
import urllib.request

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 添加项目根到 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 解析 UUID 模式
UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

QDRANT_URL = "http://localhost:6333"
COLLECTIONS = ["knowledge_texts", "knowledge_images", "knowledge_tables"]

def get_db():
    """获取 SQLite 连接"""
    from app.database import SessionLocal
    from app.modules.pantianshou_composition.models import PdfBook
    from sqlalchemy.orm import Session
    db = SessionLocal()
    return db

def scroll_points(collection):
    """从 Qdrant 滚动获取所有点"""
    points = []
    offset = None
    while True:
        body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset:
            body["offset"] = offset
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        batch = resp.get("result", {}).get("points", [])
        points.extend(batch)
        next_offset = resp.get("result", {}).get("next_page_offset")
        if next_offset is None:
            break
        offset = next_offset
    return points

def overwrite_payloads(collection, points):
    """批量覆写 payload（不改变向量）"""
    if not points:
        return 0
    ops = [{"id": p["id"], "payload": p["payload"]} for p in points]
    body = json.dumps({"points": ops}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}/points/overwrite",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    return result.get("result", {}).get("num_updated", len(points))

def main():
    from app.database import SessionLocal
    from app.modules.pantianshou_composition.models import PdfBook

    db = SessionLocal()

    # 预加载所有 book_id -> title
    all_books = db.query(PdfBook.id, PdfBook.title, PdfBook.file_name).all()
    book_titles = {}
    for b in all_books:
        t = b.title or ''
        if t and not UUID_RE.match(t):
            book_titles[b.id] = t

    logger.info(f"已加载 {len(book_titles)} 个有效书名")

    total_fixed = 0
    for collection in COLLECTIONS:
        logger.info(f"扫描 {collection}...")
        points = scroll_points(collection)
        to_fix = []
        for p in points:
            pl = p.get("payload", {})
            old_bt = pl.get("book_title", "")

            # 不需要修复
            if old_bt and not UUID_RE.match(old_bt):
                continue

            # 查找正确书名
            book_id = pl.get("book_id") or pl.get("book")
            if not book_id:
                continue
            correct = book_titles.get(book_id)
            if not correct:
                continue

            # 标记修复
            pl["book_title"] = correct
            if isinstance(pl.get("metadata"), dict):
                pl["metadata"]["book_title"] = correct
            to_fix.append(p)

        if not to_fix:
            logger.info(f"  {collection}: 无需修复")
            continue

        n = overwrite_payloads(collection, to_fix)
        total_fixed += n
        logger.info(f"  {collection}: 修复了 {n} 个点的 book_title")

    db.close()
    logger.info(f"总计修复 {total_fixed} 个点")
    return total_fixed

if __name__ == "__main__":
    main()
