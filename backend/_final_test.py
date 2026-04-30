"""彻底排查 $...$ 残留和配图问题"""
import requests, json

API = 'http://localhost:8001/api/v1/knowledge'

# 1. Search
r = requests.post(API + '/search',
    json={'query': '起承转合', 'limit': 5}, timeout=15)
d = r.json()
results = d.get('results', [])

# Helper
def find_dollar(obj, path=''):
    """递归查找所有 $ 符号"""
    if isinstance(obj, str):
        if '$' in obj:
            # Show context around first $
            idx = obj.index('$')
            ctx = obj[max(0,idx-10):idx+15]
            return [(path, ctx)]
        return []
    if isinstance(obj, dict):
        found = []
        for k, v in obj.items():
            found.extend(find_dollar(v, path + '.' + k))
        return found
    if isinstance(obj, list):
        found = []
        for i, v in enumerate(obj):
            found.extend(find_dollar(v, path + '[%d]' % i))
        return found
    return []

# 2. Check all results
print('=== RESULTS ===')
for i, res in enumerate(results):
    dollars = find_dollar(res, 'results[%d]' % i)
    if dollars:
        print('result[%d]:' % i)
        for p, ctx in dollars:
            print('  %s: ...%s...' % (p, ctx))
    assoc = res.get('associated_images', [])
    if assoc:
        a = assoc[0]
        url = a.get('url','')
        stored = a.get('stored_url','')
        print('result[%d] assoc url: %s' % (i, url[:80]))
        print('result[%d] assoc stored_url: %s' % (i, stored[:80]))
        # Verify URL works
        if url:
            test_url = url if url.startswith('http') else 'http://localhost:8001' + url
            tr = requests.head(test_url, timeout=3)
            print('  url HEAD: %d' % tr.status_code)
        if stored:
            test_url2 = stored if stored.startswith('http') else 'http://localhost:8001' + stored
            tr2 = requests.head(test_url2, timeout=3)
            print('  stored HEAD: %d' % tr2.status_code)

# 3. Check AI summary
print()
print('=== AI SUMMARY ===')
s = d.get('ai_summary',{})
dollars_ai = find_dollar(s, 'ai_summary')
if dollars_ai:
    for p, ctx in dollars_ai:
        print('  %s: ...%s...' % (p, ctx))
else:
    print('  AI summary clean')

# 4. Check related_images
print()
print('=== RELATED IMAGES ===')
ri = d.get('related_images', [])
for i, r0 in enumerate(ri):
    dollars_ri = find_dollar(r0, 'related_images[%d]' % i)
    for p, ctx in dollars_ri:
        print('  %s: ...%s...' % (p, ctx))
    url = r0.get('url','')
    stored = r0.get('stored_url','')
    print('  [%d] url: %s' % (i, url[:80]))
    print('  [%d] stored_url: %s' % (i, stored[:80]))
    if url:
        test_url = url if url.startswith('http') else 'http://localhost:8001' + url
        tr = requests.head(test_url, timeout=3)
        print('  url HEAD: %d' % tr.status_code)

# 5. Check markdown endpoint for book from first result
print()
print('=== MARKDOWN + OUTLINE ===')
for res in results[:1]:
    bid = res.get('book_id','')
    if bid:
        r2 = requests.get(API + '/books/%s/markdown' % bid, timeout=5)
        md = r2.json().get('markdown','')
        if '$' in md:
            idx = md.index('$')
            print('MARKDOWN has $: ...%s...' % md[max(0,idx-10):idx+15])
        else:
            print('MARKDOWN clean')
        
        r3 = requests.get(API + '/books/%s/outline' % bid, timeout=5)
        ol = r3.json().get('outline',[])
        for o in ol[:5]:
            if '$' in (o.get('title','') or ''):
                print('OUTLINE has $: %s' % (o.get('title','') or '')[:60])

print()
print('=== IMAGE BY UUID ===')
r4 = requests.get('http://localhost:8001/api/v1/knowledge/images/687fe38f-8f0f-4000-b20f-655519c3c04f', timeout=5)
print('Image by UUID:', r4.status_code, 'size:', len(r4.content), 'type:', r4.headers.get('content-type',''))

# Final summary
total_dollars = (len(dollars_ai) + 
    sum(len(find_dollar(r, 'r')) for r in results) +
    sum(len(find_dollar(r0, 'ri')) for r0 in ri))
print()
print('=== FINAL VERDICT ===')
if total_dollars == 0:
    print('ALL CLEAN - NO $ SIGNS ANYWHERE')
else:
    print('STILL HAS $ at %d locations' % total_dollars)
