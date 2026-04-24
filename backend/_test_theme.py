import sys
sys.path.insert(0, '.')
from reclassify_themes import classify_with_llm

tests = [
    '一路榮華。李鱓',
    '写此以纪其胜。雍正十一年春月，懊道人。',
    '民苦耕作官租重，叹息年年为底忙。可笑老夫闲不住，又来纸上写凄凉。',
    '笔精墨妙气韵生动，聊写胸中逸气耳。',
    '乾隆二十年为慎庵先生写，时年七十又一。',
]
for t in tests:
    r = classify_with_llm(t)
    theme_str = '/'.join([f"{tt['name']}({tt['confidence']})" for tt in r['themes']])
    print(f"题跋: {t}")
    print(f"  → {theme_str}")
    print(f"  推理: {r.get('reasoning','')}")
    print()
