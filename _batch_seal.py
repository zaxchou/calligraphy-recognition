"""
批量操作：
1. 将李鱓所有印章的来源设为指定出处
2. 为所有缺失缩略图的 seal_images 批量生成缩略图
"""
import os
import sys
import sqlite3

DB = os.path.join(os.path.dirname(__file__), "backend", "data", "calligraphy.db")
SEAL_DIR = os.path.join(os.path.dirname(__file__), "backend", "data", "seals")
SEAL_THUMB_DIR = os.path.join(SEAL_DIR, "thumbs")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# ═══════════════════════════════════════════════════════════
# 1. 批量设置李鱓印章出处
# ═══════════════════════════════════════════════════════════
source_text = "上海博物馆编《中国书画家印鉴款识》（文物出版社，1987.12）"

rows = conn.execute(
    "SELECT id, name, source FROM seals WHERE artist_name LIKE ?",
    ('%李鱓%',)
).fetchall()

print(f"找到 {len(rows)} 个李鱓的印章")
for r in rows:
    conn.execute("UPDATE seals SET source = ? WHERE id = ?", (source_text, r["id"]))
    print(f"  [{r['id']}] {r['name']}: {r['source'] or '(空)'} → {source_text}")

conn.commit()
print("出处更新完成")
print()

# ═══════════════════════════════════════════════════════════
# 2. 批量生成缺失的缩略图
# ═══════════════════════════════════════════════════════════
imgs = conn.execute(
    "SELECT id, seal_id, path, thumbnail_path FROM seal_images"
).fetchall()

from PIL import Image, ImageOps

def make_thumb(src_path, dst_path, max_size=200):
    img = Image.open(src_path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    img.save(dst_path, "JPEG", quality=85, optimize=True)
    return True

generated = 0
skipped = 0
errored = 0

base = os.path.dirname(DB)

for img in imgs:
    thumb_path = img["thumbnail_path"] or ""
    orig_path = img["path"] or ""

    # 已经有缩略图且文件存在 → 跳过
    if thumb_path:
        thumb_abs = os.path.join(base, thumb_path.replace("/static/", ""))
        if os.path.exists(thumb_abs):
            skipped += 1
            continue

    # 没有原图 → 跳过
    if not orig_path:
        skipped += 1
        continue

    # 数据库存的是 /static/seals/xxx，实际文件在 data/seals/xxx（去掉 /static/ 前缀）
    orig_abs = os.path.join(base, orig_path.replace("/static/", ""))
    if not os.path.exists(orig_abs):
        print(f"  [SKIP] seal_images.id={img['id']} seal_id={img['seal_id']} 原图不存在: {orig_path}")
        errored += 1
        continue

    # 生成缩略图
    try:
        thumb_filename = f"thumb_{os.path.basename(orig_path)}"
        if not thumb_filename.lower().endswith(".jpg"):
            thumb_filename = thumb_filename.rsplit(".", 1)[0] + ".jpg"
        dst = os.path.join(SEAL_THUMB_DIR, thumb_filename)
        make_thumb(orig_abs, dst)

        thumb_url = f"/static/seals/thumbs/{thumb_filename}"
        conn.execute(
            "UPDATE seal_images SET thumbnail_path = ? WHERE id = ?",
            (thumb_url, img["id"])
        )
        print(f"  [OK] seal_images.id={img['id']} seal_id={img['seal_id']} → {thumb_url}")
        generated += 1
    except Exception as e:
        print(f"  [ERR] seal_images.id={img['id']} seal_id={img['seal_id']} 缩略图生成失败: {e}")
        errored += 1

conn.commit()
print()
print(f"缩略图处理完成: 生成 {generated}, 跳过 {skipped}, 失败 {errored}")

conn.close()
