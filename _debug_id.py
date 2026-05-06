import urllib.request, json

r1 = json.loads(urllib.request.urlopen(
    "http://localhost:8001/api/v1/tubi/result/80b05398-7768-48a8-bda0-ff5c450c089c").read())
r2 = json.loads(urllib.request.urlopen(
    "http://localhost:8001/api/v1/tubi/results?skip=0&limit=2000").read())

detail_id = r1["data"]["id"]
items = r2["data"]
match = [x for x in items if x["id"] == detail_id]

if match:
    idx = items.index(match[0])
    print("FOUND at index %d/%d" % (idx, len(items)))
    if idx > 0:
        print("prev id:", items[idx-1]["id"])
    if idx < len(items) - 1:
        print("next id:", items[idx+1]["id"])
else:
    print("NOT FOUND")
    print("detail_id type=%s value=%r" % (type(detail_id).__name__, detail_id))
    print("items[0] id type=%s value=%r" % (type(items[0]["id"]).__name__, items[0]["id"]))
