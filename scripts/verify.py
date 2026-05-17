import urllib.request, json
r = urllib.request.urlopen('http://localhost:3000/api/v1/artists?featured=1&page_size=10')
d = json.loads(r.read())
print(f'Total featured: {d["total"]}')
for a in d['artists']:
    print(f'  {a["name"]}: artwork_count={a.get("artwork_count", "MISSING")}')
