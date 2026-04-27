"""验证统一混合引擎输出质量
1. 从 DB 取李鱓低可信度作品样本
2. 用统一引擎跑（规则+低可信度→DeepSeek修正）
3. 对比前后结果
4. 验证偏差检测在预期内
"""
import sys, os, json, sqlite3, asyncio
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.services.inscription_content_analyzer import classify_inscription_v4, llm_analyze_combined
from app.services.tibi_analysis_rules import RULES_VERSION

DB = "data/calligraphy.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# ── 取样本：低可信度和高可信度各取一些 ──
rows = conn.execute("""
    SELECT id, inscription_content, year, title, analysis_note,
           artwork_width_cm, artwork_height_cm, artist
    FROM tubi_analyses WHERE artist = '李鱓'
    AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 5
    ORDER BY id
""").fetchall()

print(f"共 {len(rows)} 幅李鱓作品\n")

# ── 跑统一引擎 ──
results = []
for i, row in enumerate(rows):
    text = row["inscription_content"] or ""
    year = row["year"]
    title = row["title"]
    analysis_note = row["analysis_note"]
    width_cm = row["artwork_width_cm"]
    height_cm = row["artwork_height_cm"]
    artist = row["artist"]

    v4 = classify_inscription_v4(
        text, year=year, title=title, analysis_note=analysis_note,
        width_cm=width_cm, height_cm=height_cm, artist=artist
    )
    conf = v4.get("confidence", 0)

    llm_fixed = False
    if conf < 0.6 and len(text) > 3:
        raw = asyncio.run(llm_analyze_combined(text, artist=artist))
        if raw.get("success") and raw.get("themes"):
            v4_primary = v4["themes"][0] if v4.get("themes") else None
            llm_primary = raw["themes"][0]
            if v4_primary and llm_primary.get("code") != v4_primary.get("code"):
                v4["themes"] = raw["themes"]
                llm_fixed = True

    results.append({
        "id": row["id"],
        "text": text[:40],
        "conf": conf,
        "llm_fixed": llm_fixed,
        "themes": v4["themes"],
        "sentiment": v4["sentiment"],
        "special_rules": v4.get("special_rules", []),
    })
    if (i+1) % 100 == 0:
        print(f"  已处理 {i+1}/{len(rows)}...")

# ── 统计结果 ──
polarities = Counter()
primary_themes = Counter()
all_themes = Counter()
emotion_scores = []
llm_fixed_count = sum(1 for r in results if r["llm_fixed"])

for r in results:
    pol = r["sentiment"]["polarity"]
    polarities[pol] += 1
    es = r["sentiment"].get("emotion_score", 0)
    emotion_scores.append(es)
    if r["themes"]:
        primary_themes[r["themes"][0]["name"]] += 1
    for t in r["themes"]:
        all_themes[t["name"]] += 1

total = len(results)
avg_es = sum(emotion_scores) / total if total else 0

print(f"\n{'='*60}")
print(f"统一引擎验证结果 — {total} 幅")
print(f"{'='*60}")
print(f"LLM 自动修正: {llm_fixed_count} 幅 ({(llm_fixed_count/total*100):.1f}%)")
print()

# 主题分布
print(f"第一主题分布:")
for name in ["咏物寄兴", "身世自况", "画理自叙", "时事讽喻", "吉语祥瑞", "交游赠答"]:
    cnt = primary_themes.get(name, 0)
    pct = cnt/total*100 if total else 0
    bar = "█" * int(pct/5)
    print(f"  {name}: {cnt:4d} 幅 ({pct:5.1f}%) {bar}")

print(f"\n情感分布:")
print(f"  positive: {polarities.get('positive',0)}  ({polarities.get('positive',0)/total*100:.1f}%)")
print(f"  negative: {polarities.get('negative',0)}  ({polarities.get('negative',0)/total*100:.1f}%)")
print(f"  neutral:  {polarities.get('neutral',0)}  ({polarities.get('neutral',0)/total*100:.1f}%)")
print(f"  均值:     {avg_es:+.2f}")

# 可信度分布
high = sum(1 for r in results if r["conf"] >= 0.7)
mid = sum(1 for r in results if 0.4 <= r["conf"] < 0.7)
low = sum(1 for r in results if r["conf"] < 0.4)
print(f"\n可信度分布:")
print(f"  高(≥0.7): {high} ({high/total*100:.1f}%)")
print(f"  中(0.4~0.7): {mid} ({mid/total*100:.1f}%)")
print(f"  低(<0.4): {low} ({low/total*100:.1f}%)")

# 展示 LLM 修正的案例
fixed_samples = [r for r in results if r["llm_fixed"]]
if fixed_samples:
    print(f"\nLLM 修正案例 ({len(fixed_samples)} 幅):")
    for r in fixed_samples[:5]:
        print(f"  id={r['id']} conf={r['conf']:.2f} text='{r['text']}...'")
        themes_str = ", ".join([f"{t['name']}({t.get('confidence',0):.2f})" for t in r['themes'][:3]])
        print(f"    结果: {themes_str}")
        print(f"    情感: {r['sentiment']['polarity']} ({r['sentiment']['emotion_score']:.1f})")

print(f"\n{'='*60}")
print("结论: ", end="")
# 检查是否在 v5.5 预期范围
pos_pct = polarities.get('positive',0)/total*100
neg_pct = polarities.get('negative',0)/total*100
print(f"positive={pos_pct:.1f}%(目标≤45%) negative={neg_pct:.1f}%(目标≥30%) 均值={avg_es:+.2f}(目标≤0.0)")
if pos_pct <= 47 and neg_pct >= 25 and avg_es <= 0.1:
    print("✅ 全部在合理范围内，统一引擎输出质量可接受")
else:
    print("⚠️ 部分指标偏差，需要调整规则")

conn.close()
