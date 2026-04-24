import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from app.services.tubi_mask_refiner import refine_paint_mask_stats


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
    db_path = os.path.join("data", "calligraphy.db")
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            "select image_id, image_width, image_height, filepath, regions "
            "from tubi_analyses "
            "where status = 'analyzed' and regions is not null"
        )
        rows = cur.fetchall()
    finally:
        con.close()

    if not rows:
        print("no_analyzed_rows")
        return 2

    rows.sort(key=lambda r: int(r[1] or 0) * int(r[2] or 0))
    image_id, w, h, fp, regions = rows[0]
    w = int(w or 0)
    h = int(h or 0)

    if isinstance(regions, str):
        regions = json.loads(regions)

    debug_dir = os.path.join("data", "tubi_debug", str(image_id))
    res = refine_paint_mask_stats(
        image_path=fp,
        painting_regions=(regions or {}).get("painting_regions") or [],
        image_width=w,
        image_height=h,
        bg_sample_ratio=float(os.getenv("TUBI_PAINT_BG_SAMPLE_RATIO", "0.06")),
        bg_deltae=float(os.getenv("TUBI_PAINT_BG_DELTAE", "12.0")),
        bg_grad_max=float(os.getenv("TUBI_PAINT_BG_GRAD_MAX", "8.0")),
        debug_dir=debug_dir,
    )
    print("picked", image_id, w, h, fp)
    print("refine", res)
    if os.path.isdir(debug_dir):
        print("debug_dir", debug_dir)
        for name in sorted(os.listdir(debug_dir)):
            p = os.path.join(debug_dir, name)
            print(" -", name, os.path.getsize(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
