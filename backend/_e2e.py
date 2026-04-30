import requests, json

API = 'http://localhost:3000/api/v1/knowledge'
r = requests.post(API + '/search',
    json={'query': '起承转合', 'limit': 3}, timeout=15)
d = r.json()

def has_dollar(obj):
    if isinstance(obj, str) and '$' in obj:
        return True
    elif isinstance(obj, dict):
        return any(has_dollar(v) for v in obj.values())
    elif isinstance(obj, list):
        return any(has_dollar(v) for v in obj)
    return False

clean = not has_dollar(d)
print('Response has dollar:', not clean)

r2 = requests.get('http://localhost:3000/api/v1/knowledge/images/687fe38f-8f0f-4000-b20f-655519c3c04f', timeout=5)
print('Image UUID:', r2.status_code, len(r2.content))

for res in d.get('results', []):
    for ai in res.get('associated_images', []):
        url = ai.get('url','')
        if url:
            r3 = requests.get('http://localhost:3000' + url, timeout=5)
            print('Image assoc:', r3.status_code, len(r3.content), url[-40:])
            break
    break

if clean:
    print('E2E PASS')
