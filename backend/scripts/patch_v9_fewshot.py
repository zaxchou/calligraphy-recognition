# -*- coding: utf-8 -*-
"""V9 Few-Shot 补丁：max_tokens 4096 + 去 CV 注入 + 追加 few-shot 示例"""
import os

SCRIPT = os.path.join(os.path.dirname(__file__), 'qichengzhuanhe_v9.py')
with open(SCRIPT, 'r', encoding='utf-8') as f:
    c = f.read()

log = []

# 1. max_tokens 2048 -> 4096
c = c.replace('"max_tokens": 2048', '"max_tokens": 4096')
log.append('max_tokens -> 4096')

# 2. Append few-shot before closing """ of V9_PROMPT
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

MARKER = '不可凭经验惯性或构图直觉设定**"""'
c = c.replace(MARKER, '不可凭经验惯性或构图直觉设定**' + FEWSHOT + '"""')
log.append('few-shot appended')

# 3. Remove CV injection block
OLD_CV = '''            cv_result = run_cv_preprocess(img)
            cv_context = cv_result.llm_context

            # 2. 构建 CV 辅助 prompt：将 CV 数据注入 V9_PROMPT
            cv_assisted_prompt = V9_PROMPT
            if cv_context.strip():
                cv_assisted_prompt = (
                    V9_PROMPT
                    + "\\n\\n" + cv_context
                    + "\\n\\n**重要：请严格参考以上 CV 预分析数据来标定坐标。尤其是「起」的位置，必须从 CV 检测的边缘入画点候选中选择，不要凭经验猜测。承/转的坐标应参考画材的精确重心。合的坐标应参考印章位置。**"
                )

            # 3. AI 分析（使用 CV 辅助 prompt）
            b64 = encode_image(img)
            raw = call_qwen_vl(cv_assisted_prompt, b64)'''

NEW_CV = '''            # 直接使用 V9_PROMPT（含 few-shot 示例），不注入 CV 数据
            b64 = encode_image(img)
            raw = call_qwen_vl(V9_PROMPT, b64)'''

if OLD_CV in c:
    c = c.replace(OLD_CV, NEW_CV)
    log.append('CV injection removed')
else:
    log.append('CV injection: already removed or mismatch')

# 4. Remove cv_data block
OLD_DATA = '''                "cv_data": {
                    "major_materials": [
                        {"centroid_pct": list(m.centroid_pct), "edge_proximity": m.edge_proximity,
                         "pixel_ratio": m.pixel_ratio, "edge_distance": m.edge_distance}
                        for m in cv_result.major_materials
                    ],
                    "edge_entries": [
                        {"edge": e.edge, "x": e.x, "y": e.y, "confidence": e.confidence}
                        for e in cv_result.edge_entries
                    ],
                    "seals": [
                        {"x": s.x, "y": s.y, "shape": s.shape}
                        for s in cv_result.seals
                    ],
                    "inscriptions": [
                        {"x": ins.x, "y": ins.y, "width": ins.width, "height": ins.height,
                         "position": ins.position}
                        for ins in cv_result.inscriptions
                    ],
                    "direction": {
                        "angle": cv_result.direction.dominant_angle,
                        "strength": cv_result.direction.dominant_strength,
                        "desc": cv_result.direction.direction_desc,
                    },
                    "dominant_entry": cv_result.edge_density.dominant_entry_edge,
                },'''

if OLD_DATA in c:
    c = c.replace(OLD_DATA, '')
    log.append('cv_data block removed')

# 5. Remove unused import
if 'from app.modules.pantianshou_composition.cv_preprocessor import run_cv_preprocess' in c and 'run_cv_preprocess' not in c.split('V9_PROMPT')[1] if len(c.split('V9_PROMPT')) > 1 else True:
    c = c.replace('from app.modules.pantianshou_composition.cv_preprocessor import run_cv_preprocess\n', '')
    log.append('unused import removed')

with open(SCRIPT, 'w', encoding='utf-8') as f:
    f.write(c)

for l in log:
    print(f'  {l}')
print(f'Done: {SCRIPT}')
