import os
import sqlite3
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
    target = os.environ.get("TUBI_FIND", "").strip()
    if not target:
        print("set TUBI_FIND to image_id or filename substring")
        return 2

    db_path = os.path.join("data", "calligraphy.db")
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        q = (
            "select image_id, status, filename, filepath, painting_percent, inscription_percent, blank_percent, analysis_note "
            "from tubi_analyses "
            "where image_id like ? or filename like ? or filepath like ? "
            "order by created_at desc limit 20"
        )
        like = f"%{target}%"
        rows = cur.execute(q, (like, like, like)).fetchall()
        if not rows:
            print("no_match")
            return 1
        for r in rows:
            print(r[0], r[1], r[2], r[3], r[4], r[5], r[6], (r[7] or "")[:120])
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())

