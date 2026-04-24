# -*- coding: utf-8 -*-
import requests, json, time

start = time.time()
try:
    r = requests.post(
        "http://127.0.0.1:8001/api/v1/content-analysis/insight",
        json={"artist": "李鱓"},
        timeout=120
    )
    elapsed = time.time() - start
    print(f"Status: {r.status_code}, Time: {elapsed:.1f}s")
    if r.status_code == 200:
        data = r.json()
        print("Success:", data.get("success"))
        report = data.get("report", "")
        print("Report length:", len(report))
        print("First 300 chars:", report[:300])
    else:
        print("Error:", r.text[:500])
except Exception as e:
    print("Exception:", e)