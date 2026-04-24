"""重试 inscription_percent = 0.0 的记录（从 tubi_worker 调用同一逻辑）"""
import sys, os, time, json, sqlite3
from datetime import datetime

# ── 路径 setup ────────────────────────────────────────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'app'))

# ── 日志 ──────────────────────────────────────────────────
LOG_FILE = 'retry_zero_area.log'
def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

# ── 从 batch_process_tubi.py 引入 process_one ─────────────
from batch_process_tubi import process_one

def main():
    conn = sqlite3.connect('data/calligraphy.db')
    conn.text_factory = str
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, filepath, status
        FROM tubi_analyses
        WHERE inscription_percent = 0.0
          AND artist = '李鱓'
          AND filepath IS NOT NULL
        ORDER BY id
    """)
    records = cur.fetchall()
    conn.close()

    total = len(records)
    log(f'=== 开始重试 {total} 条 (inscription_percent=0) ===')

    ok = fail = skip = 0
    for i, (rec_id, title, filepath, old_status) in enumerate(records):
        log(f'[{i+1}/{total}] id={rec_id} {title}')
        if not os.path.exists(filepath):
            log(f'  文件不存在: {filepath}')
            fail += 1
            continue
        # 重置状态为 pending 让 process_one 走完整流程
        conn2 = sqlite3.connect('data/calligraphy.db')
        conn2.text_factory = str
        cur2 = conn2.cursor()
        cur2.execute("UPDATE tubi_analyses SET status='pending' WHERE id=?", (rec_id,))
        conn2.commit()
        conn2.close()
        status, _ = process_one(rec_id)
        if status == 'OK':
            ok += 1
        elif status == 'SKIP':
            skip += 1
        else:
            fail += 1
        time.sleep(0.5)

    log(f'=== 完成: 成功={ok} 跳过={skip} 失败={fail} ===')

if __name__ == '__main__':
    main()
