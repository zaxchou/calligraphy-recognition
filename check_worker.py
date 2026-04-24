import sqlite3
conn = sqlite3.connect('backend/data/calligraphy.db')
cursor = conn.cursor()

# 检查 tubi_jobs 表中 queued 任务
cursor.execute("SELECT id, image_id, status, created_at, last_error FROM tubi_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 10")
print('tubi_jobs 中排队任务:')
for r in cursor.fetchall():
    print(f'  id={r[0]}, image_id={r[1]}, status={r[2]}, created={r[3]}, last_error={r[4]}')

# 检查 tubi_analyses 中排队任务
cursor.execute("SELECT id, image_id, title, status, created_at FROM tubi_analyses WHERE status = 'queued' ORDER BY created_at ASC LIMIT 10")
print('\ntubi_analyses 中排队任务:')
for r in cursor.fetchall():
    print(f'  id={r[0]}, image_id={r[1]}, title={r[2]}, status={r[3]}, created={r[4]}')

conn.close()