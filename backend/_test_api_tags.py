# -*- coding: utf-8 -*-
import requests, json

r = requests.get("http://127.0.0.1:8001/api/v1/content-analysis/stats", params={"artist": "李鱓"}, timeout=10)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    tags = data.get("material_tags", [])
    print(f"material_tags count: {len(tags)}")
    for t in tags[:20]:
        print(f"  {t['tag']}: {t['count']} ({t['percentage']}%)")
else:
    print("Error:", r.text[:300])