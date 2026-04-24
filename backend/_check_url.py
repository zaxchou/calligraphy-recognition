"""检查 id=57-67 返回的 thumbnail_url"""
import sqlite3, sys
sys.path.insert(0, '.')
from app.core.path_utils import get_static_url

DB = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\calligraphy.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT id, thumbnail_path FROM tubi_analyses WHERE id BETWEEN 57 AND 67 ORDER BY id")
for row in cur.fetchall():
    tid, thumb = row
    url = get_static_url(thumb) if thumb else "EMPTY"
    print(f"ID={tid}: DB='{thumb}' -> URL='{url}'")
conn.close()