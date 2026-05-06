#!/usr/bin/env python3
import json, urllib.request
resp = urllib.request.urlopen("http://localhost:6333/collections/knowledge_texts")
data = json.loads(resp.read())
c = data.get("result", {})
vc = c.get("config", {}).get("params", {}).get("vectors", {})
print(f"vector_size: {vc.get('size')}")
print(f"distance: {vc.get('distance')}")
print(f"points: {c.get('points_count')}")
