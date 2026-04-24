# -*- coding: utf-8 -*-
"""Phase 2: 将学习结果中的优化 prompt 替换到 V9_PROMPT，追加 few-shot，然后跑测试"""
import os, re, json

SCRIPT = os.path.join(os.path.dirname(__file__), 'qichengzhuanhe_v9.py')

# 1. Read learn result
learn_path = os.path.join(os.path.dirname(__file__), '..', 'training_v9_learn.md')
with open(learn_path, 'r', encoding='utf-8') as f:
    learn_text = f.read()

# 2. Extract optimized prompt (after "### 3.")
idx = learn_text.find('### 3.')
if idx < 0:
    print('ERROR: Cannot find optimized prompt in learn result')
    exit(1)

new_prompt_body = learn_text[idx:].lstrip('### 3. 优化后的 Prompt\n\n').strip()

# 3. Read current script
with open(SCRIPT, 'r', encoding='utf-8') as f:
    content = f.read()

# 4. Find and replace V9_PROMPT = """...""" (including the few-shot we added)
# Pattern: V9_PROMPT = """....""" where the closing """ is after few-shot
start_marker = 'V9_PROMPT = """'
start_idx = content.find(start_marker)
if start_idx < 0:
    print('ERROR: Cannot find V9_PROMPT')
    exit(1)

# Find the matching closing """ - search from after start_marker+4
search_start = start_idx + len(start_marker)
# The closing """ is the LAST """ that closes this string
# Find first """ occurrence after search_start that ends the prompt
# We need to find the next """ that's not part of content
close_idx = content.find('"""', search_start)
if close_idx < 0:
    print('ERROR: Cannot find end of V9_PROMPT')
    exit(1)

old_prompt = content[start_idx:close_idx + 3]
print(f'Old prompt length: {len(old_prompt)} chars')

# 5. Build new prompt with few-shot
FEWSHOT = """

---

**📚 Few-Shot 示例（以下是人工标注的正确范例，请参考其标注逻辑和坐标模式）**

### 示例1：雏鸡+山石图
- 画材：雏鸡、山石
- 起 (85, 45)：山石从右侧入画，起取山石主干与右边缘交汇处
- 承 (70, 35)：雏鸡躯干面积中心，从起向上生长，欧氏距离≈18%<30%
- 转 (30, 60)：视线从承转向左下方，方向突变>45°，山石区域视觉焦点
- 合 (10, 20)：收束于左上角印章区域，转→合向量与起→承向量形成闭环
- 路径：S形

### 示例2：蒲扇图
- 画材：蒲扇
- 起 (85, 95)：蒲扇柄从右下角入画，起取柄基座与底部边缘交汇处
- 承 (70, 70)：蒲扇主体面积中心，从起向上微偏左，距离≈28%<30%
- 转 (35, 45)：花茎分叉处，方向突变>45°，墨色最浓的视觉张力峰值
- 合 (80, 15)：收束于右上题跋区域，转→合向量与起→承向量形成几何闭环
- 路径：S形

**请参考以上示例的标注风格：起在边缘的画材入画点、承在画材面积中心、转在方向突变处、合在题跋/印章视觉重心。**"""

new_prompt = f'V9_PROMPT = """{new_prompt_body}{FEWSHOT}"""'
print(f'New prompt length: {len(new_prompt)} chars')

# 6. Replace
content = content.replace(old_prompt, new_prompt)

with open(SCRIPT, 'w', encoding='utf-8') as f:
    f.write(content)

print('V9_PROMPT updated with Phase 2 optimized prompt + few-shot')
print(f'Updated: {SCRIPT}')
