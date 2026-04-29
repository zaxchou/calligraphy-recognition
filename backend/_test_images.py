import requests, json

r = requests.post('http://localhost:8001/api/v1/knowledge/search',
    json={'query': '起承转合', 'limit': 5}, timeout=15)
d = r.json()
for res in d.get('results', []):
    assoc = res.get('associated_images', [])
    if assoc:
        print('associated_images[0] keys:', list(assoc[0].keys()))
        print('  url:', assoc[0].get('url','')[:80])
        print('  stored_url:', assoc[0].get('stored_url','')[:80])
        break

    img = res.get('image', {})
    if img:
        print('image keys:', list(img.keys()))
        print('  url:', img.get('url','')[:80])
        print('  stored_url:', img.get('stored_url','')[:80])
        break
