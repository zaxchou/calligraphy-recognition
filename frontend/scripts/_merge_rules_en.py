# 把规则引擎模板短语（值查词典）合入 en.js —— 只追加 en.js 尚不存在的键
import io, json, re

pairs = json.load(io.open('scripts/rules-en.json', encoding='utf-8'))
en_src = io.open('src/locales/en.js', encoding='utf-8').read()
existing = set(re.findall(r"'((?:[^'\\]|\\.)+)'\s*:", en_src))

q = lambda s: s.replace('\\', '\\\\').replace("'", "\\'")
block, skipped = [], 0
for zh, en in pairs.items():
    if zh in existing:
        skipped += 1
        continue
    block.append(f"  '{q(zh)}': '{q(en)}',")
    existing.add(zh)

i = en_src.rstrip().rfind('}')
out = en_src[:i] + '  // === rule-engine canned phrases (translateContent 值查词典) ===\n' + '\n'.join(block) + '\n' + en_src[i:]
io.open('src/locales/en.js', 'w', encoding='utf-8', newline='').write(out)
print(f'appended {len(block)}, skipped(existing) {skipped}')
