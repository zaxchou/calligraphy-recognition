
import sqlite3
import json

conn = sqlite3.connect('data/calligraphy.db')
cursor = conn.cursor()

# 这是 /content-analysis/stats 接口的查询逻辑
cursor.execute("""
    SELECT period_phase, content_analysis
    FROM tubi_analyses
    WHERE (artist LIKE ? OR artist LIKE ?)
      AND content_analysis IS NOT NULL
""", ("%李鱓%", "%李鱓%"))

theme_counts = {}
sentiment_counts = {}
all_themes = {}

for row in cursor.fetchall():
    period, content_json = row
    period = period or "未分期"

    try:
        analysis = json.loads(content_json)

        # 主题统计 - 这里是统计所有主题，不是只看第一个
        themes = analysis.get("themes", [])
        for theme in themes:
            key = (period, theme.get("name", "未知"))
            theme_counts[key] = theme_counts.get(key, 0) + 1
            if theme.get("name") == "讽喻社会与民生":
                all_themes[theme.get("name")] = all_themes.get(theme.get("name"), 0) + 1

        # 情感统计
        sentiment = analysis.get("sentiment", {})
        polarity = sentiment.get("polarity", "neutral")
        sentiment_counts[polarity] = sentiment_counts.get(polarity, 0) + 1

    except:
        continue

print("=== /content-analysis/stats 接口的统计逻辑 ===\n")
print(f"主题分布（包含所有主题，不只是第一个）: {dict(theme_counts)}")
print(f"情感分布: {sentiment_counts}")
print(f"讽喻社会总出现次数（含第二、第三主题）: {all_themes}")

# 也计算一下只算第一主题的数量
cursor.execute("""
    SELECT content_analysis
    FROM tubi_analyses
    WHERE (artist LIKE ? OR artist LIKE ?)
      AND content_analysis IS NOT NULL
""", ("%李鱓%", "%李鱓%"))

main_theme_counts = {}
for row in cursor.fetchall():
    try:
        analysis = json.loads(row[0])
        themes = analysis.get("themes", [])
        if themes:
            main_theme = themes[0].get("name", "未知")
            main_theme_counts[main_theme] = main_theme_counts.get(main_theme, 0) + 1
    except:
        continue

print(f"\n只算第一主题的主题分布: {main_theme_counts}")
