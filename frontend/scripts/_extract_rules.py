# 提取后端分析规则里的模板中文，对照 zh.js 已有词条，输出缺失清单
import io, re, json

src = io.open('../backend/app/services/tibi_analysis_rules.py', encoding='utf-8').read()
# 抓所有含中文的字符串字面量（单/双引号）
lits = set()
for m in re.findall(r'"([^"\n]*[\u4e00-\u9fff][^"\n]*)"', src):
    lits.add(m)
for m in re.findall(r"'([^'\n]*[\u4e00-\u9fff][^'\n]*)'", src):
    lits.add(m)
lits = {l.strip() for l in lits if len(l.strip()) >= 2}

zh_src = io.open('src/locales/zh.js', encoding='utf-8').read()
zh_dict = dict(re.findall(r"'((?:[^'\\]|\\.)+)'\s*:\s*'((?:[^'\\]|\\.)*)'", zh_src))
zh_values = set(zh_dict.values())

missing = sorted(l for l in lits if l not in zh_values)
print('规则文件中文串:', len(lits), '| 已覆盖:', len(lits) - len(missing), '| 缺失:', len(missing))
json.dump(missing, io.open('scripts/missing-rules-zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for m in missing:
    print(m)
