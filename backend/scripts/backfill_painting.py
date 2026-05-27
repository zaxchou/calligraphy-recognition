"""
批量回填画材数据
────────────────────────────────────────
为没有画材数据的作品重新分析画材并更新数据库
"""

import sqlite3
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.inscription_content_analyzer import match_painting_materials


def backfill_painting_materials():
    """批量回填画材数据"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calligraphy.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 查找没有画材数据的作品
    cur.execute("SELECT id, title, content_analysis FROM tubi_analyses WHERE content_analysis IS NOT NULL")
    rows = cur.fetchall()

    updated = 0
    skipped = 0

    for row in rows:
        try:
            ca = json.loads(row["content_analysis"])
            v4 = ca.get("v4_signals", {})
            painting = v4.get("painting", [])

            if painting:  # 已有画材数据
                skipped += 1
                continue

            title = row["title"] or ""
            matches = match_painting_materials(title, None, title)

            if not matches:
                continue

            # 更新 v4_signals
            if "v4_signals" not in ca:
                ca["v4_signals"] = {}
            ca["v4_signals"]["painting"] = matches

            # 保存
            cur.execute("UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
                       (json.dumps(ca, ensure_ascii=False), row["id"]))
            updated += 1

            if updated % 50 == 0:
                print(f"  已更新 {updated} 条...")
                conn.commit()

        except Exception as e:
            print(f"  错误 (ID={row['id']}): {e}")

    conn.commit()
    conn.close()

    print(f"\n完成:")
    print(f"  总作品: {len(rows)}")
    print(f"  已有画材: {skipped}")
    print(f"  新增画材: {updated}")


if __name__ == "__main__":
    backfill_painting_materials()
