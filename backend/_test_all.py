import requests, json

r = requests.post('http://localhost:8001/api/v1/knowledge/search',
    json={'query': '起承转合', 'limit': 3}, timeout=15)
d = r.json()

# Check ALL fields for $
for field in ['content', 'content_full', 'context_before', 'context_after']:
    for i, res in enumerate(d.get('results', [])):
        v = res.get(field, '') or ''
        if '$' in v:
            idx = v.index('$')
            ctx = v[max(0,idx-5):idx+15]
            print('RESULT[%d].%s has $ at pos=%d: ...%s...' % (i, field, idx, ctx))

s = d.get('ai_summary',{}).get('answer','')
if '$' in s:
    idx = s.index('$')
    print('AI_SUMMARY has $ at pos=%d: ...%s...' % (idx, s[max(0,idx-5):idx+15]))

# Check outline
for i, res in enumerate(d.get('results', [])[:1]):
    bid = res.get('book_id','')
    if bid:
        r2 = requests.get('http://localhost:8001/api/v1/knowledge/books/%s/outline' % bid, timeout=5)
        ol = r2.json().get('outline',[])
        for o in ol[:3]:
            t = o.get('title','')
            if '$' in t:
                print('OUTLINE has $:', t[:80])

# Check markdown
for i, res in enumerate(d.get('results', [])[:1]):
    bid = res.get('book_id','')
    if bid:
        r3 = requests.get('http://localhost:8001/api/v1/knowledge/books/%s/markdown' % bid, timeout=5)
        md = r3.json().get('markdown','')
        if '$' in md:
            idx = md.index('$')
            print('MARKDOWN has $ at pos=%d: ...%s...' % (idx, md[max(0,idx-5):idx+15]))

# Check image url
for res in d.get('results', []):
    assoc = res.get('associated_images', [])
    if assoc:
        a = assoc[0]
        url = a.get('url','')
        stored = a.get('stored_url','')
        break
print()
print('assoc url:', url[:60])
print('assoc stored_url:', stored[:60])
print()
print('Done - ALL checks above show any remaining $')
