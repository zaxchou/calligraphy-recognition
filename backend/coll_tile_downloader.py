#!/usr/bin/env python3
"""
COLL 类型作品瓦片下载器
用于中华珍宝馆"未开放下载"的作品（hdp.src="COLL"），从阿里云 OSS 下载瓦片并拼接。
"""

import io
import json
import math
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

API = "http://127.0.0.1:10086/command"
SESSION = "calligraphy"
TILE_SIZE = 256
OUTPUT_DIR = Path("E:/下载/潘天寿")


def evaluate(code: str) -> str:
    r = requests.post(API, json={"action": "evaluate", "args": {"code": code}, "session": SESSION})
    return r.json()["data"]["value"]


def navigate(url: str) -> None:
    requests.post(API, json={"action": "navigate", "args": {"url": url, "newTab": False}, "session": SESSION})
    time.sleep(5)


def get_hdp_info(source_id: str) -> dict | None:
    """Navigate to artwork page and extract HDP info from React state/API."""
    DETAIL_URL = (
        f"http://g2.ltfc.net/source_list/HUIA/"
        f"%5B%225df8a8c85e3be25e694d7549%22%5D?page=1&sourceId={source_id}"
    )
    navigate(DETAIL_URL)
    time.sleep(3)

    # Extract from React state
    code = """(() => {
        const root = document.getElementById('root');
        if (!root) return 'no root';
        const fiberKey = Object.keys(root).find(k => k.startsWith('__reactFiber'));
        if (!fiberKey) return 'no fiber';
        let fiber = root[fiberKey];
        let depth = 0;
        while (fiber && depth < 100) {
            if (fiber.memoizedState) {
                let state = fiber.memoizedState;
                while (state) {
                    const val = state.queue?.lastRenderedState || state.memoizedState;
                    if (val && typeof val === 'object' && !Array.isArray(val) && val.hdp) {
                        // Found it - extract hdp info
                        if (val.hdp.hdpcoll) {
                            const coll = val.hdp.hdpcoll;
                            const hdps = coll.hdps || [];
                            const result = hdps.map(h => ({
                                name: h.name || '',
                                resourceId: h.resourceId,
                                maxlevel: h.maxlevel,
                                width: h.size?.width || 0,
                                height: h.size?.height || 0,
                                tilesDir: h.tilesDir || 'cagstore',
                                tilesSource: h.tilesSource || ''
                            }));
                            return JSON.stringify({title: val.name, owner: val.owner, hdps: result});
                        }
                    }
                    state = state.next;
                }
            }
            fiber = fiber.return;
            depth++;
        }
        return 'hdp not found at depth ' + depth;
    })()"""
    result = evaluate(code)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        print(f"  Failed to parse: {result[:200]}")
        return None


def get_tile_url(resource_id: str, level: int, col: int, row: int) -> str:
    """Generate OSS tile URL. The auth params come from the thumb tile URL pattern."""
    # Use the CDN URL pattern observed in network requests
    return (
        f"https://cag-ac.ltfc.net/cagstore/{resource_id}/{level}/{col}_{row}.jpg"
    )


def download_and_stitch(hdp_info: dict, artwork_title: str) -> bool:
    """Download all tiles at maxlevel and stitch into a single image."""
    hdps = hdp_info.get("hdps", [])
    if not hdps:
        print("  No HDP sub-images found")
        return False

    for idx, hdp in enumerate(hdps):
        resource_id = hdp["resourceId"]
        maxlevel = hdp["maxlevel"]
        full_w = hdp["width"]
        full_h = hdp["height"]
        name = hdp.get("name", f"sub_{idx}")

        if full_w <= 0 or full_h <= 0:
            print(f"  [{idx+1}/{len(hdps)}] {name}: unknown dimensions, skipping")
            continue

        # Calculate tiles needed at maxlevel
        # At level L, the image is scaled by 2^L / 2^maxlevel
        # Tile coverage: each tile covers TILE_SIZE pixels at that level's resolution
        scale = 2 ** maxlevel
        level_w = round(full_w * scale / scale)  # = full_w at maxlevel...
        # Actually at maxlevel, 1 pixel = 1 tile pixel
        # Number of tiles: ceil(full_w / 256), ceil(full_h / 256)
        cols = math.ceil(full_w / TILE_SIZE)
        rows = math.ceil(full_h / TILE_SIZE)

        print(f"  [{idx+1}/{len(hdps)}] {name}")
        print(f"    Size: {full_w}x{full_h}, Tiles: {cols}x{rows} = {cols*rows} tiles at level {maxlevel}")

        # Create stitched image
        stitched = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE))
        downloaded = 0
        failed = 0

        for row in range(rows):
            for col in range(cols):
                url = get_tile_url(resource_id, maxlevel, col, row)
                try:
                    resp = requests.get(url, timeout=30, headers={
                        "Referer": "http://g2.ltfc.net/",
                        "User-Agent": "Mozilla/5.0"
                    })
                    if resp.status_code == 200:
                        img = Image.open(io.BytesIO(resp.content))
                        stitched.paste(img, (col * TILE_SIZE, row * TILE_SIZE))
                        downloaded += 1
                    else:
                        failed += 1
                        if failed <= 3:
                            print(f"    HTTP {resp.status_code} at tile ({col},{row})")
                except Exception as e:
                    failed += 1
                    if failed <= 3:
                        print(f"    Error at tile ({col},{row}): {e}")

                # Progress indicator
                if (row * cols + col + 1) % 50 == 0:
                    print(f"    Progress: {row * cols + col + 1}/{cols * rows} ({downloaded} ok, {failed} fail)")

        if downloaded == 0:
            print(f"    FAILED: no tiles downloaded")
            continue

        # Crop to actual image dimensions
        stitched = stitched.crop((0, 0, full_w, full_h))

        # Save
        suffix = f"_{idx+1}" if len(hdps) > 1 else ""
        safe_title = artwork_title.replace("/", "_").replace("\\", "_")
        out_path = OUTPUT_DIR / f"当代_潘天寿_{safe_title}{suffix}.jpg"
        stitched.save(out_path, "JPEG", quality=92)
        size_mb = out_path.stat().st_size / 1e6
        print(f"    SAVED: {out_path.name} ({size_mb:.1f} MB, {downloaded} tiles)")

    return True


def main():
    # These 6 artworks couldn't download via normal API
    failed_ids = [
        ("67377ac3a7a81319b586295a", "灵岩涧一角"),
        ("67377ac4a7a81319b586295d", "晚风"),
        ("67377ad4a7a81319b586295f", "彩墨写雁荡山花"),
        ("67926e06ccb75b6ab3298d3b", "指墨鹰石图轴"),
        ("67926e2eccb75b6ab3298d3d", "烟云微茫图轴"),
        ("680c97c564ff5875f6c29ddb", "梅月松风图"),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for source_id, title in failed_ids:
        print(f"\n{'='*60}")
        print(f"Processing: {title} ({source_id})")

        hdp_info = get_hdp_info(source_id)
        if not hdp_info:
            print("  Failed to get HDP info")
            continue

        actual_title = hdp_info.get("title", title)
        print(f"  Title: {actual_title}")
        print(f"  Owner: {hdp_info.get('owner', '?')}")

        download_and_stitch(hdp_info, actual_title)
        time.sleep(2)

    print(f"\nDone. Files saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
