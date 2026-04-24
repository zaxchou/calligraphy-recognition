import sqlite3, json

DB_PATH = "z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/calligraphy.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 查看所有 period_phase 的值
cur.execute("SELECT period_phase, COUNT(*) FROM tubi_analyses GROUP BY period_phase ORDER BY period_phase")
print("Period distribution:")
for phase, cnt in cur.fetchall():
    print(f"  '{phase}': {cnt}")

# 查看未分期或空值的记录
print("\n--- Records with NULL/empty period_phase ---")
cur.execute(
    "SELECT id, title, year, period_phase FROM tubi_analyses "
    "WHERE period_phase IS NULL OR period_phase = '' "
    "ORDER BY id"
)
for rid, title, year, phase in cur.fetchall():
    print(f"  ID={rid} | year={year} | phase='{phase}' | {title[:50]}")

# 查看 content_analysis 里的 period 信息
print("\n--- content_analysis period info for those records ---")
cur.execute(
    "SELECT id, title, period_phase, content_analysis FROM tubi_analyses "
    "WHERE (period_phase IS NULL OR period_phase = '') "
    "AND content_analysis IS NOT NULL AND content_analysis != '{}'"
)
for rid, title, phase, ca_str in cur.fetchall():
    data = json.loads(ca_str)
    signals = data.get("signals", {})
    ca_period = data.get("period", "")
    ca_phase = data.get("period_phase", "")
    year_from_ca = signals.get("year", "") if isinstance(signals, dict) else ""
    print(f"  ID={rid} | DB_phase='{phase}' | CA_period='{ca_period}' | CA_phase='{ca_phase}' | signals_year={year_from_ca} | {title[:40]}")

conn.close()
