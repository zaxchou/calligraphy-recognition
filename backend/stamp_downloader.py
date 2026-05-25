#!/usr/bin/env python3
"""
中华珍宝馆印章下载 + 导入脚本
用法:
  python stamp_downloader.py --artist-url "http://g2.ltfc.net/artist_sign_list/{artist_id}?name={name}" --artist "徐渭"
"""

import argparse, json, os, re, sys, time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageOps

API = "http://127.0.0.1:10086/command"
SESSION = "stamp-download"
DB_PATH = Path(__file__).parent / "data" / "calligraphy.db"


def parse_args():
    p = argparse.ArgumentParser(description="中华珍宝馆印章下载导入")
    p.add_argument("--artist-url", required=True, help="印章列表页 URL")
    p.add_argument("--artist", required=True, help="艺术家名称")
    p.add_argument("--dynasty", default="", help="朝代")
    p.add_argument("--output", default=None, help="输出目录 (默认 backend/data/seals/<艺术家>)")
    return p.parse_args()


def api(action, args=None):
    r = requests.post(API, json={"action": action, "args": args or {}, "session": SESSION}, timeout=60)
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(d.get("error", {}).get("message", d))
    return d["data"]


def evaluate(code):
    return api("evaluate", {"code": code}).get("value", "")


def download_stamps(artist_url: str, output_dir: Path) -> list[dict]:
    """Navigate to stamp page and download all stamp images. Returns stamp metadata list."""
    print(f"Navigating to: {artist_url}")
    api("navigate", {"url": artist_url, "newTab": True})
    time.sleep(5)

    # Get image URLs
    imgs = json.loads(evaluate(
        "JSON.stringify(Array.from(document.querySelectorAll('img[src*=stamp_raw]')).map(i => i.src))"
    ))
    print(f"Found {len(imgs)} stamp images")

    # Parse stamp names from page text
    text = evaluate("document.body.innerText")
    lines = [l.strip() for l in text.split('\n') if l.strip() and '印鉴' not in l]

    stamps = []
    img_idx = 0
    idx = 0
    while idx < len(lines) - 1 and img_idx < len(imgs):
        name = lines[idx]
        pub = lines[idx + 1]
        if '出版社' in pub or '主编' in pub or '印谱' in pub:
            stamps.append({"name": name, "publisher": pub, "url": imgs[img_idx]})
            img_idx += 1
            idx += 2
        else:
            idx += 1

    print(f"Parsed {len(stamps)} stamps with names")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "thumbs").mkdir(exist_ok=True)

    downloaded = 0
    for s in stamps:
        name = s['name']
        filepath = output_dir / f"{name}.jpg"
        if filepath.exists():
            downloaded += 1
            continue

        clean_url = re.sub(r'&?image_process=[^&]*', '', s['url'])
        try:
            resp = requests.get(clean_url, timeout=30,
                headers={"Referer": "http://g2.ltfc.net/", "User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 500:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                downloaded += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
        time.sleep(0.2)

    print(f"Downloaded: {downloaded}/{len(stamps)}")
    return stamps


def import_to_db(stamps: list[dict], artist: str, dynasty: str, seal_dir: Path):
    """Import downloaded stamps into the seals database."""
    import sqlite3

    db = DB_PATH
    if not db.exists():
        print(f"DB not found: {db}")
        return

    conn = sqlite3.connect(str(db))
    thumb_dir = seal_dir / "thumbs"
    thumb_dir.mkdir(exist_ok=True)

    # Find or create artist
    cur = conn.execute("SELECT id FROM artists WHERE name=?", (artist,))
    row = cur.fetchone()
    if not row:
        conn.execute("INSERT INTO artists (name, dynasty) VALUES (?, ?)", (artist, dynasty))
        conn.commit()
        artist_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        artist_id = row[0]

    imported = 0
    for s in stamps:
        name = s['name']
        cur = conn.execute("SELECT id FROM seals WHERE name=? AND artist_name=?", (name, artist))
        if cur.fetchone():
            continue

        now = datetime.now().isoformat()
        pub = s.get('publisher', '')
        desc = f"来源: {pub}" if pub else name

        conn.execute("""INSERT INTO seals (name, artist_id, artist_name, seal_type, description, created_at, updated_at, source)
            VALUES (?, ?, ?, '印章', ?, ?, ?, '中华珍宝馆')""",
            (name, artist_id, artist, desc, now, now))

        seal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        img_path = seal_dir / f"{name}.jpg"

        # Generate thumbnail
        thumb_path = thumb_dir / f"{name}_thumb.jpg"
        if img_path.exists() and not thumb_path.exists():
            try:
                with Image.open(img_path) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(thumb_path, "JPEG", quality=85)
            except Exception:
                pass

        rel_path = f"/static/seals/{img_path.name}"
        rel_thumb = f"/static/seals/thumbs/{thumb_path.name}" if thumb_path.exists() else ""
        conn.execute("""INSERT INTO seal_images (seal_id, path, description, sort_order, created_at, thumbnail_path)
            VALUES (?, ?, ?, 1, ?, ?)""",
            (seal_id, rel_path, name, now, rel_thumb))

        imported += 1

    conn.commit()
    cur = conn.execute("SELECT COUNT(*) FROM seals WHERE artist_name=?", (artist,))
    total = cur.fetchone()[0]
    print(f"Imported: {imported} new seals (total {total} for {artist})")
    conn.close()


def main():
    args = parse_args()
    if args.output:
        output_dir = Path(args.output)
        thumb_dir = output_dir / "thumbs"
    else:
        output_dir = Path(__file__).parent / "data" / "seals"
        thumb_dir = output_dir / "thumbs"

    stamps = download_stamps(args.artist_url, output_dir)
    if stamps:
        import_to_db(stamps, args.artist, args.dynasty, output_dir)

    api("close_session", {})
    print("Done.")


if __name__ == "__main__":
    main()
