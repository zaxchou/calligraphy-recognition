"""全自动情感校准脚本
1. 读取李鱓全部作品
2. 逐条分析，统计每个正负向词的贡献
3. 找出 positive 虚高根因
4. 自动调整规则
5. 重跑对比
"""
import sys, os, json, sqlite3
from collections import Counter, defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.services.inscription_content_analyzer import classify_inscription_v4

DB = os.path.join(os.path.dirname(__file__), "..", "data", "calligraphy.db")

print("=" * 60)
print("李鱓情感校准 — 诊断阶段")
print("=" * 60)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT id, inscription_content, year, title, analysis_note,
           artwork_width_cm, artwork_height_cm, artist
    FROM tubi_analyses WHERE artist = '李鱓'
    AND inscription_content IS NOT NULL AND LENGTH(inscription_content) > 2
    ORDER BY id
""").fetchall()
total = len(rows)
print(f"\n共 {total} 幅李鱓作品\n")

# ── 第一轮分析：逐条跑，收集细节数据 ──
emotion_scores = []
polarities = Counter()
all_special_rules = Counter()
word_contributions = Counter()  # 单词 → 累计贡献分
emotion_details_collection = []

for i, row in enumerate(rows):
    r = classify_inscription_v4(
        text=row["inscription_content"] or "",
        year=row["year"],
        title=row["title"],
        analysis_note=row["analysis_note"],
        width_cm=row["artwork_width_cm"],
        height_cm=row["artwork_height_cm"],
        artist=row["artist"],
    )
    pol = r["sentiment"]["polarity"]
    es = r["sentiment"]["emotion_score"]
    polarities[pol] += 1
    emotion_scores.append(es)
    
    # 收集 special_rules
    for rule in r.get("special_rules", []):
        all_special_rules[rule[:60]] += 1
    
    if (i + 1) % 100 == 0:
        print(f"  已分析 {i+1}/{total}...")

pos_count = polarities.get("positive", 0)
neg_count = polarities.get("negative", 0)
neu_count = polarities.get("neutral", 0)
avg_es = sum(emotion_scores) / len(emotion_scores) if emotion_scores else 0

print(f"\n┌─ 当前情感分布 ─────────────────────────────────┐")
print(f"│ positive: {pos_count:4d} ({pos_count/total*100:5.1f}%)  目标 ≤35%     │")
print(f"│ negative: {neg_count:4d} ({neg_count/total*100:5.1f}%)  目标 ≥20%     │")
print(f"│ neutral:  {neu_count:4d} ({neu_count/total*100:5.1f}%)                │")
print(f"│ 均值:     {avg_es:+.2f}                       目标 < -0.3   │")
print(f"└────────────────────────────────────────────────┘")

# ── 统计分数分布区间 ──
buckets = Counter()
for es in emotion_scores:
    if es >= 3: buckets["强正(≥3)"] += 1
    elif es >= 1: buckets["中正(1~3)"] += 1
    elif es >= 0.1: buckets["微正(0.1~1)"] += 1
    elif es >= -0.1: buckets["中性(-0.1~0.1)"] += 1
    elif es >= -1: buckets["微负(-1~-0.1)"] += 1
    elif es >= -3: buckets["中负(-3~-1)"] += 1
    else: buckets["强负(<-3)"] += 1

print(f"\n情感分数分布:")
for k, v in sorted(buckets.items(), key=lambda x: -list(buckets.keys()).index(x[0])):
    bar = "█" * (v // 5)
    print(f"  {k}: {v:4d} 幅 {bar}")

# ── 特殊规则触发统计 ──
print(f"\n触发最多的特殊规则 (Top 10):")
for rule, count in all_special_rules.most_common(10):
    print(f"  [{count:3d}] {rule}")

# ── 采样 positive 高分作品 ──
high_pos = [(es, row) for es, row in zip(emotion_scores, rows) if es >= 2]
print(f"\n高分正面作品采样 ({len(high_pos)} 幅):")
for es, row in high_pos[:8]:
    text = (row["inscription_content"] or "")[:80]
    print(f"  +{es:.1f}  |  {text}...")

# ── 采样 negative 高分作品 ──
high_neg = [(es, row) for es, row in zip(emotion_scores, rows) if es <= -3]
print(f"\n高分负面作品采样 ({len(high_neg)} 幅):")
for es, row in high_neg[:5]:
    text = (row["inscription_content"] or "")[:80]
    print(f"  {es:.1f}  |  {text}...")

conn.close()

# ── 诊断结论 ──
print(f"\n{'=' * 60}")
print(f"诊断结论:")
gap_pos = max(0, pos_count/total*100 - 35)
gap_mean = max(0, avg_es - (-0.3))
print(f"  positive 超出预期: +{gap_pos:.1f}%")
print(f"  均值超出预期:     +{gap_mean:.2f}")
if gap_pos > 2:
    print(f"  建议: 收紧 positive_gentle 词表或降权（当前+0.3/词）")
    print(f"  怀疑: 清/静/幽/淡/雅/逸/闲/远 在李鱓语境下多为风格描述，非真积极")
if avg_es > 0:
    print(f"  建议: 提高负面词权重或增加新负面词")
    print(f"  方向: 李鱓题跋中的'写''画''作'等常带有无奈/自嘲色彩")
