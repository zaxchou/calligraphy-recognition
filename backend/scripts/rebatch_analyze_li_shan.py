# -*- coding: utf-8 -*-
"""
李鱓作品批量重跑脚本（v5 重构版）
- 用新的意图导向6分类重跑所有李鱓作品
- 输出新旧主题/情感分布对比报告
- 支持迭代校准：自动检测偏差并生成调整建议

运行: cd backend && python scripts/rebatch_analyze_li_shan.py
"""
import sqlite3
import json
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.inscription_content_analyzer import (
    classify_inscription_v4, THEMES, THEME_NAME_MIGRATION
)
from app.services.auto_tags import compute_tags

DB_PATH = "data/calligraphy.db"
ARTIST = "李鱓"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 获取所有李鱓作品
    cur.execute("""
        SELECT id, inscription_content, year, title, analysis_note,
               artwork_width_cm, artwork_height_cm, artist,
               content_analysis, period_phase
        FROM tubi_analyses
        WHERE artist = ?
        ORDER BY id
    """, (ARTIST,))
    rows = cur.fetchall()
    total = len(rows)
    print(f"\n{'='*70}")
    print(f"李鱓作品批量重跑（v5 意图导向分类）— 共 {total} 幅")
    print(f"{'='*70}")

    # 统计变量
    old_themes = Counter()
    new_themes = Counter()
    old_polarities = Counter()
    new_polarities = Counter()
    old_emotion_scores = []
    new_emotion_scores = []
    theme_changes = Counter()  # (旧主题→新主题) 变化统计
    updated_count = 0
    error_count = 0

    for i, row in enumerate(rows):
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{total}...")

        record_id = row["id"]
        text = row["inscription_content"] or ""
        year = row["year"]
        title = row["title"]
        analysis_note = row["analysis_note"]
        width_cm = row["artwork_width_cm"]
        height_cm = row["artwork_height_cm"]
        artist = row["artist"]

        # 解析旧 content_analysis
        old_ca = None
        if row["content_analysis"]:
            try:
                old_ca = json.loads(row["content_analysis"])
            except Exception:
                pass

        # 记录旧主题/情感
        if old_ca:
            for t in old_ca.get("themes", []):
                old_name = t.get("name", "")
                # 兼容旧名称
                compat_name = THEME_NAME_MIGRATION.get(old_name, old_name)
                old_themes[compat_name] += 1
            old_sent = old_ca.get("sentiment", {})
            old_pol = old_sent.get("polarity", "neutral")
            old_polarities[old_pol] += 1
            old_score = old_sent.get("emotion_score")
            if old_score is not None:
                old_emotion_scores.append(old_score)

        # 用新规则引擎重跑
        try:
            result = classify_inscription_v4(
                text=text,
                year=year,
                title=title,
                analysis_note=analysis_note,
                width_cm=width_cm,
                height_cm=height_cm,
                artist=artist,
            )

            # 记录新主题/情感
            for t in result.get("themes", []):
                new_themes[t["name"]] += 1
            new_sent = result.get("sentiment", {})
            new_pol = new_sent.get("polarity", "neutral")
            new_polarities[new_pol] += 1
            new_score = new_sent.get("emotion_score")
            if new_score is not None:
                new_emotion_scores.append(new_score)

            # 记录主题变化
            old_main = ""
            if old_ca and old_ca.get("themes"):
                old_main = old_ca["themes"][0].get("name", "")
                old_main = THEME_NAME_MIGRATION.get(old_main, old_main)
            new_main = result["themes"][0]["name"] if result.get("themes") else ""
            if old_main and new_main and old_main != new_main:
                theme_changes[(old_main, new_main)] += 1

            # 构建新 content_analysis
            new_ca = dict(old_ca) if old_ca else {}
            new_ca["themes"] = result.get("themes", [])
            new_ca["sentiment"] = new_sent
            new_ca["v5_refactored_at"] = datetime.now().isoformat()

            # 更新数据库
            theme_tags = ",".join(t["name"] for t in result.get("themes", []) if t.get("name"))
            cur.execute("""
                UPDATE tubi_analyses
                SET content_analysis = ?, theme_tags = ?
                WHERE id = ?
            """, (json.dumps(new_ca, ensure_ascii=False), theme_tags, record_id))

            # 重新计算自动标签
            record_for_tags = {
                "title": title,
                "period_phase": row["period_phase"],
                "artwork_height_cm": height_cm,
                "artwork_width_cm": width_cm,
                "content_analysis": json.dumps(new_ca, ensure_ascii=False),
                "material_tags": None,  # 不改 material_tags
            }
            auto_tags = compute_tags(record_for_tags)
            if auto_tags:
                cur.execute("UPDATE tubi_analyses SET tags = ? WHERE id = ?",
                           (json.dumps(auto_tags, ensure_ascii=False), record_id))

            updated_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  错误 id={record_id}: {e}")

    conn.commit()

    # ═══════════════════════════════════════════════════════════════════
    # 输出对比报告
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"重跑完成: {updated_count} 幅更新, {error_count} 幅错误")
    print(f"{'='*70}")

    # 1. 主题分布对比
    print(f"\n【一、主题分布对比（新 vs 旧）】")
    all_theme_names = sorted(set(list(old_themes.keys()) + list(new_themes.keys())))
    print(f"  {'主题':12s} {'旧':>6s} {'旧%':>6s} {'新':>6s} {'新%':>6s} {'变化':>8s}")
    print(f"  {'-'*50}")
    for name in all_theme_names:
        old_cnt = old_themes.get(name, 0)
        new_cnt = new_themes.get(name, 0)
        old_pct = old_cnt / total * 100 if total else 0
        new_pct = new_cnt / total * 100 if total else 0
        diff = new_cnt - old_cnt
        sign = "+" if diff > 0 else ""
        print(f"  {name:12s} {old_cnt:6d} {old_pct:5.1f}% {new_cnt:6d} {new_pct:5.1f}% {sign}{diff:6d}")

    # 2. 情感分布对比
    print(f"\n【二、情感分布对比（新 vs 旧）】")
    for pol in ["positive", "negative", "neutral"]:
        old_cnt = old_polarities.get(pol, 0)
        new_cnt = new_polarities.get(pol, 0)
        old_pct = old_cnt / total * 100 if total else 0
        new_pct = new_cnt / total * 100 if total else 0
        diff = new_cnt - old_cnt
        sign = "+" if diff > 0 else ""
        print(f"  {pol:12s}: 旧 {old_cnt:3d}({old_pct:5.1f}%) → 新 {new_cnt:3d}({new_pct:5.1f}%) {sign}{diff}")

    # 3. 情感分数对比
    print(f"\n【三、情感分数对比】")
    if new_emotion_scores:
        new_avg = sum(new_emotion_scores) / len(new_emotion_scores)
        old_avg_str = f"{sum(old_emotion_scores)/len(old_emotion_scores):+.2f}" if old_emotion_scores else "N/A"
        print(f"  新均值: {new_avg:+.2f} (旧: {old_avg_str})")
        print(f"  新范围: {min(new_emotion_scores):+.2f} ~ {max(new_emotion_scores):+.2f}")

    # 4. 主题变化热力图（Top 10 变化路径）
    print(f"\n【四、主题变化路径（Top 10）】")
    for (old_t, new_t), cnt in theme_changes.most_common(10):
        print(f"  {old_t:12s} → {new_t:12s}: {cnt:3d} 幅")

    # 5. 偏差检测与调整建议
    print(f"\n【五、偏差检测与调整建议】")

    # 预期分布（基于美术史研究）
    expected = {
        "身世自况": (20, 30),
        "咏物寄兴": (25, 35),
        "画理自叙": (8, 15),
        "时事讽喻": (10, 18),
        "吉语祥瑞": (5, 12),
        "交游赠答": (10, 18),
    }

    for name, (low, high) in expected.items():
        cnt = new_themes.get(name, 0)
        pct = cnt / total * 100 if total else 0
        if pct < low:
            print(f"  [!] {name}: {pct:.1f}% 低于预期下限 {low}% -- 建议增加关键词权重或补充关键词")
        elif pct > high:
            print(f"  [!] {name}: {pct:.1f}% 高于预期上限 {high}% -- 建议收紧定义或降低权重")
        else:
            print(f"  [OK] {name}: {pct:.1f}% 在预期范围内 [{low}%-{high}%]")

    # 情感偏差检测
    neg_pct = new_polarities.get("negative", 0) / total * 100 if total else 0
    pos_pct = new_polarities.get("positive", 0) / total * 100 if total else 0
    if neg_pct < 20:
        print(f"  [!] 消极情感 {neg_pct:.1f}% 低于预期20% -- 李鱓'懊道人'底色应更偏阴")
    if pos_pct > 35:
        print(f"  [!] 积极情感 {pos_pct:.1f}% 高于预期35% -- 可能被花鸟题材误导")
    if new_emotion_scores:
        avg = sum(new_emotion_scores) / len(new_emotion_scores)
        if avg > 0.5:
            print(f"  [!] 情感均值 {avg:+.2f} 偏阳 -- 李鱓整体应偏阴(预期 < -0.3)")
        elif avg < -0.5:
            print(f"  [OK] 情感均值 {avg:+.2f} 符合李鱓偏阴底色")

    conn.close()
    print(f"\n{'='*70}")
    print("重跑完成。请根据偏差检测结果调整规则，然后重新运行。")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
