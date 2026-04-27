"""采样验证：低可信度作品中 DeepSeek 的实际分歧率"""
import sys, os, json, sqlite3, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.services.inscription_content_analyzer import classify_inscription_v4, llm_analyze_combined
from collections import Counter

DB = "data/calligraphy.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT id, inscription_content, year, artist
    FROM tubi_analyses WHERE artist = '李鱓'
    AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 5
    ORDER BY id
""").fetchall()

candidates = []
for row in rows:
    v4 = classify_inscription_v4(row["inscription_content"], year=row["year"], artist=row["artist"])
    conf = v4.get("confidence", 0)
    if conf < 0.6:
        candidates.append((row, v4, conf))

print(f"低可信度(<0.6)作品: {len(candidates)} 幅\n")

# 取前20幅
sample = candidates[:20]
divergence_count = 0
no_change_count = 0
llm_fail = 0

for i, (row, v4, conf) in enumerate(sample):
    text = row["inscription_content"] or ""
    v4_primary = v4["themes"][0] if v4.get("themes") else None
    v4_theme_name = v4_primary["name"] if v4_primary else "?"
    
    raw = asyncio.run(llm_analyze_combined(text, artist=row["artist"]))
    
    if not raw.get("success") or not raw.get("themes"):
        llm_fail += 1
        print(f"  [{i+1}] LLM_FAIL conf={conf:.2f} [{v4_theme_name}]")
        continue

    llm_primary = raw["themes"][0]
    llm_code = llm_primary.get("code", 0)

    if v4_primary and llm_code != v4_primary.get("code"):
        divergence_count += 1
        print(f"  [{i+1}] FIX conf={conf:.2f}: [{v4_theme_name}] -> [{llm_primary['name']}] (text: {text[:30]})")
    else:
        no_change_count += 1

print(f"\n采样 {len(sample)} 幅:")
print(f"  分歧: {divergence_count} ({(divergence_count/len(sample))*100:.0f}%)")
print(f"  无分歧: {no_change_count} ({(no_change_count/len(sample))*100:.0f}%)")
print(f"  LLM调用失败: {llm_fail}")
print(f"预计总修正: {divergence_count/len(sample)*len(candidates):.0f} 幅")

conn.close()
