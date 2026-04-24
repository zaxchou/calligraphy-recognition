import sqlite3
import json

conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

# Get all records with content_analysis for 李鱓
cur.execute("""
    SELECT id, title, year, content_analysis
    FROM tubi_analyses
    WHERE (artist LIKE ? OR artist LIKE ?)
      AND content_analysis IS NOT NULL
""", ('%李鱓%', '%李鱓%'))

records = []
for row in cur.fetchall():
    record_id, title, year, content_json = row
    try:
        analysis = json.loads(content_json)
        records.append({
            'id': record_id,
            'title': title,
            'year': year,
            'analysis': analysis
        })
    except:
        print(f"Failed to parse record {record_id}")

print(f"Total records: {len(records)}\n")

# Analyze dual-channel sentiment
agreement_count = 0
disagreement_count = 0
positive_count = 0
negative_count = 0
neutral_count = 0
llm_positive = 0
llm_negative = 0
llm_neutral = 0

disagreement_cases = []

for r in records:
    analysis = r['analysis']
    sentiment = analysis.get('sentiment', {})
    
    # Rule-based channel
    rule_polarity = sentiment.get('polarity', 'neutral')
    # LLM channel
    llm_sentiment = sentiment.get('llm_sentiment', {})
    llm_polarity = llm_sentiment.get('polarity', 'neutral') if llm_sentiment else 'unknown'
    
    if rule_polarity == llm_polarity:
        agreement_count += 1
    else:
        disagreement_count += 1
        disagreement_cases.append({
            'id': r['id'],
            'title': r['title'],
            'year': r['year'],
            'rule': rule_polarity,
            'llm': llm_polarity
        })
    
    # LLM distribution
    if llm_polarity == 'positive':
        llm_positive += 1
    elif llm_polarity == 'negative':
        llm_negative += 1
    elif llm_polarity == 'neutral':
        llm_neutral += 1
    
    # Rule-based distribution
    if rule_polarity == 'positive':
        positive_count += 1
    elif rule_polarity == 'negative':
        negative_count += 1
    elif rule_polarity == 'neutral':
        neutral_count += 1

print("=" * 60)
print("双通道情感分析统计")
print("=" * 60)
print(f"总记录数: {len(records)}")
print(f"\n一致性分布:")
print(f"  两通道一致: {agreement_count} ({agreement_count/len(records)*100:.1f}%)")
print(f"  两通道不一致: {disagreement_count} ({disagreement_count/len(records)*100:.1f}%)")
print(f"\nLLM通道情感分布:")
print(f"  positive: {llm_positive} ({llm_positive/len(records)*100:.1f}%)")
print(f"  negative: {llm_negative} ({llm_negative/len(records)*100:.1f}%)")
print(f"  neutral:  {llm_neutral} ({llm_neutral/len(records)*100:.1f}%)")
print(f"\n规则通道情感分布:")
print(f"  positive: {positive_count} ({positive_count/len(records)*100:.1f}%)")
print(f"  negative: {negative_count} ({negative_count/len(records)*100:.1f}%)")
print(f"  neutral:  {neutral_count} ({neutral_count/len(records)*100:.1f}%)")

print(f"\n" + "=" * 60)
print(f"不一致案例 (共{len(disagreement_cases)}条):")
print("=" * 60)
for i, case in enumerate(disagreement_cases[:5], 1):
    print(f"{i}. ID={case['id']}, {case['title']} ({case['year']})")
    print(f"   规则={case['rule']}, LLM={case['llm']}")

conn.close()