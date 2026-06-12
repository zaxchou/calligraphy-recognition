"""更新李鱓 DB 预期分布为混合引擎校准值"""
import sqlite3, json

conn = sqlite3.connect("data/calligraphy.db")

new_theme = json.dumps({
    "身世自况": (15, 45), "咏物寄兴": (35, 55), "画理自叙": (3, 10),
    "时事讽喻": (3, 10), "吉语祥瑞": (3, 10), "交游赠答": (3, 10),
})
new_sentiment = json.dumps({
    "negative_min": 40, "positive_max": 40, "emotion_mean_max": -0.3,
})

conn.execute("""
    UPDATE artist_rules SET 
        expected_theme_distribution = ?,
        expected_sentiment_distribution = ?,
        rules_version = '5.6',
        updated_at = datetime('now')
    WHERE artist_name = '李鱓'
""", (new_theme, new_sentiment))

conn.commit()

row = conn.execute(
    "SELECT artist_name, rules_version FROM artist_rules WHERE artist_name = '李鱓'"
).fetchone()
print(f"更新完成: {row[0]} v{row[1]}")

# 验证: 取回对比
r = conn.execute(
    "SELECT expected_theme_distribution, expected_sentiment_distribution FROM artist_rules WHERE artist_name = '李鱓'"
).fetchone()
theme = json.loads(r[0])
sent = json.loads(r[1])
print(f"主题: 身世自况{theme['身世自况']} 咏物寄兴{theme['咏物寄兴']}")
print(f"情感: negative_min={sent['negative_min']} positive_max={sent['positive_max']} emotion_mean_max={sent['emotion_mean_max']}")

conn.close()
