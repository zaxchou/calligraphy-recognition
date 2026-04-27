"""种子数据：将现有画家规则导入 artist_rules 表"""
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.tibi_analysis_rules import HARDCODED_ARTIST_RULES, RULES_VERSION
from app.core.database import get_db_connection

now = datetime.now().isoformat()

SEED_DATA = {
    "李鱓": {
        "emotion_baseline": -0.7,
        "life_stages": [
            {"name": "早期（入宫学蒋）", "year_start": 1714, "year_end": 1722,
             "weight": 1.0, "mood_offset": 0.3, "description": "师从蒋廷锡，画法工致，抱负满腔"},
            {"name": "中期（出京卖画）", "year_start": 1723, "year_end": 1745,
             "weight": 1.5, "mood_offset": -0.3, "description": "仕途受挫，卖画为生"},
            {"name": "晚期（彻底归隐）", "year_start": 1746, "year_end": 1760,
             "weight": 2.0, "mood_offset": -0.5, "description": "题跋谨慎，生活困顿，衰年变法"},
        ],
        "sentiment_note": "李鱓题跋多含蓄，'借景抒怀'常暗藏压抑愤懑。**表面写景但有愁苦词即判negative**。落款署名（懊道人/复堂）本身不承载正文情感信息，不因此判负。",
        "theme_note": "- 李鱓核心主题是'身世自况'：凡是涉及自身境遇（仕途、卖画、困顿、自嘲）的题跋，都应归为'身世自况'而非'咏物寄兴'或'吉语祥瑞'。'老夫卖画''臣非老画师'等是身世自况的强信号。落款署名（懊道人/复堂）本身不决定主题，需结合正文判断。",
        "theme_exceptions": {"5": {"override_if_contains": ["世味", "辣", "苦"], "override_to": "negative"}},
        "expected_theme_distribution": {"身世自况": [5, 15], "咏物寄兴": [55, 70], "画理自叙": [5, 12], "时事讽喻": [5, 15], "吉语祥瑞": [3, 10], "交游赠答": [8, 18]},
        "expected_sentiment_distribution": {"negative_min": 20, "positive_max": 35, "emotion_mean_max": -0.3},
    },
    "郑燮": {
        "emotion_baseline": -0.3,
        "life_stages": [
            {"name": "早期", "year_start": 1693, "year_end": 1732, "weight": 1.0, "mood_offset": 0.0, "description": "读书应试"},
            {"name": "中期", "year_start": 1733, "year_end": 1745, "weight": 1.3, "mood_offset": -0.2, "description": "宦游山东"},
            {"name": "晚期", "year_start": 1746, "year_end": 1765, "weight": 1.5, "mood_offset": -0.3, "description": "罢官卖画"},
        ],
        "sentiment_note": "郑燮题跋多议论民生，'衙斋卧听萧萧竹，疑是民间疾苦声'为代表。",
        "theme_note": "",
        "theme_exceptions": {},
        "expected_theme_distribution": {"身世自况": [5, 15], "咏物寄兴": [50, 65], "画理自叙": [5, 15], "时事讽喻": [10, 25], "吉语祥瑞": [3, 10], "交游赠答": [10, 20]},
        "expected_sentiment_distribution": {"negative_min": 15, "positive_max": 30, "emotion_mean_max": -0.1},
    },
    "金农": {
        "emotion_baseline": -0.2,
        "life_stages": [],
        "sentiment_note": "",
        "theme_note": "",
        "theme_exceptions": {},
        "expected_theme_distribution": {"身世自况": [5, 15], "咏物寄兴": [55, 70], "画理自叙": [5, 12], "时事讽喻": [5, 15], "吉语祥瑞": [3, 10], "交游赠答": [8, 18]},
        "expected_sentiment_distribution": {"negative_min": 20, "positive_max": 35, "emotion_mean_max": -0.3},
    },
    "黄慎": {
        "emotion_baseline": -0.1,
        "life_stages": [],
        "sentiment_note": "",
        "theme_note": "",
        "theme_exceptions": {},
        "expected_theme_distribution": {"身世自况": [5, 15], "咏物寄兴": [55, 70], "画理自叙": [5, 12], "时事讽喻": [5, 15], "吉语祥瑞": [3, 10], "交游赠答": [8, 18]},
        "expected_sentiment_distribution": {"negative_min": 20, "positive_max": 35, "emotion_mean_max": -0.3},
    },
}


def seed():
    conn = get_db_connection()
    try:
        for name, rules in SEED_DATA.items():
            existing = conn.execute(
                "SELECT id FROM artist_rules WHERE artist_name = ?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE artist_rules SET
                       emotion_baseline=?, life_stages=?, sentiment_note=?, theme_note=?,
                       theme_exceptions=?, expected_theme_distribution=?,
                       expected_sentiment_distribution=?, rules_version=?, updated_at=?
                       WHERE artist_name=?""",
                    (
                        rules["emotion_baseline"],
                        json.dumps(rules["life_stages"], ensure_ascii=False),
                        rules["sentiment_note"],
                        rules["theme_note"],
                        json.dumps(rules["theme_exceptions"], ensure_ascii=False),
                        json.dumps(rules["expected_theme_distribution"], ensure_ascii=False),
                        json.dumps(rules["expected_sentiment_distribution"], ensure_ascii=False),
                        RULES_VERSION, now, name
                    )
                )
                print(f"[OK] 更新: {name}")
            else:
                conn.execute(
                    """INSERT INTO artist_rules (
                        artist_name, emotion_baseline, life_stages, sentiment_note,
                        theme_note, theme_exceptions, expected_theme_distribution,
                        expected_sentiment_distribution, rules_version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name, rules["emotion_baseline"],
                        json.dumps(rules["life_stages"], ensure_ascii=False),
                        rules["sentiment_note"], rules["theme_note"],
                        json.dumps(rules["theme_exceptions"], ensure_ascii=False),
                        json.dumps(rules["expected_theme_distribution"], ensure_ascii=False),
                        json.dumps(rules["expected_sentiment_distribution"], ensure_ascii=False),
                        RULES_VERSION, now, now
                    )
                )
                print(f"[OK] 插入: {name}")
        conn.commit()
        print("\n种子数据导入完成")
    except Exception as e:
        conn.rollback()
        print(f"[ERR] {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
