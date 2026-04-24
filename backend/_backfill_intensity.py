"""回填 content_analysis.sentiment.intensity 字段
从已有的 emotion_score 计算 intensity = round(min(abs(emotion_score) / 3, 1.0), 2)
"""
import sqlite3
import json

DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/calligraphy.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute(
    "SELECT id, content_analysis FROM tubi_analyses "
    "WHERE content_analysis IS NOT NULL AND content_analysis != '{}'"
)
rows = cur.fetchall()
print(f"Total records with content_analysis: {len(rows)}")

updated = 0
skipped = 0

for rid, ca_str in rows:
    try:
        data = json.loads(ca_str)
        s = data.get("sentiment", {})
        if "intensity" in s:
            skipped += 1
            continue
        es = s.get("emotion_score", 0)
        if es is None:
            es = 0
        intensity = round(min(abs(es) / 3, 1.0), 2)
        s["intensity"] = intensity
        data["sentiment"] = s
        cur.execute(
            "UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), rid)
        )
        updated += 1
        print(f"  ID={rid}: emotion_score={es} -> intensity={intensity}")
    except Exception as e:
        print(f"  ID={rid}: ERROR - {e}")

conn.commit()
conn.close()
print(f"\nDone: updated={updated}, skipped={skipped}")
