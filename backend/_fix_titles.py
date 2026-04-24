import sqlite3
import re

def parse_calligraphy_filename(filename):
    name = os.path.splitext(filename)[0]
    parts = name.split('_')
    if len(parts) < 3:
        return {"title": name, "artist": "李鱓", "year": None, "period": None}

    artist = parts[1] if parts[1] else "李鱓"
    year = None
    period = None
    title_parts = []
    for i, part in enumerate(parts):
        if re.match(r"^\d{4}$", part):
            year = int(part)
            if artist in ("李鱓",):
                if year <= 1722:
                    period = "早期"
                elif year <= 1745:
                    period = "中期"
                else:
                    period = "晚期"
            break
        elif part == "年代不详":
            year = None
            period = "年代不详"
            break
        else:
            if i > 1:  # skip dynasty (0) and artist (1)
                title_parts.append(part)
    title = "_".join(title_parts) if title_parts else name
    return {"title": title, "artist": artist, "year": year, "period": period}

import os
conn = sqlite3.connect('data/calligraphy.db')
cur = conn.cursor()

cur.execute("SELECT id, filename FROM tubi_analyses WHERE id >= 193 ORDER BY id DESC LIMIT 3")
rows = cur.fetchall()
for r in rows:
    parsed = parse_calligraphy_filename(r[1])
    cur.execute(
        "UPDATE tubi_analyses SET title=?, year=?, period=? WHERE id=?",
        (parsed["title"], parsed["year"], parsed["period"], r[0])
    )
    print(f"id={r[0]} title='{parsed['title']}' year={parsed['year']} period={parsed['period']}")

conn.commit()
conn.close()
