#!/usr/bin/env python3
"""
回填作品元数据（尺寸 + 年份）
从 CSV 元数据中解析 dimensions 和 创作年代，更新到数据库。

用法:
  python backend/backfill_metadata.py \
    --csv "E:/下载/朱耷/artwork_metadata.csv" \
    --artist "朱耷" --library-id 9
"""
import argparse, csv, re, sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "calligraphy.db"

# Chinese numeral conversion
CN_NUM = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9,
    '〇': 0, '零': 0, '○': 0,
}


def parse_args():
    p = argparse.ArgumentParser(description="从CSV回填作品元数据")
    p.add_argument("--csv", required=True, help="CSV 元数据文件")
    p.add_argument("--artist", required=True, help="艺术家名称")
    p.add_argument("--library-id", type=int, required=True, help="作品库 ID")
    p.add_argument("--dry-run", action="store_true", help="只预览，不实际修改")
    return p.parse_args()


def parse_dimensions(dims_str):
    """Parse '120x57.4厘米' → (120.0, 57.4) or (None, None)."""
    if not dims_str or not dims_str.strip():
        return None, None
    m = re.match(r'([\d.]+)\s*[x×X]\s*([\d.]+)\s*(?:厘?米|cm)?', dims_str.strip())
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass
    return None, None


def parse_year(text):
    """Extract creation year from text (handles Arabic and Chinese numerals)."""
    if not text:
        return None
    idx = text.find('创作年代')
    if idx < 0:
        return None
    after = text[idx + 4:]
    after = after.lstrip('：:：| ')

    # Try Arabic year first (e.g. "1688")
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


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"ERROR: DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"CSV: {len(rows)} rows")

    dims_updated = 0
    dims_skip_none = 0
    dims_skip_notfound = 0
    dims_skip_already = 0
    year_updated = 0
    year_skip_none = 0
    year_skip_notfound = 0
    year_skip_already = 0

    for row in rows:
        title = row.get("title", "").strip()
        if not title:
            continue

        # Build text for year parsing
        text = (row.get('inscriptions', '') or '') + ' ' + (row.get('description', '') or '')

        # Find matching artwork
        cur = conn.execute(
            "SELECT id, title, artwork_width_cm, artwork_height_cm, year "
            "FROM tubi_analyses "
            "WHERE artist=? AND library_id=? AND title LIKE ?",
            (args.artist, args.library_id, f"%{title}%"),
        )
        matches = cur.fetchall()

        if not matches:
            cur = conn.execute(
                "SELECT id, title, artwork_width_cm, artwork_height_cm, year "
                "FROM tubi_analyses "
                "WHERE artist=? AND library_id=? AND title=?",
                (args.artist, args.library_id, title),
            )
            matches = cur.fetchall()

        if not matches:
            dims_skip_notfound += 1
            year_skip_notfound += 1
            continue

        for m in matches:
            db_id = m["id"]
            db_title = m["title"]

            # --- Dimensions ---
            w_cm, h_cm = parse_dimensions(row.get("dimensions", ""))
            if w_cm is not None:
                if m["artwork_width_cm"] is None or m["artwork_height_cm"] is None:
                    if not args.dry_run:
                        conn.execute(
                            "UPDATE tubi_analyses SET artwork_width_cm=?, artwork_height_cm=? WHERE id=?",
                            (w_cm, h_cm, db_id),
                        )
                    dims_updated += 1
                    print(f"  [DIMS] {db_title[:30]} → {w_cm}x{h_cm} cm")
                else:
                    dims_skip_already += 1
            else:
                dims_skip_none += 1

            # --- Year ---
            y = parse_year(text)
            if y is not None:
                if m["year"] is None:
                    if not args.dry_run:
                        conn.execute(
                            "UPDATE tubi_analyses SET year=? WHERE id=?",
                            (y, db_id),
                        )
                    year_updated += 1
                    print(f"  [YEAR] {db_title[:30]} → {y}")
                else:
                    year_skip_already += 1
            else:
                year_skip_none += 1

    conn.commit() if not args.dry_run else None

    print(f"\n--- Results ---")
    print(f"Dimensions: updated={dims_updated} skip_none={dims_skip_none} "
          f"skip_notfound={dims_skip_notfound} skip_already={dims_skip_already}")
    print(f"Year:       updated={year_updated} skip_none={year_skip_none} "
          f"skip_notfound={year_skip_notfound} skip_already={year_skip_already}")

    cur = conn.execute(
        "SELECT COUNT(*) as cnt, COUNT(artwork_width_cm) as dims, COUNT(year) as yrs "
        "FROM tubi_analyses WHERE artist=? AND library_id=?",
        (args.artist, args.library_id),
    )
    r = cur.fetchone()
    print(f"Library #{args.library_id}: {r['cnt']} artworks, {r['dims']} dims, {r['yrs']} years")

    conn.close()


if __name__ == "__main__":
    main()
