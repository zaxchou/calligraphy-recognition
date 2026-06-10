"""
恢复卡住的文献处理任务 + 元数据提取
"""
import os, sys, sqlite3, time, logging, json, re, asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.modules.pantianshou_composition.knowledge_ingest_v2 import process_pdf_file_sync
from app.modules.pantianshou_composition.metadata_extractor import extract_metadata

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger('recover')
UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def is_bad(t):
    return not t or bool(UUID_RE.match(t.strip()))

def update_metadata(book_id, fname):
    """LLM 提取元数据写回 SQLite"""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT full_md, title, author, journal, publish_year, abstract, keywords FROM pdf_books WHERE id=?", (book_id,)).fetchone()
        if not row or not row[0]:
            conn.close()
            return
        # 不需要提取的跳过
        if not is_bad(row[1]) and row[2] and row[3]:
            conn.close()
            return
        meta = asyncio.run(extract_metadata(row[0]))
        if not meta:
            conn.close()
            return
        updates = {}
        if is_bad(row[1]) and meta.get('title'): updates['title'] = meta['title']
        if not row[2] and meta.get('authors'):
            a = meta['authors']
            updates['author'] = a[0] if isinstance(a, list) else a
        if not row[3] and meta.get('journal'): updates['journal'] = meta['journal']
        if not row[4] and meta.get('publish_year'): updates['publish_year'] = meta['publish_year']
        if not row[5] and meta.get('abstract'): updates['abstract'] = meta['abstract']
        if not row[6] and meta.get('keywords'): updates['keywords'] = json.dumps(meta['keywords'], ensure_ascii=False)
        if updates:
            set_clause = ', '.join(f'{k}=?' for k in updates)
            conn.execute(f"UPDATE pdf_books SET {set_clause} WHERE id=?", (*updates.values(), book_id))
            conn.commit()
            logger.info(f"[{fname}] 元数据更新: {list(updates.keys())}")
        conn.close()
    except Exception as e:
        logger.warning(f"[{fname}] 元数据提取失败: {e}")

def recover():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE knowledge_tasks SET status='queued', stage='queued', progress=0 WHERE task_type='pdf_ingest' AND status!='completed'")
    conn.execute("UPDATE pdf_books SET status='processing' WHERE document_type='literature' AND status!='completed'")
    conn.commit()
    cur = conn.execute("""
        SELECT kt.id, kt.book_id, pb.stored_path, pb.artist_id, pb.file_name
        FROM knowledge_tasks kt JOIN pdf_books pb ON kt.book_id = pb.id
        WHERE kt.status='queued' AND kt.task_type='pdf_ingest'
    """)
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    logger.info(f"需要处理 {total} 个文献")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def process_one(task_id, book_id, pdf_path, artist_id, fname):
        logger.info(f"[{fname}] 开始处理...")
        try:
            process_pdf_file_sync(pdf_path=pdf_path, task_id=task_id, book_id=book_id, artist_id=artist_id, document_type='literature')
            update_metadata(book_id, fname)
            logger.info(f"[{fname}] ✅ 完成")
            return True
        except Exception as e:
            logger.error(f"[{fname}] ❌ 失败: {e}")
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = []
        for tid, bid, sp, aid, fn in rows:
            if not os.path.exists(sp):
                logger.warning(f"[{fn}] 文件不存在: {sp}")
                continue
            futures.append(pool.submit(process_one, tid, bid, sp, aid, fn))
        for f in as_completed(futures):
            pass

if __name__ == '__main__':
    recover()
