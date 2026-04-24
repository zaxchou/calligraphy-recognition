"""
批量导入新图片到题跋分析系统
从指定目录读取图片，复制到 uploads 目录，生成缩略图，创建数据库记录

用法：
  # 先 dry-run 看看会导入哪些
  python _import_new_images.py --dry-run

  # 确认后正式导入
  python _import_new_images.py

  # 指定不同目录
  python _import_new_images.py --source "E:\李鱓全集\修改版\已校对"
"""
import sys
import os
import uuid
import shutil
import sqlite3
import argparse
import time
from PIL import Image, ImageOps

# ─── 配置 ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
THUMBNAIL_DIR = os.path.join(DATA_DIR, "thumbnails")
DB_PATH = os.path.join(DATA_DIR, "calligraphy.db")
DEFAULT_SOURCE = r"E:\李鱓全集\修改版\已校对"

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def normalize_path(path: str) -> str:
    """统一使用正斜杠存储路径"""
    return path.replace('\\', '/')


def parse_filename(filename: str):
    """
    从文件名解析画作信息
    格式1: 清_李鱓_画名_年份.jpg -> artist=李鱓, title=画名, year=年份
    格式2: 清_李鱓_画名.jpg -> artist=李鱓, title=画名, year=None
    格式3: 李鱓_画名_序号.jpg -> artist=李鱓, title=画名, year=None
    其他: title=文件名（去扩展名）, artist=李鱓, year=None
    """
    name = os.path.splitext(filename)[0]
    parts = name.split('_')

    artist = '李鱓'  # 默认画家
    title = name
    year = None

    if len(parts) >= 4 and parts[0] == '清':
        # 清_李鱓_画名_年份 或 清_李鱓_画名_年代不详
        artist = parts[1]
        title = parts[2]
        # 尝试解析年份（可能带后缀如 1730-1750 或 1(1)）
        year_str = parts[3]
        if year_str == '年代不详':
            year = None
        else:
            try:
                year = int(year_str)
            except ValueError:
                # 尝试取前4位数字
                digits = ''
                for c in year_str:
                    if c.isdigit():
                        digits += c
                        if len(digits) == 4:
                            break
                if len(digits) == 4:
                    year = int(digits)

    elif len(parts) == 3 and parts[0] == '清':
        # 清_李鱓_画名
        artist = parts[1]
        title = parts[2]

    elif len(parts) == 3 and parts[0] in ['李鱓', '郑燮']:
        # 李鱓_画名_序号
        artist = parts[0]
        title = parts[1]

    elif len(parts) == 2 and parts[0] in ['李鱓', '郑燮']:
        # 李鱓_画名
        artist = parts[0]
        title = parts[1]

    return artist, title, year


def get_existing_filenames(db_path: str) -> set:
    """获取数据库中已有的原始文件名"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT filename FROM tubi_analyses")
    existing = set(row[0] for row in cur.fetchall())
    conn.close()
    return existing


def generate_thumbnail(src_path: str, thumb_path: str, size=(300, 300)) -> bool:
    """生成缩略图"""
    try:
        with Image.open(src_path) as img:
            img = ImageOps.exif_transpose(img)
            thumb = img
            if thumb.mode != "RGB":
                thumb = thumb.convert("RGB")
            thumb.thumbnail(size, Image.Resampling.LANCZOS)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            thumb.save(thumb_path, "JPEG", quality=85, optimize=False)
            return os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0
    except Exception as e:
        print(f"    缩略图生成失败: {e}")
        return False


def get_image_size(path: str):
    """获取图片尺寸"""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def main():
    parser = argparse.ArgumentParser(description='批量导入图片到题跋分析系统')
    parser.add_argument('--source', default=DEFAULT_SOURCE, help='源图片目录')
    parser.add_argument('--dry-run', action='store_true', help='只预览不实际导入')
    parser.add_argument('--artist', default=None, help='覆盖画家名（默认从文件名解析）')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认直接导入')
    args = parser.parse_args()

    source_dir = args.source
    if not os.path.isdir(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        sys.exit(1)

    # 获取已有文件名
    existing = get_existing_filenames(DB_PATH)
    print(f"数据库已有 {len(existing)} 条记录")

    # 扫描源目录
    files = []
    for f in sorted(os.listdir(source_dir)):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTS:
            files.append(f)

    print(f"源目录共 {len(files)} 个图片文件")

    # 过滤已存在的
    new_files = []
    for f in files:
        if f in existing:
            print(f"  跳过(已存在): {f}")
        else:
            new_files.append(f)

    print(f"\n需要导入 {len(new_files)} 张新图片")

    if not new_files:
        print("没有新图片需要导入")
        return

    # 预览
    print("\n── 导入预览 ──")
    for f in new_files:
        artist, title, year = parse_filename(f)
        year_str = str(year) if year else 'N/A'
        print(f"  {f} -> 画家={artist} 画作={title} 年份={year_str}")

    if args.dry_run:
        print("\n[dry-run] 以上为预览，未实际导入。去掉 --dry-run 参数执行导入。")
        return

    # 确认
    if not args.yes:
        print(f"\n即将导入 {len(new_files)} 张图片，是否继续？(y/N) ", end='')
        confirm = input().strip().lower()
        if confirm != 'y':
            print("已取消")
            return

    # 确保目录存在
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)

    # 开始导入
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    ok = fail = 0
    t0 = time.time()
    for i, filename in enumerate(new_files):
        src_path = os.path.join(source_dir, filename)
        try:
            # 1. 生成 UUID 文件名
            file_id = str(uuid.uuid4())
            ext = os.path.splitext(filename)[1]
            new_filename = f"{file_id}{ext}"
            dest_path = os.path.join(UPLOAD_DIR, new_filename)

            # 2. 复制文件
            shutil.copy2(src_path, dest_path)

            # 3. 获取图片尺寸
            width, height = get_image_size(dest_path)

            # 4. 生成缩略图
            thumb_filename = f"{file_id}_thumb.jpg"
            thumb_path = os.path.join(THUMBNAIL_DIR, thumb_filename)
            thumb_ok = generate_thumbnail(dest_path, thumb_path)

            # 5. 解析元数据
            artist, title, year = parse_filename(filename)
            if args.artist:
                artist = args.artist

            # 6. 写入数据库
            cur.execute("""
                INSERT INTO tubi_analyses
                    (image_id, filename, filepath, thumbnail_path,
                     title, artist, year, image_width, image_height, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded')
            """, (
                file_id,
                filename,  # 保留原始文件名用于去重
                normalize_path(dest_path),
                normalize_path(thumb_path) if thumb_ok else None,
                title,
                artist,
                year,
                width,
                height,
            ))
            conn.commit()

            year_str = str(year) if year else 'N/A'
            print(f"  [{i+1}/{len(new_files)}] OK: {filename} -> {title} ({artist}, {year_str}) {width}x{height}")
            ok += 1

        except Exception as e:
            print(f"  [{i+1}/{len(new_files)}] FAIL: {filename} -> {e}")
            fail += 1

    conn.close()
    elapsed = time.time() - t0
    print(f"\n导入完成: 成功={ok} 失败={fail} 耗时={elapsed:.1f}s")
    print(f"\n下一步：")
    print(f"  1. 批量AI分析: python batch_process_tubi.py")
    print(f"  2. 内容分析: curl -X POST 'http://localhost:8001/api/v1/content-analysis/batch?force_reanalyze=true'")


if __name__ == '__main__':
    main()
