"""
从 AI 分析描述中提取画材关键词
────────────────────────────────────────
从已有的 analysis_note 文字中提取画材/题材关键词
不需要调用 AI 识图，直接文本匹配

用法:
  python -m scripts.extract_painting_materials              # 批量处理所有无画材数据的作品
  python -m scripts.extract_painting_materials --limit 10   # 只处理前 10 幅
  python -m scripts.extract_painting_materials --id 56      # 只处理指定 ID
"""

import json
import os
import sys
import re
import argparse
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.inscription_content_analyzer import match_painting_materials
from app.services.tibi_analysis_rules import MATERIAL_KEYWORDS, PAINTING_MATERIAL_RULES

# 从两个来源提取所有关键词用于文本匹配
ALL_MATERIAL_KEYWORDS = set()
for keyword, _ in MATERIAL_KEYWORDS:
    ALL_MATERIAL_KEYWORDS.add(keyword)
for rule in PAINTING_MATERIAL_RULES:
    ALL_MATERIAL_KEYWORDS.update(rule['keywords'])


def extract_keywords_from_text(text: str) -> List[str]:
    """从 AI 分析描述中提取画材关键词"""
    if not text:
        return []

    found = []
    for keyword in ALL_MATERIAL_KEYWORDS:
        if keyword in text:
            found.append(keyword)

    # 去重和排序
    return sorted(set(found))


def get_artworks_without_painting(limit: int = None) -> List[Dict]:
    """获取没有画材数据的作品"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calligraphy.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT id, image_id, title, artist, analysis_note, content_analysis
        FROM tubi_analyses
        WHERE content_analysis IS NOT NULL
        ORDER BY id
    """)

    results = []
    for row in cur.fetchall():
        try:
            ca = json.loads(row["content_analysis"])
            v4 = ca.get("v4_signals", {})
            painting = v4.get("painting", [])
            if not painting:
                results.append({
                    "id": row["id"],
                    "image_id": row["image_id"],
                    "title": row["title"],
                    "artist": row["artist"],
                    "analysis_note": row["analysis_note"] or "",
                    "content_analysis": ca,
                })
        except:
            pass

    conn.close()

    if limit:
        results = results[:limit]

    return results


def update_painting_materials(record_id: int, keywords: List[str], content_analysis: Dict):
    """更新数据库中的画材数据"""
    # 用关键词构造虚拟标题来匹配画材规则
    virtual_title = " ".join(keywords)
    matches = match_painting_materials(virtual_title, None, virtual_title)

    if not matches:
        return False

    # 更新 v4_signals
    if "v4_signals" not in content_analysis:
        content_analysis["v4_signals"] = {}
    content_analysis["v4_signals"]["painting"] = matches

    # 保存到数据库
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calligraphy.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
               (json.dumps(content_analysis, ensure_ascii=False), record_id))
    conn.commit()
    conn.close()

    return True


def batch_extract(limit: int = None, record_id: int = None):
    """批量从 analysis_note 提取画材关键词"""
    # 获取待处理作品
    if record_id:
        artworks = get_artworks_without_painting()
        artworks = [a for a in artworks if a["id"] == record_id]
        if not artworks:
            print(f"ID {record_id} 未找到或已有画材数据")
            return
    else:
        artworks = get_artworks_without_painting(limit)

    print(f"待处理: {len(artworks)} 幅作品")

    updated = 0
    failed = 0

    for i, artwork in enumerate(artworks):
        print(f"[{i+1}/{len(artworks)}] {artwork['title']}...", end="", flush=True)

        # 从 analysis_note 提取关键词
        keywords = extract_keywords_from_text(artwork["analysis_note"])

        if not keywords:
            print(f" ✗ 未提取到画材关键词")
            failed += 1
            continue

        # 更新数据库
        success = update_painting_materials(artwork["id"], keywords, artwork["content_analysis"])
        if success:
            print(f" ✓ {keywords}")
            updated += 1
        else:
            print(f" ✗ 关键词无法匹配画材规则: {keywords}")
            failed += 1

    print(f"\n完成:")
    print(f"  处理: {len(artworks)} 幅")
    print(f"  成功: {updated}")
    print(f"  失败: {failed}")


def main():
    parser = argparse.ArgumentParser(description="从 AI 分析描述中提取画材关键词")
    parser.add_argument("--limit", type=int, help="只处理前 N 幅")
    parser.add_argument("--id", type=int, help="只处理指定 ID")

    args = parser.parse_args()
    batch_extract(limit=args.limit, record_id=args.id)


if __name__ == "__main__":
    main()
