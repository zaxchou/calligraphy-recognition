#!/usr/bin/env python3
"""Remove ECharts theme chart code from TubiDetail.vue"""
import re

path = r'Z:\molin-wiki\frontend\src\views\TubiDetail.vue'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove updateThemeChart() from setTimeout
content = content.replace(
    'setTimeout(() => { updatePieChart(); updateThemeChart() }, 300)',
    'setTimeout(() => { updatePieChart() }, 300)'
)

# 2. Remove the entire updateThemeChart function + its watch
# Find the function definition and watch block
start = content.find('// ── 主题柱状图')
if start >= 0:
    # Find the end - after the watch block
    end_marker = '}, { deep: true, immediate: true })'
    end = content.find(end_marker, start)
    if end >= 0:
        end += len(end_marker)
        # Cut from start to end+1 (the newline after)
        while end < len(content) and content[end] in '\r\n':
            end += 1
        content = content[:start] + content[end:]
        print(f'Removed function block at {start}-{end}')
    else:
        print('Could not find end of watch block')
else:
    print('Could not find function start')

# 3. Remove themeChart?.resize()
content = content.replace(
    '  pieChart?.resize()\n  themeChart?.resize()',
    '  pieChart?.resize()'
)

# 4. Remove themeChart?.dispose()
content = content.replace(
    '  pieChart?.dispose()\n  themeChart?.dispose()',
    '  pieChart?.dispose()'
)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print('Done')
