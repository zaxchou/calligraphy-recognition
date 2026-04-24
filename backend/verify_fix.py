
import sqlite3
import json

conn = sqlite3.connect('data/calligraphy.db')
cursor = conn.cursor()

cursor.execute('SELECT image_id, title, year, inscription_content, content_analysis FROM tubi_analyses WHERE content_analysis IS NOT NULL')
rows = cursor.fetchall()

print('=== 修复后情感分布统计 ===\n')

theme_counts = {}
sentiment_counts = {}
satire_sentiments = []

for image_id, title, year, inscription_content, content_analysis in rows:
    try:
        ca = json.loads(content_analysis) if isinstance(content_analysis, str) else content_analysis
        if not ca:
            continue
        # 主题
        themes = ca.get('themes', [])
        if themes:
            main_theme = themes[0]['name']
            theme_counts[main_theme] = theme_counts.get(main_theme, 0) + 1
        # 情感
        sentiment = ca.get('sentiment', {}).get('polarity', 'unknown')
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        # 讽喻社会作品情感
        if themes and main_theme == '讽喻社会与民生':
            score = ca.get('sentiment', {}).get('emotion_score')
            satire_sentiments.append({
                'title': title,
                'sentiment': sentiment,
                'score': score
            })
    except Exception as e:
        pass

print(f'主题分布: {theme_counts}')
print(f'情感分布: {sentiment_counts}')
print()

print('=== 讽喻社会作品情感详情 ===\n')
for item in satire_sentiments:
    print(f"【{item['title']}】: {item['sentiment']} (分: {item['score']})")

print(f"\n讽喻社会作品共 {len(satire_sentiments)} 条")
print(f"  - positive: {sum(1 for s in satire_sentiments if s['sentiment'] == 'positive')}")
print(f"  - negative: {sum(1 for s in satire_sentiments if s['sentiment'] == 'negative')}")
print(f"  - neutral: {sum(1 for s in satire_sentiments if s['sentiment'] == 'neutral')}")
