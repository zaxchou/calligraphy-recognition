"""
验证尺寸信号修复效果
- 检查哪些作品尺寸触发了 size_theme_boost
- 对比情感修正: 旧(乘法) vs 新(加法)
- 展示尺寸boost的置信度折扣效果
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
os.chdir(os.path.dirname(__file__))

import sqlite3
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "calligraphy.db")

from app.services.inscription_content_analyzer import (
    classify_inscription_v4,
    get_size_category,
    _extract_material_category_from_title,
    SIZE_THEME_RULES,
    SIZE_PERIOD_MOOD_RULES,
)

def get_records_with_dimensions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, year, inscription_content, analysis_note,
               artwork_width_cm, artwork_height_cm, period_phase
        FROM tubi_analyses
        WHERE (artist LIKE '%李鱓%' OR artist LIKE '%郑燮%')
          AND artwork_height_cm IS NOT NULL
          AND inscription_content IS NOT NULL
        ORDER BY artwork_height_cm DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def main():
    records = get_records_with_dimensions()
    print(f"=== 尺寸信号验证报告 ===")
    print(f"有尺寸记录总数: {len(records)}\n")

    size_category_counts = {"小幅": 0, "中幅": 0, "大幅": 0, "未知": 0}
    total_size_boost_fired = 0
    sentiment_comparison_examples = []
    boost_examples = []

    for r in records:
        rid, title, year, text, analysis_note, w, h, period = r
        cat = get_size_category(w, h)
        size_category_counts[cat] += 1

        # 运行 v4 分类器（带尺寸）
        result = classify_inscription_v4(
            text or "", year=year, title=title,
            analysis_note=analysis_note,
            width_cm=w, height_cm=h
        )

        size_sig = result.get("signals", {}).get("size", {})
        theme_boost = size_sig.get("theme_boost", {})
        sentiment_modifier = size_sig.get("sentiment_modifier", 1.0)
        mood_tag = size_sig.get("mood_tag")
        material_cats = size_sig.get("material_categories", [])

        # 旧版情感修正（乘法）
        text_emotion = result["signals"]["text"]["emotion_score"]
        old_emotion = text_emotion * sentiment_modifier if sentiment_modifier != 1.0 else text_emotion
        new_emotion = text_emotion + sentiment_modifier if sentiment_modifier != 1.0 else text_emotion

        if theme_boost:
            total_size_boost_fired += 1
            boost_examples.append({
                "id": rid,
                "title": title[:20],
                "cat": cat,
                "h": h,
                "period": period,
                "materials": material_cats,
                "boost": theme_boost,
                "mood_tag": mood_tag,
                "top_themes": [(t["name"], t["confidence"], t["score"]) for t in result["themes"][:2]],
            })

        if sentiment_modifier != 1.0 and abs(old_emotion - new_emotion) > 0.1:
            sentiment_comparison_examples.append({
                "id": rid,
                "title": title[:20] if title else "",
                "cat": cat,
                "text_emotion": text_emotion,
                "modifier": sentiment_modifier,
                "old_emotion": round(old_emotion, 3),
                "new_emotion": round(new_emotion, 3),
            })

    # ── 输出1: 尺寸分布 ──
    print("【1】尺寸分布")
    total = sum(size_category_counts.values())
    for cat, cnt in size_category_counts.items():
        print(f"  {cat}: {cnt}条 ({cnt/total*100:.1f}%)")
    print()

    # ── 输出2: 触发尺寸boost的作品 ──
    print(f"【2】触发尺寸boost的作品: {total_size_boost_fired}条")
    if boost_examples:
        print(f"{'ID':>4} {'尺寸':>4} {'高度':>6} {'分期':>6} {'画材':>12} {'Boost':>16} {'心境':>8} {'第1主题(置信,得分)':>25}")
        print("-" * 110)
        for ex in boost_examples:
            mats = ",".join(ex["materials"]) if ex["materials"] else "无"
            boost_str = str(ex["boost"])
            themes_str = f"{ex['top_themes'][0][0]}({ex['top_themes'][0][1]},{ex['top_themes'][0][2]})" if ex["top_themes"] else ""
            print(f"{ex['id']:>4} {ex['cat']:>4} {ex['h']:>6.1f} {str(ex['period'] or ''):>6} {mats[:12]:>12} {boost_str:>16} {str(ex['mood_tag'] or ''):>8} {themes_str:>25}")
    print()

    # ── 输出3: 情感修正对比（旧乘法 vs 新加法） ──
    print(f"【3】情感修正对比 (modifier={sentiment_modifier}时): 乘法 vs 加法")
    if sentiment_comparison_examples:
        print(f"{'ID':>4} {'尺寸':>4} {'文本情感':>10} {'modifier':>10} {'旧乘法':>10} {'新加法':>10} {'差异':>8}")
        print("-" * 70)
        for ex in sentiment_comparison_examples:
            diff = ex["new_emotion"] - ex["old_emotion"]
            print(f"{ex['id']:>4} {ex['cat']:>4} {ex['text_emotion']:>10.3f} {ex['modifier']:>10.3f} {ex['old_emotion']:>10.3f} {ex['new_emotion']:>10.3f} {diff:>+8.3f}")
    else:
        print("  （本次样本中无需要对比的记录）")
    print()

    # ── 输出4: 置信度折扣示例 ──
    print("【4】尺寸boost置信度折扣示例")
    discount_examples = [ex for ex in boost_examples if ex["top_themes"]]
    if discount_examples[:5]:
        print(f"{'ID':>4} {'尺寸':>4} {'Boost主题':>20} {'得分':>6} {'boost占比':>8} {'原置信':>8} {'折后置信':>8}")
        print("-" * 80)
        for ex in discount_examples[:5]:
            for theme_name, conf, score in ex["top_themes"]:
                boost_val = ex["boost"].get(3) or ex["boost"].get(2) or ex["boost"].get(6) or 0
                if boost_val > 0:
                    boost_ratio = min(boost_val / max(score, 0.01), 1.0)
                    # 模拟折扣
                    if score >= 5:
                        raw_conf = 0.9
                    elif score >= 3:
                        raw_conf = 0.8
                    elif score >= 2:
                        raw_conf = 0.7
                    else:
                        raw_conf = 0.6
                    discounted = raw_conf * (0.5 + 0.5 * (1 - boost_ratio))
                    print(f"{ex['id']:>4} {ex['cat']:>4} {theme_name[:10]:>20} {score:>6.1f} {boost_ratio:>8.1%} {raw_conf:>8.2f} {discounted:>8.2f}")
    else:
        print("  （无有效示例）")
    print()
    print("=== 验证完成 ===")

if __name__ == "__main__":
    main()
