"""检查大纲页码"""
import requests
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

book_id = "b250300e-8ae4-486d-a73b-854708c048d3"
r = requests.get(f'http://localhost:8001/api/v1/knowledge/books/{book_id}/outline')
data = r.json()
outline = data.get('outline', [])

print(f"Total items: {len(outline)}")
print("\n=== Last 15 items ===")
for i, item in enumerate(outline[-15:]):
    idx = len(outline) - 15 + i
    print(f"  {idx:3d}. page={item.get('page', 0):3d}, level={item.get('level', 0)}, title={item.get('title', '')[:60]}")

# 检查页码分布
pages = [item.get('page', 0) for item in outline]
print(f"\n=== Page stats ===")
print(f"  Min: {min(pages)}")
print(f"  Max: {max(pages)}")
print(f"  Items with page=700: {sum(1 for p in pages if p == 700)}")
print(f"  Items with page>600: {sum(1 for p in pages if p > 600)}")
