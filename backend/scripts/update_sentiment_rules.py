"""更新 DB 中所有画家的 expected_sentiment 和 rules_version"""
import sqlite3, json

conn = sqlite3.connect("data/calligraphy.db")
conn.row_factory = sqlite3.Row

new_expected = json.dumps({
    "negative_min": 30,
    "positive_max": 45,
    "emotion_mean_max": 0.0
})

for name in ["李鱓", "郑燮", "金农", "黄慎"]:
    row = conn.execute(
        "SELECT id FROM artist_rules WHERE artist_name = ?", (name,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE artist_rules SET expected_sentiment_distribution = ?, rules_version = ?, updated_at = datetime('now') WHERE artist_name = ?",
            (new_expected, "5.5", name)
        )
        print(f"[OK] 更新 {name} → v5.5")

conn.commit()

for name in ["李鱓", "郑燮"]:
    row = conn.execute(
        "SELECT artist_name, rules_version, expected_sentiment_distribution FROM artist_rules WHERE artist_name = ?",
        (name,)
    ).fetchone()
    print(f"  验证 {row['artist_name']}: v{row['rules_version']} sentiment={row['expected_sentiment_distribution']}")

conn.close()
print("DB更新完成")
