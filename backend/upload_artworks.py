#!/usr/bin/env python3
"""
作品批量上传脚本
读取 CSV 元数据和图片文件，通过 API 上传到作品库。

用法:
  python upload_artworks.py --csv "E:/下载/朱耷/artwork_metadata.csv" \
    --images "E:/下载/朱耷" --library-id 9 \
    --api-base http://127.0.0.1:3000
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests


def parse_args():
    p = argparse.ArgumentParser(description="批量上传作品到作品库")
    p.add_argument("--csv", required=True, help="CSV 元数据文件路径")
    p.add_argument("--images", required=True, help="图片文件目录")
    p.add_argument("--library-id", type=int, required=True, help="作品库 ID")
    p.add_argument("--api-base", default="http://127.0.0.1:3000",
                   help="API 地址 (默认 http://127.0.0.1:3000)")
    p.add_argument("--phone", default="13917029446", help="登录手机号")
    p.add_argument("--password", default="ilovehouhan", help="登录密码")
    p.add_argument("--max", type=int, default=None, help="限制上传数量 (测试用)")
    p.add_argument("--dry-run", action="store_true", help="只打印将要上传的内容，不上传")
    return p.parse_args()


def login(api_base: str, phone: str, password: str) -> str:
    """登录获取 JWT token."""
    resp = requests.post(
        f"{api_base}/api/v1/auth/login-password",
        json={"account": phone, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token")
    if not token:
        raise RuntimeError(f"Login failed: {data}")
    return token


def get_existing_titles(api_base: str, token: str, library_id: int) -> set[str]:
    """获取库中已有作品标题集合（用于去重）."""
    headers = {"Authorization": f"Bearer {token}"}
    all_titles = set()
    page = 1
    while True:
        resp = requests.get(
            f"{api_base}/api/v1/libraries/{library_id}/artworks",
            params={"page": page, "page_size": 100},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            title = (item.get("title") or "").strip()
            if title:
                all_titles.add(title)
        page += 1
    return all_titles


def matches_existing(csv_title: str, existing_titles: set[str]) -> bool:
    """检查 CSV 作品名是否匹配任何 DB 已有作品."""
    csv_clean = csv_title.strip()
    if not csv_clean:
        return False
    for db_title in existing_titles:
        # Check substring match in both directions
        if csv_clean in db_title or db_title in csv_clean:
            return True
    return False


def get_image_files(csv_row: dict, images_dir: Path) -> list[Path]:
    """Get image files for an artwork by matching filename patterns.

    First tries the 'filenames' CSV field. Falls back to glob matching
    files named like '{dynasty}_{artist}_{title}_*.jpg' in the images dir.
    """
    # First try explicit filenames from CSV
    filenames_str = csv_row.get("filenames", "").strip()
    if filenames_str:
        files = []
        for name in filenames_str.split("|"):
            name = name.strip()
            if not name:
                continue
            filepath = images_dir / name
            if filepath.exists():
                files.append(filepath)
            else:
                matches = sorted(images_dir.glob(name))
                if matches:
                    files.append(matches[0])
        if files:
            return files

    # Fallback: match by title pattern
    title = csv_row.get("title", "").strip()
    artist = csv_row.get("artist", "").strip()
    dynasty = csv_row.get("dynasty", "").strip()

    if not title:
        return []

    # Build glob pattern: 清_朱耷_兰竹图_*.jpg
    # Clean title for filename-safe chars
    safe_title = title
    pattern = f"{dynasty}_{artist}_{safe_title}_*.jpg"
    matches = sorted(images_dir.glob(pattern))

    # Also try without dynasty prefix
    if not matches:
        pattern2 = f"*_{artist}_{safe_title}_*.jpg"
        matches = sorted(images_dir.glob(pattern2))

    # Also try with album page naming
    if not matches:
        pattern3 = f"*_{artist}_*{safe_title}*.jpg"
        matches = sorted(images_dir.glob(pattern3))

    # Filter out duplicate files (Edge creates "(1)" copies)
    filtered = []
    for f in matches:
        name = f.name
        # Skip Edge duplicate naming like "xxx (1).jpg"
        if " (1)" in name or " (2)" in name:
            # Check if the original exists
            orig_name = name.replace(" (1)", "").replace(" (2)", "")
            orig = f.parent / orig_name
            if orig.exists():
                continue  # Skip duplicate, keep original
        filtered.append(f)

    return filtered


def parse_dimensions(dims_str: str) -> tuple[float | None, float | None]:
    """Parse dimension string like '120x57.4厘米' into (width_cm, height_cm)."""
    if not dims_str or not dims_str.strip():
        return None, None
    import re
    # Match: WxH followed by optional unit
    m = re.match(r'([\d.]+)\s*[x×X]\s*([\d.]+)\s*(?:厘?米|cm)?', dims_str.strip())
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass
    return None, None


CN_NUM = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
    '〇': 0, '零': 0, '○': 0,
}


def parse_year(text: str) -> int | None:
    """Extract creation year from text (handles Arabic and Chinese numerals).
    Looks for '创作年代：YYYY' or '创作年代：一二三四' patterns."""
    if not text:
        return None
    import re
    idx = text.find('创作年代')
    if idx < 0:
        return None
    after = text[idx + 4:]
    after = after.lstrip('：:：| ')

    # Try Arabic year first
    m = re.search(r'(\d{4})', after[:30])
    if m:
        y = int(m.group(1))
        if 1000 < y < 2026:
            return y

    # Try Chinese numerals (e.g. "一六六五" → 1665)
    cn_year = ''
    for ch in after[:20]:
        if ch in CN_NUM:
            cn_year += str(CN_NUM[ch])
        elif ch == '年':
            break
        elif ch in '十百千—–- ':
            continue
        else:
            break
    if len(cn_year) == 4 and cn_year.isdigit():
        y = int(cn_year)
        if 1000 < y < 2026:
            return y
    return None


def build_metadata(csv_row: dict) -> dict:
    """将 CSV 行映射为 API 字段."""
    meta = {}

    # Direct mappings
    meta["title"] = csv_row.get("title", "").strip()
    meta["artist"] = csv_row.get("artist", "").strip()
    meta["period"] = csv_row.get("dynasty", "").strip()
    meta["current_location"] = csv_row.get("museum", "").strip()
    meta["material"] = csv_row.get("material", "").strip()
    meta["mounting_format"] = csv_row.get("format", "").strip()

    # Parse dimensions into structured fields
    dims_str = csv_row.get("dimensions", "").strip()
    width_cm, height_cm = parse_dimensions(dims_str)
    if width_cm is not None:
        meta["artwork_width_cm"] = width_cm
    if height_cm is not None:
        meta["artwork_height_cm"] = height_cm

    # Parse year from inscriptions/description
    text_for_year = (csv_row.get("inscriptions", "") or "") + " " + (csv_row.get("description", "") or "")
    yr = parse_year(text_for_year)
    if yr is not None:
        meta["year"] = yr

    # Build notes from description + seals (NOT dimensions, now in structured fields)
    notes_parts = []
    desc = csv_row.get("description", "").strip()
    if desc:
        notes_parts.append(desc)
    author_seals = csv_row.get("author_seals", "").strip()
    if author_seals:
        notes_parts.append(f"作者印: {author_seals}")
    collection_seals = csv_row.get("collection_seals", "").strip()
    if collection_seals:
        notes_parts.append(f"收藏印: {collection_seals}")
    meta["notes"] = " | ".join(notes_parts)

    # Tags: combine technique + tags
    tag_parts = []
    technique = csv_row.get("technique", "").strip()
    if technique:
        tag_parts.append(technique)
    tags = csv_row.get("tags", "").strip()
    if tags:
        tag_parts.append(tags)
    meta["free_tags"] = ", ".join(tag_parts)

    # Inscriptions
    inscriptions = csv_row.get("inscriptions", "").strip()
    if inscriptions:
        # Truncate long inscriptions for the inscription_author field
        meta["inscription_author"] = inscriptions[:200]
        # Append full inscriptions to notes if long
        if len(inscriptions) > 200:
            current_notes = meta.get("notes", "")
            meta["notes"] = f"{current_notes} | 款识: {inscriptions}"

    # Other authors
    other = csv_row.get("other_authors", "").strip()
    if other and not meta.get("inscription_author"):
        meta["inscription_author"] = other

    # Visibility
    meta["visibility"] = "public"

    return meta


def upload_file(
    filepath: Path, metadata: dict, api_base: str, token: str, library_id: int
) -> bool:
    """上传单个图片文件。自动处理文件名去序号（避免被误解析为年份）。"""
    import shutil
    import tempfile

    headers = {"Authorization": f"Bearer {token}"}

    # Clean filename: strip sequence number like _1, _14 before .jpg
    # "清_朱耷_兰竹图_1.jpg" → "清_朱耷_兰竹图.jpg"
    orig_name = filepath.name
    stem = filepath.stem
    # Remove trailing _NNN sequence number
    cleaned_stem = stem
    parts = stem.split("_")
    if parts and parts[-1].isdigit() and 1 <= int(parts[-1]) <= 200:
        cleaned_stem = "_".join(parts[:-1])
    cleaned_name = f"{cleaned_stem}{filepath.suffix}"

    # Copy to temp with cleaned name
    tmpdir = Path(tempfile.gettempdir()) / "artwork_upload"
    tmpdir.mkdir(exist_ok=True)
    tmp_path = tmpdir / cleaned_name
    shutil.copy2(filepath, tmp_path)

    # Prepare metadata form fields
    data_fields = {}
    for key, val in metadata.items():
        if val:
            data_fields[key] = val

    try:
        with open(tmp_path, "rb") as f:
            files = {"file": (cleaned_name, f, "image/jpeg")}
            resp = requests.post(
                f"{api_base}/api/v1/libraries/{library_id}/artworks",
                files=files,
                data=data_fields,
                headers=headers,
                timeout=120,
            )
        if resp.status_code in (200, 201):
            return True
        else:
            detail = resp.text[:200]
            print(f"     [FAIL] HTTP {resp.status_code}: {detail}")
            return False
    except Exception as e:
        print(f"     [FAIL] {e}")
        return False
    finally:
        # Cleanup temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def main():
    args = parse_args()

    csv_path = Path(args.csv)
    images_dir = Path(args.images)

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        sys.exit(1)
    if not images_dir.is_dir():
        print(f"ERROR: Images directory not found: {images_dir}")
        sys.exit(1)

    # Login
    print(f"Logging in to {args.api_base}...")
    token = login(args.api_base, args.phone, args.password)
    print("   [OK] Authenticated")

    # Get existing titles for dedup
    print(f"Fetching existing artworks in library {args.library_id}...")
    existing_titles = get_existing_titles(args.api_base, token, args.library_id)
    print(f"   Found {len(existing_titles)} existing titles")

    # Read CSV
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"CSV: {len(rows)} artworks")

    # Filter: skip existing
    new_artworks = []
    skipped_artworks = []
    for row in rows:
        title = row.get("title", "").strip()
        if matches_existing(title, existing_titles):
            skipped_artworks.append(title)
        else:
            new_artworks.append(row)

    print(f"   New to upload: {len(new_artworks)}")
    print(f"   Skip (duplicate): {len(skipped_artworks)}")
    if skipped_artworks:
        print(f"   Skipped titles: {', '.join(skipped_artworks[:10])}"
              f"{'...' if len(skipped_artworks) > 10 else ''}")

    if args.max:
        new_artworks = new_artworks[:args.max]
        print(f"   (limited to {args.max} by --max)")

    if args.dry_run:
        print("\n=== DRY RUN - will upload ===")
        for i, row in enumerate(new_artworks):
            files = get_image_files(row, images_dir)
            print(f"  {i+1}. {row['title']} ({len(files)} files)")
            for fp in files[:3]:
                print(f"     - {fp.name} ({fp.stat().st_size / 1e6:.1f} MB)")
            if len(files) > 3:
                print(f"     ... and {len(files) - 3} more")
        print(f"\nTotal: {len(new_artworks)} artworks to upload")
        return

    # Upload
    total_ok = 0
    total_fail = 0
    uploaded_files: set[str] = set()  # track absolute paths to prevent duplicates
    for i, row in enumerate(new_artworks):
        title = row.get("title", "").strip()
        files = get_image_files(row, images_dir)
        if not files:
            print(f"  [{i+1}/{len(new_artworks)}] {title}: no files found, skipping")
            continue

        # Filter out files already uploaded (same file matched by different CSV entries)
        unique_files = []
        for fp in files:
            abs_path = str(fp.resolve())
            if abs_path not in uploaded_files:
                unique_files.append(fp)
                uploaded_files.add(abs_path)
            else:
                print(f"     [SKIP] {fp.name} (already uploaded)")
        if not unique_files:
            print(f"  [{i+1}/{len(new_artworks)}] {title}: all files already uploaded, skipping")
            continue

        metadata = build_metadata(row)
        print(f"  [{i+1}/{len(new_artworks)}] {title} ({len(unique_files)} files)")

        ok_count = 0
        for fp in unique_files:
            if upload_file(fp, metadata, args.api_base, token, args.library_id):
                ok_count += 1
                print(f"     [OK] {fp.name}")
            else:
                total_fail += 1
            time.sleep(0.5)  # rate limit

        total_ok += ok_count
        print(f"   -> {ok_count}/{len(files)} uploaded for {title}")

    print(f"\n{'='*60}")
    print(f"Done. Uploaded: {total_ok} files, Failed: {total_fail}")
    print(f"Skipped (duplicate): {len(skipped_artworks)} artworks")
    print(f"New artworks added: {len(new_artworks)}")


if __name__ == "__main__":
    main()
