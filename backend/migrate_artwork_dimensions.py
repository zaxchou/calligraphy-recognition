"""
数据库迁移：为 tubi_analyses 表新增画作实际尺寸和册页分组字段
运行方式：cd backend && python migrate_artwork_dimensions.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")

NEW_COLUMNS = [
    ("artwork_width_cm", "REAL"),
    ("artwork_height_cm", "REAL"),
    ("album_name", "VARCHAR(200)"),
    ("album_index", "INTEGER"),
]


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 获取已有列名
    cur.execute("PRAGMA table_info(tubi_analyses)")
    existing_cols = {row[1] for row in cur.fetchall()}
    print(f"当前列: {sorted(existing_cols)}")

    added = 0
    for col_name, col_type in NEW_COLUMNS:
        if col_name in existing_cols:
            print(f"  SKIP: {col_name} 已存在")
        else:
            sql = f"ALTER TABLE tubi_analyses ADD COLUMN {col_name} {col_type}"
            try:
                cur.execute(sql)
                print(f"  ADD:  {col_name} ({col_type})")
                added += 1
            except Exception as e:
                print(f"  FAIL: {col_name} - {e}")

    conn.commit()

    # 验证
    cur.execute("PRAGMA table_info(tubi_analyses)")
    final_cols = [row[1] for row in cur.fetchall()]
    print(f"\n完成。新增 {added} 列，共 {len(final_cols)} 列")
    print(f"列名: {final_cols}")

    # 预览数据
    cur.execute("SELECT id, title, artwork_width_cm, artwork_height_cm, album_name, album_index FROM tubi_analyses LIMIT 5")
    print("\n示例数据（前5条）:")
    for row in cur.fetchall():
        print(f"  id={row[0]}, title={row[1]}, w={row[2]}, h={row[3]}, album={row[4]}, idx={row[5]}")

    conn.close()


if __name__ == "__main__":
    print(f"迁移数据库: {DB_PATH}")
    migrate()
