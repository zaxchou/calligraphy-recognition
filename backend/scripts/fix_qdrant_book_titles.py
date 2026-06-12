"""
修复 Qdrant 向量中 book_title 为 UUID 的问题
用 SQLite 中正确的 book.title 覆盖 Qdrant payload 中的 book_title
"""
import os, sys, json, re, logging, urllib.request, urllib.error

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
QDRANT_URL = "http://deploy-qdrant-1:6333"
COLLECTIONS = ["knowledge_texts", "knowledge_images", "knowledge_tables"]

def scroll_points(collection):
    points = []
    offset = None
    while True:
        body = {"limit": 100, "with_payload": True, "with_vector": False}
        if offset:
            body["offset"] = offset
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{collection}/points/scroll",
            data=data, headers={"Content-Type": "application/json"}
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        batch = resp.get("result", {}).get("points", [])
        points.extend(batch)
        next_offset = resp.get("result", {}).get("next_page_offset")
        if next_offset is None:
            break
        offset = next_offset
    return points

def set_payloads(collection, points):
    """用 set-payload 覆写 book_title 字段"""
    if not points:
        return 0
    ops = [{"id": p["id"], "payload": {"book_title": p["payload"]["book_title"]}} for p in points]
    body = json.dumps({"points": ops}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}/points/set-payload",
        data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        return result.get("result", {}).get("num_updated", len(points))
    except urllib.error.HTTPError as e:
        logger.error(f"set-payload failed: {e.code} {e.read().decode()}")
        return 0

def main():
    import sqlite3
    for p in ["/app/data/knowledge.db",
              os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.db")]:
        if os.path.exists(p):
            knowledge_db = p
            break
    else:
        logger.error("cannot find knowledge.db")
        return

    logger.info(f"连接数据库: {knowledge_db}")
    conn = sqlite3.connect(knowledge_db)
    rows = conn.execute("SELECT id, title FROM pdf_books").fetchall()
    conn.close()

    book_titles = {}
    for bid, title in rows:
        t = title or ''
        if t and not UUID_RE.match(str(t)):
            book_titles[bid] = t
    logger.info(f"已加载 {len(book_titles)} 个有效书名")

    total_fixed = 0
    for collection in COLLECTIONS:
        logger.info(f"扫描 {collection}...")
        points = scroll_points(collection)
        to_fix = []
        for p in points:
            pl = p.get("payload", {})
            old_bt = pl.get("book_title", "")
            if old_bt and not UUID_RE.match(old_bt):
                continue
            book_id = pl.get("book_id") or pl.get("book")
            if not book_id:
                continue
            correct = book_titles.get(book_id)
            if not correct:
                continue
            pl["book_title"] = correct
            if isinstance(pl.get("metadata"), dict):
                pl["metadata"]["book_title"] = correct
            to_fix.append(p)

        if not to_fix:
            logger.info(f"  {collection}: 无需修复")
            continue
        n = set_payloads(collection, to_fix)
        total_fixed += n
        logger.info(f"  {collection}: 修复了 {n} 个点的 book_title")

    logger.info(f"总计修复 {total_fixed} 个点")
    return total_fixed

if __name__ == "__main__":
    main()
