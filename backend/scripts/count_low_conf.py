"""统计已知数据库中的低可信度作品数"""
import sqlite3, json

conn = sqlite3.connect("data/calligraphy.db")
conn.row_factory = sqlite3.Row

for artist in ["李鱓", "郑燮"]:
    rows = conn.execute(
        "SELECT id, content_analysis FROM tubi_analyses WHERE artist = ? AND content_analysis IS NOT NULL",
        (artist,)
    ).fetchall()

    low = 0
    for r in rows:
        ca = json.loads(r["content_analysis"])
        conf = ca.get("v4_confidence", 0) or 0
        if conf < 0.6:
            low += 1
    print(f"{artist}: 共 {len(rows)} 幅，低可信度(<0.6): {low}")

conn.close()
