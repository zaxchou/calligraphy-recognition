import sqlite3, json

conn = sqlite3.connect("/opt/calligraphy-recognition/backend/data/calligraphy.db")
c = conn.cursor()
c.execute("SELECT content_analysis FROM tubi_analyses WHERE content_analysis IS NOT NULL AND content_analysis != ''")

all_themes = {}
for row in c.fetchall():
    try:
        ca = json.loads(row[0])
        for t in ca.get("themes", []):
            name = t.get("name", "")
            code = t.get("code", "")
            conf = t.get("confidence", 0)
            key = f"{code}_{name}"
            if key not in all_themes:
                all_themes[key] = {"code": code, "name": name, "count": 0, "min_conf": 1.0, "max_conf": 0.0}
            all_themes[key]["count"] += 1
            all_themes[key]["min_conf"] = min(all_themes[key]["min_conf"], conf)
            all_themes[key]["max_conf"] = max(all_themes[key]["max_conf"], conf)
    except:
        pass

print("All theme types found:")
for key in sorted(all_themes.keys(), key=lambda k: -all_themes[k]["count"]):
    info = all_themes[key]
    print(f"  code={info['code']} '{info['name']}': {info['count']} occ, conf {info['min_conf']:.2f}-{info['max_conf']:.2f}")

conn.close()
