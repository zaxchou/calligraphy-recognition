import sqlite3

conn = sqlite3.connect('data/knowledge.db')

# 查看表结构
for table in ['extracted_images', 'text_chunks']:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    print(f"=== {table} ===")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")
    print()

# 查看图片数据
cursor = conn.execute('SELECT id, book_id, file_name FROM extracted_images LIMIT 3')
print('=== 图片数据 ===')
for row in cursor:
    print(f'ID: {row[0]}, Book: {row[1][:12]}..., File: {row[2]}')

# 查看文本块数据
cursor = conn.execute('SELECT * FROM text_chunks LIMIT 1')
cols = [desc[0] for desc in cursor.description]
print(f"\n=== text_chunks 列: {cols} ===")
row = cursor.fetchone()
if row:
    for i, col in enumerate(cols):
        val = str(row[i])[:60] if row[i] else "NULL"
        print(f"  {col}: {val}")

conn.close()
