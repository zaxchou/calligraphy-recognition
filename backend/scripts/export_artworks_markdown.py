#!/usr/bin/env python3
"""
export_artworks_markdown.py
将数据库中的作品导出为 Obsidian 可用的 Markdown 文件。

输出目录结构：
  exports/
    {artist}/
      {year}_{title}_{id}.md    # 每幅作品一个文件
    images/
      {artist}/
        originals/   -> 原图（复制）
        annotated/   -> 标注图（复制）

用法：
  python scripts/export_artworks_markdown.py              # 导出全部
  python scripts/export_artworks_markdown.py --artist 李鱓  # 仅导出某位画家
  python scripts/export_artworks_markdown.py --dry-run    # 仅预览，不写入
"""

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime

# ── 路径配置 ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "data", "calligraphy.db")
EXPORT_BASE = os.path.join(BACKEND_DIR, "..", "exports")
IMAGES_BASE = os.path.join(EXPORT_BASE, "images")

# 数据库中的图片根目录
UPLOADS_DIR = os.path.join(BACKEND_DIR, "data", "uploads")
ANNOTATED_DIR = os.path.join(BACKEND_DIR, "data", "annotated")


def safe_filename(name: str) -> str:
    """将字符串转为安全的文件名"""
    if not name:
        name = "untitled"
    invalid = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for c in invalid:
        name = name.replace(c, '_')
    return name.strip()[:80]   # 截断防止超长


def copy_image(src: str, dst: str) -> bool:
    """复制图片文件，返回是否成功"""
    if not src or not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def parse_content_analysis(ca_json: str) -> dict:
    """解析 content_analysis JSON 字段"""
    if not ca_json:
        return {}
    try:
        return json.loads(ca_json)
    except Exception:
        return {}


def build_markdown(row: dict, images_relpath: dict) -> str:
    """
    为一幅作品生成 Markdown 文本。
    images_relpath: { 'original': 相对路径, 'annotated': 相对路径或 None }
    """
    lines = []

    title = row.get("title") or "（无标题）"
    artist = row.get("artist") or "未知"
    year = row.get("year")
    period_phase = row.get("period_phase") or ""
    width = row.get("artwork_width_cm")
    height = row.get("artwork_height_cm")
    inscription = (row.get("inscription_content") or "").strip()
    inscription_modern = (row.get("inscription_modern") or "").strip()
    seal_content = (row.get("seal_content") or "").strip()
    analysis_note = (row.get("analysis_note") or "").strip()
    content_analysis_raw = row.get("content_analysis") or ""
    tags = (row.get("tags") or "").strip()
    material_tags = (row.get("material_tags") or "").strip()
    album_name = (row.get("album_name") or "").strip()
    album_index = row.get("album_index")
    created_at = row.get("created_at") or ""

    # ── 标题（Obsidian 大标题）────
    lines.append(f"# {title}")
    lines.append("")

    # ── 基本信息表格 ──────────────
    lines.append("## 基本信息")
    lines.append("")
    lines.append("| 字段 | 内容 |")
    lines.append("|------|------|")

    # 作者
    lines.append(f"| 作者 | {artist} |")

    # 创作年份
    if year:
        year_str = str(year)
        if period_phase:
            year_str += f"（{period_phase}）"
        lines.append(f"| 创作年份 | {year_str} |")
    elif period_phase:
        lines.append(f"| 时期 | {period_phase} |")

    # 尺寸
    if width and height:
        lines.append(f"| 尺寸 | {width} × {height} cm |")
    elif width:
        lines.append(f"| 宽度 | {width} cm |")
    elif height:
        lines.append(f"| 高度 | {height} cm |")

    # 册页信息
    if album_name:
        album_str = album_name
        if album_index:
            album_str += f"（第{album_index}开）"
        lines.append(f"| 所属册页 | {album_str} |")

    # 数据库 ID
    lines.append(f"| 数据库 ID | {row.get('id')} |")
    lines.append(f"| 图像 ID | `{row.get('image_id') or 'N/A'}` |")

    if created_at:
        lines.append(f"| 录入时间 | {created_at[:10]} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 图片展示 ──────────────────
    orig_rel = images_relpath.get("original")
    ann_rel = images_relpath.get("annotated")

    if ann_rel or orig_rel:
        lines.append("## 作品图像")
        lines.append("")

        if ann_rel:
            lines.append(f"**标注图**（AI 分析标注）")
            lines.append("")
            lines.append(f"![[{ann_rel}]]")
            lines.append("")

        if orig_rel:
            lines.append(f"**原作图**")
            lines.append("")
            lines.append(f"![[{orig_rel}]]")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── 题跋原文 ──────────────────
    if inscription:
        lines.append("## 题跋原文")
        lines.append("")
        lines.append(f"> {inscription.replace(chr(10), '  \n> ')}")
        lines.append("")

        if inscription_modern and inscription_modern != inscription:
            lines.append("*Modern translation:*")
            lines.append("")
            lines.append(f"> {inscription_modern.replace(chr(10), '  \n> ')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── 印章 ──────────────────────
    if seal_content:
        lines.append("## 印章")
        lines.append("")
        lines.append(seal_content)
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── AI 内容分析 ──────────────
    ca = parse_content_analysis(content_analysis_raw)
    if ca:
        lines.append("## AI 内容分析")
        lines.append("")

        # 主题
        themes = ca.get("themes", [])
        if themes:
            lines.append("**主题判定：**")
            for t in themes:
                name = t.get("name", "")
                conf = t.get("confidence", 0)
                is_primary = t.get("is_primary", False)
                primary_mark = " ★（第一主题）" if is_primary else ""
                lines.append(f"- {name}（置信度 {conf:.0%}）{primary_mark}")
            lines.append("")

        # 情感
        sentiment = ca.get("sentiment", {})
        if sentiment:
            polarity = sentiment.get("polarity", "")
            score = sentiment.get("emotion_score", 0)
            polarity_cn = {"positive": "积极", "negative": "消极", "neutral": "中性"}.get(polarity, polarity)
            lines.append(f"**情感倾向：** {polarity_cn}（score: {score:+.2f}）")
            lines.append("")

        # 特征词
        feature_words = ca.get("feature_words", {})
        if feature_words:
            lines.append("**特征词：**")
            for dim, words in feature_words.items():
                if words:
                    lines.append(f"- {dim}：{', '.join(words)}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── 标签 ──────────────────────
    if tags:
        try:
            tags_list = json.loads(tags) if tags.startswith("[") else [t.strip() for t in tags.split(",")]
        except Exception:
            tags_list = [t.strip() for t in tags.split(",")]
        if tags_list:
            lines.append("## 自动标签")
            lines.append("")
            lines.append(" ".join(f"`{t}`" for t in tags_list if t))
            lines.append("")

    if material_tags:
        lines.append("**画材标签：** " + material_tags)
        lines.append("")

    if tags or material_tags:
        lines.append("---")
        lines.append("")

    # ── AI 讲评 ─────────────────
    if analysis_note:
        lines.append("## AI 讲评")
        lines.append("")
        lines.append(analysis_note)
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── 元数据（供程序解析）───────
    lines.append("<!-- metadata")
    meta = {
        "db_id": row.get("id"),
        "image_id": row.get("image_id"),
        "artist": artist,
        "title": title,
        "year": year,
        "period_phase": period_phase,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }
    lines.append(json.dumps(meta, ensure_ascii=False, indent=2))
    lines.append("--!>")

    return "\n".join(lines)


def export_artworks(artist_filter: str = None, dry_run: bool = False):
    """主导出函数"""

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 构建查询
    if artist_filter:
        cur.execute("""
            SELECT * FROM tubi_analyses
            WHERE artist = ?
            ORDER BY artist, year, id
        """, (artist_filter,))
    else:
        cur.execute("""
            SELECT * FROM tubi_analyses
            ORDER BY artist, year, id
        """)

    rows = cur.fetchall()
    total = len(rows)
    print(f"[export] 共 {total} 幅作品待导出" + (f"（画家：{artist_filter}）" if artist_filter else ""))
    conn.close()

    if dry_run:
        print("[export] DRY RUN — 仅预览，不写入文件")
        for i, row in enumerate(rows[:5]):
            r = dict(row)
            print(f"  [{i+1}] {r.get('artist')} | {r.get('title')} | {r.get('year')}")
        if total > 5:
            print(f"  ... 共 {total} 幅（仅显示前 5）")
        return

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, row in enumerate(rows):
        r = dict(row)
        artist = r.get("artist") or "未知"
        title = r.get("title") or "untitled"
        db_id = r.get("id")
        image_id = r.get("image_id") or ""

        # 原图路径：优先用 filepath 字段（存的是 data/uploads/xxx.jpg），其次用 filename
        # filepath 是系统内部路径，对应 uploads/ 下的实际文件
        filepath_raw = r.get("filepath") or ""
        original_src = ""
        if filepath_raw:
            # filepath 如 "data/uploads/e8ab4386-xxx.jpg"，提取文件名去 uploads/ 找
            fname = os.path.basename(filepath_raw.replace("\\", "/"))
            candidate = os.path.join(UPLOADS_DIR, fname)
            if os.path.exists(candidate):
                original_src = candidate
            else:
                # filepath 本身可能是绝对路径
                if os.path.exists(filepath_raw):
                    original_src = filepath_raw
        if not original_src:
            filename = r.get("filename") or ""
            if filename:
                candidate = os.path.join(UPLOADS_DIR, filename)
                if os.path.exists(candidate):
                    original_src = candidate

        # 标注图路径（优先用 DB 字段，其次按命名规则推断）
        annotated_rel_in_db = r.get("annotated_image_path") or ""
        if annotated_rel_in_db and annotated_rel_in_db.startswith("data/annotated/"):
            annotated_src = os.path.join(BACKEND_DIR, annotated_rel_in_db)
        elif image_id:
            inferred = os.path.join(ANNOTATED_DIR, f"annotated_{image_id}.jpg")
            annotated_src = inferred if os.path.exists(inferred) else ""
        else:
            annotated_src = ""

        # 目标目录
        artist_dir = os.path.join(EXPORT_BASE, safe_filename(artist))
        os.makedirs(artist_dir, exist_ok=True)

        # 复制图片
        img_dir_artist = os.path.join(IMAGES_BASE, safe_filename(artist))
        images_rel = {}

        if original_src and os.path.exists(original_src):
            orig_filename = os.path.basename(original_src)
            orig_dst = os.path.join(img_dir_artist, "originals", orig_filename)
            if copy_image(original_src, orig_dst):
                # Obsidian 相对路径（从 .md 文件出发）
                rel = os.path.relpath(orig_dst, artist_dir).replace("\\", "/")
                images_rel["original"] = rel
        else:
            if not original_src:
                print(f"  [warn] id={db_id}: 无 filename，跳过原图")
            elif not os.path.exists(original_src):
                print(f"  [warn] id={db_id}: 原图不存在 {original_src}")

        if annotated_src and os.path.exists(annotated_src):
            ann_filename = os.path.basename(annotated_src)
            ann_dst = os.path.join(img_dir_artist, "annotated", ann_filename)
            if copy_image(annotated_src, ann_dst):
                rel = os.path.relpath(ann_dst, artist_dir).replace("\\", "/")
                images_rel["annotated"] = rel
        elif annotated_src:
            print(f"  [warn] id={db_id}: 标注图不存在 {annotated_src}")

        # 生成 Markdown
        md_content = build_markdown(r, images_rel)

        # 写入文件
        year_str = str(r.get("year")) if r.get("year") else "unknown"
        md_filename = f"{year_str}_{safe_filename(title)}_{db_id}.md"
        md_path = os.path.join(artist_dir, md_filename)

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            success_count += 1
            if (i + 1) % 50 == 0:
                print(f"  ... 已处理 {i+1}/{total}")
        except Exception as e:
            print(f"  [error] 写入失败: id={db_id}, {e}")
            error_count += 1

    print(f"\n[export] 完成！")
    print(f"  成功：{success_count}")
    print(f"  跳过：{skip_count}")
    print(f"  失败：{error_count}")
    print(f"  输出目录：{EXPORT_BASE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导出作品数据为 Obsidian Markdown")
    parser.add_argument("--artist", type=str, default=None, help="仅导出指定画家（如：李鱓）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    args = parser.parse_args()

    export_artworks(artist_filter=args.artist, dry_run=args.dry_run)
