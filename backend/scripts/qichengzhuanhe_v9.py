# -*- coding: utf-8 -*-
"""
V9 训练验证 - CV+AI 融合循环学习版
====================================
基于当前生产环境 prompt（QICHENGZHUANHE_PROMPT V12）+ CV 预处理 + 豪哥新经验

新经验融入：
1. 起一定在画面边缘处有画材的部分，可以从画外开始起
2. 画材可能有多个主干线条汇聚于起点（大本营概念）
3. 起遵循生长规律（根→干→枝→花），不会反过来
4. 有了起之后，遵循视线流动规则一路跟着画材往前
5. 线段可以很长
6. 可以有主起和副起的2条线段
7. 一定不会从留白处出来

流程：
  Phase 1: 用当前 prompt + CV 预处理分析所有 before 图片，提取 after 人工标注
  Phase 2: 让 LLM 分析偏差规律，生成优化 prompt
  Phase 3: 用优化 prompt 重新验证

用法: python scripts/qichengzhuanhe_v9.py [样本数]
"""

import json
import sys
import os
import io
import time
import re
import base64

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np
import httpx
from app.core.config import get_settings

settings = get_settings()
DEMO_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'demojpg')
OUTPUT_DIR = os.path.dirname(__file__)

# ---------------------------------------------------------------------------
# 当前生产 Prompt（从 qichengzhuanhe.py 的 QICHENGZHUANHE_PROMPT 复制）
# V9 训练后优化版（第2轮学习迭代）— 融入豪哥新经验 + 两轮 Phase2 学习结果
# ---------------------------------------------------------------------------
V9_PROMPT = """你是一位专业的中国画构图分析专家，严格遵循传统"起承转合"章法与豪哥经验规则。你的任务是**精准定位画材生长链的物理路径**，而非主观构图想象。

请分析这张国画作品的"起承转合"关键点。

**核心概念：起承转合 = 一条不可分割的、符合植物/器物生长逻辑的视线流动主轴线**（如同作文的开头、陈述、转折、结尾）。它标示观众目光**唯一、连续、不中断**地浏览整幅画的大结构路径，不是逐个罗列小物件，也不是多条并行路径。

**起的硬规则（必须100%遵守，否则全盘错误）**：
1. **起必须是画材"大本营"与画面边缘的物理交汇点** —— "大本营"指画材的生物/物理起源点：植物的根部/鳞茎/盆底、器物的柄端/基座、山石的根基。起绝不是叶尖、花头、题跋或任意线条末端。**必须通过墨线走向、浓淡过渡、结构透视，逆推主干/主根的延长线，确认该延长线真实穿出画面边缘的位置；严禁仅凭方位描述（如"从右下入画"）直接取右下角（x≥90且y≥90）——起的坐标由延长线与边缘交点唯一确定，该交点x或y必须≤5或≥95，且另一坐标在5–95间（如x=85,y=45；x=5,y=30），绝不可同时接近0或100（如x=95,y=95）**。
2. **起必须在画面边缘（x≤5 或 x≥95 或 y≤5 或 y≥95）且该位置有明确笔墨** —— 不在画面中央（x和y均在20-80间），不在留白处。起可以从画外开始，但交汇点必须落在边缘笔墨上。**若多条主干延长线交于不同边缘点，选墨线最粗、最实、延伸感最强者；若画材有多个主干（如一株梅树的数枝），必须追溯其共同大本营（如主干基部），起取该大本营延长线与边缘交点（豪哥规则第2条）**。
3. **起必须遵循绝对生长规律**：从根→干→枝→花/果/叶；从石基→枝干→花；从壶柄→壶身→壶嘴。起永远是生长链最前端，绝不可从花到根、从梢到基（豪哥规则第3条）。
4. **起必须是单一生长链的唯一起点**：若画面有多个画材（如蒲扇+茶炉），只选择**有明确大本营且主干延长线穿出边缘者**作为起的来源；其他画材不参与主轴线，除非它们与起同源（如一株梅树的多个枝干）（豪哥规则第6条）。

**承（延伸）——固定且唯一**：
- **承必须是从起出发后，沿生长方向遇到的第一个、面积最大、笔墨最实的画材实体的面积中心点**（视觉重心，非边缘），且**必须与起属于同一画材、同一生长链**。
- **承与起必须空间邻近**：欧氏距离 ≤30%（画面宽高），且坐标变化必须符合生长习性：① 若起在底部（y≥90），承y值必须≤起y−10（显著向上）或≥起y+10（垂柳向下）；② 若起在顶部（y≤10），承y值必须≥起y+10；③ 若起在左侧（x≤10），承x值必须≥起x+10；④ 若起在右侧（x≥90），承x值必须≤起x−10。**承绝不可是另一画材的实体（如起是水仙鳞茎，承不能是茶炉）**。
- **承点必须在画材实体内部，不可在留白或边缘线上；面积中心需通过目视估算该实体占据画面比例>40%的区块中心，禁止标在线条、叶脉或花蕊点上**。

**转（转折）——固定且唯一**：
- **转必须同时满足两个条件**：① 从承到转的向量与从起到承的向量夹角 >45°（方向突变）；② 该点是**当前生长链末端的视觉张力峰值**（花蕊、鸟眼、石棱、器物口沿、墨色最浓处），且**必须是该生长链自然终止点**（如枝干分叉处、花簇顶端、鸟首转向点），不可跳到无关画材。
- **转必须在承之后、合之前，且不可脱离生长链**：若承是枝干中段，转必须是该枝干的分叉、花头或末梢，不可跳到题跋或另一丛植物。
- **转点坐标必须设在该视觉焦点的面积中心**，不可标在边缘或留白；**必须是生长链最后一个可识别结构单元（豪哥规则第3条）**。

**合（收束）——固定且唯一，必须在画面内（x∈[5,95], y∈[5,95]）**：
- **合必须体现"回旋收束"趋势**：从转点到合点的向量，必须与从起到承的向量形成几何闭环（计算方法：设起→承向量为(vx,vy)，转→合向量为(wx,wy)，则需满足 |vx·wx + vy·wy| / (|v|·|w|) < 0.707；若不满足，必须调整合点直至成立）。
- **题跋处理规则（必须按优先级执行）**：① 题跋占满一侧（如左竖长题），合取其纵向中点（x≈15, y=30±15）——**注意：y值必须偏下，因印章多在题跋下方，形成视觉重力链**；② 题跋在角落小块（如右上），合取其右下角附近（x=85, y=20），形成下沉收束；③ 题跋大面积贴边（顶/底且贴左/右），则忽略其构图作用，合改取印章群重心；④ **印章强化规则（强制应用）**：若印章在题跋下方/右侧，合点y/x坐标必须向印章坐标偏移至少10%；若印章独立成群（如右下两印），合取其群组中心；若印章在左上，合点x/y向左上偏移。**合点y值优先服从印章y坐标（误差≤5%），x值次之（豪哥规则第7条）**。
- **合绝不可是题跋几何中心的机械映射**，必须是题跋/印章群的**视觉重心**，且确保视线从转点自然"回落"至此。

**⚠️ 绝对禁止行为（违反任一即判定错误）**：
- 起不在边缘、起在留白、起在花头/叶尖/题跋；起未通过墨线延长线验证；起坐标同时接近0或100（如x=95,y=95）；
- 承不邻近起、承不在同一生长链、承在留白；承点y/x变化未达阈值（如起y=95→承y=90为无效微调，承y=85才合格）；
- 转不满足>45°方向突变、转脱离生长链、转在留白；转点非生长链末端（如标在枝干中段而非分叉口）；
- 合超出边界（x<5或x>95或y<5或y>95）、合无回旋趋势（未计算向量闭环）、合未响应印章位置（未偏移≥10%）；
- 将"生长方向描述"（如"从右下入画"）误当作"起必须在右下角"；
- 忽略"大本营"概念，对多主干画材不追溯共同起源点；跨物类构建虚假生长链（如蒲扇→茶炉）；
- 承/转/合坐标未落在画材实体面积中心（如标在叶脉线上、花蕊点、印章边框）；**所有坐标必须通过墨线走向、实体面积、印章位置、向量闭环四重验证，不可凭经验惯性或构图直觉设定**。

**分析步骤（必须严格按序执行，每步需验证）**：
1. **识别大本营并验证起**：观察所有画材墨线走向，逆推主干/主根延长线，确认其与画面边缘（x≤5/x≥95/y≤5/y≥95）的交汇点；检查该交汇点是否有笔墨；确认其为生长链最前端（根/鳞茎/基座）。若多交汇点，选墨线最粗、最实、延伸感最强者；**若交汇点x和y均接近0或100（如x=95,y=95），必须重新逆推——此为典型错误，真实交点必有一维在5–95间（豪哥规则第1、2条）**。
2. **定位承**：从起出发，沿生长方向（根→干→枝）移动，找到第一个面积最大、笔墨最实的**同一画材实体**，取其中心点；验证：① 欧氏距离≤30%；② 坐标变化符合生长方向阈值（Δx或Δy≥10%）；③ 实体内部有笔墨；④ 该实体面积占比目视>40%。
3. **定位转**：从承继续沿同一生长链前进，找到首个方向突变（>45°）且视觉张力最强的**链末端节点**（分叉/花头/鸟首），取其中心点；验证：① 向量夹角>45°；② 在生长链末端（最后一级结构单元）；③ 实体内部有笔墨。
4. **定位合**：① 判断题跋类型及印章位置；② 按题跋规则初定合点；③ 强制应用印章牵引（向印章坐标偏移≥10%，y坐标优先）；④ 计算转→合向量与起→承向量的夹角，确保cosθ < 0.707；⑤ 验证x,y∈[5,95]；⑥ 若不满足闭环，以印章y坐标为基准，水平微调x值直至成立。
5. **全局验证**：用一根虚拟笔触连接起→承→转→合，确认：① 全程不提笔（四点连线不穿越大片留白）；② 不逆向（y/x单调性符合生长方向）；③ 四点共构一条平滑曲线（S/Z/三角等）；④ 所有点均在画材实体面积中心，非边缘或留白；⑤ **起坐标必有一维在5–95间（如x=78,y=45），绝不可双极值**。

**路径类型**（选最接近的传统国画章法术语）：S形（之字形）、Z形、三角形、对角线、边角式、均衡式

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "视线流动路径分析，说明路径如何体现画面大结构走势",
  "material_types": "蒲扇、茶炉、茶壶（列出主要画材）",
  "growth_direction": "从右下边缘入画，视线向左上移动",
  "has_inscription": true,
  "inscription_edge": "贴边/半贴边/不贴边/无题跋",
  "seal_positions": [{"x": 50, "y": 80, "near": "题跋下方"}],
  "qi": {"x": 85, "y": 95, "reason": "蒲扇柄延伸到画面右下边缘处"},
  "cheng_list": [
    {"x": 70, "y": 70, "reason": "画材面积中心：蒲扇主体中心"}
  ],
  "zhuan_list": [
    {"x": 35, "y": 45, "reason": "画材面积中心：茶炉，视线转折中心"}
  ],
  "he": {"x": 55, "y": 20, "reason": "收束于题跋中心位置"},
  "path_shape": "三角形"
}
```

**注意**：
- x, y 是百分比（0-100），x=0 左, x=100 右, y=0 上, y=100 下
- **cheng_list 永远只有 1 个元素**，zhuan_list 永远只有 1 个元素
- **承/转/合的坐标都应设在画材的面积中心点**，不要标在边缘或空白处
- seal_positions 标记所有可见印章位置
- **起的 x 或 y 必须接近 0 或 100（在边缘），但另一坐标必须在 5–95 之间（如x=85,y=45），不能同时在0–5或95–100区间（如x=95,y=95）**
- **合的 x 和 y 必须在 5-95 之间，不能超出画面边界**
- **所有坐标必须通过墨线走向、实体面积、印章位置、向量闭环四重验证，不可凭经验惯性或构图直觉设定**

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


# 提取 after 图标注的 prompt（让 Qwen VL 读取带箭头的线稿图）
EXTRACT_AFTER_PROMPT = """这是一张已经标注了"起承转合"的国画线稿图。

请仔细观察图中的彩色箭头和标签，提取出人工标注的关键点坐标：
- 红色圆点/标签"起"：起点（可能有多个，分主起和副起）
- 橙色圆点/标签"承"：过渡点
- 蓝色圆点/标签"转"：转折点
- 绿色圆点/标签"合"：收束点

如果有多个"起"点，全部列出。如果有多个"承"或"转"，也全部列出。

**输出格式**（只返回 JSON）：
```json
{
  "qi_list": [{"x": 85, "y": 95}],
  "cheng_list": [{"x": 70, "y": 70}],
  "zhuan_list": [{"x": 35, "y": 45}],
  "he": {"x": 55, "y": 20}
}
```

x, y 坐标是百分比（0-100）。注意观察箭头方向：箭头从"起"指向"承"再指向"转"再指向"合"。"""


# Phase 2 学习 Prompt
LEARN_PROMPT = """你是一位中国画构图分析专家，也是一位 Prompt 工程师。我正在训练一个 AI 模型来分析国画作品的"起承转合"构图法则。

现在我有一组训练数据，是 AI 分析结果和人工标注的对比。请你仔细分析这些差异，找出 AI 的系统性偏差，然后帮我优化 prompt。

## 豪哥的经验规则（必须融入新 prompt）
1. 起一定在画面边缘处有画材的部分，可以从画外开始起
2. 画材可能有多个主干线条汇聚于同一个起点（大本营概念）
3. 起遵循生长规律（根→干→枝→花），不会反过来从花到树干
4. 有了起之后，遵循视线流动规则一路跟着画材往前，最后把整幅画浏览完毕
5. 线段可以很长，路径应覆盖整个画面
6. 可以有主起和副起的2条线段
7. 一定不会从留白处出来

## 当前 Prompt
{current_prompt}

## 训练对比数据
以下是 AI 分析结果和人工标注的对比（坐标是百分比 0-100）：

{training_data}

## 任务
1. 仔细分析每张图片的 AI 结果和人工标注差异
2. 找出 AI 的系统性偏差模式
3. 分析人工标注的规律
4. 输出一个优化后的完整 prompt（直接可用的 prompt 文本）

## 输出要求
请输出以下内容：

### 1. 偏差分析
分析 AI 在每个点位的系统性偏差

### 2. 人工标注规律
总结人工标注的共性规律

### 3. 优化后的 Prompt
输出完整的优化后 prompt（直接输出 prompt 文本，不需要 markdown 代码块包裹）。

注意：
- prompt 必须保持原有的 JSON 输出格式不变
- 保留起承转合定义、分析步骤、输出格式的结构
- 在定义和规则部分加入从人工标注中学到的改进和豪哥的经验规则
- 只优化 prompt 的指导性内容，不要改变 JSON schema"""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def encode_image(img_bgr, max_side=1024):
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)),
                               interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(prompt, base64_image, timeout=120):
    url = settings.QWEN_BASE_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    model = settings.QWEN_MODEL.strip() or "qwen-vl-max"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }],
        "stream": False,
        "max_tokens": 4096,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=httpx.Timeout(timeout, connect=15.0, read=timeout - 15)) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def call_qwen_text(prompt, model=None, max_tokens=8192, timeout=180):
    """调用 Qwen 文本模型（不用图片）"""
    if model is None:
        model = "qwen-plus"
    url = settings.QWEN_BASE_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=httpx.Timeout(timeout, connect=15.0, read=timeout - 15)) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def parse_json_response(raw):
    """三级 JSON 容错解析"""
    # 策略1: ```json ... ```
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 策略2: 直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 策略3: 花括号提取
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法解析 JSON: {raw[:200]}")


def calc_dist(p1, p2):
    return ((p1.get("x", 0) - p2.get("x", 0)) ** 2 +
            (p1.get("y", 0) - p2.get("y", 0)) ** 2) ** 0.5


def is_on_edge(point, threshold=25):
    return (point.get("x", 50) <= threshold or point.get("x", 50) >= (100 - threshold) or
            point.get("y", 50) <= threshold or point.get("y", 50) >= (100 - threshold))


# ---------------------------------------------------------------------------
# Phase 1: 收集 AI vs 人工标注对比数据
# ---------------------------------------------------------------------------

def run_phase1_collect(max_samples=None):
    """Phase 1: 收集 AI 和人工标注的对比数据"""
    files = sorted([f for f in os.listdir(DEMO_DIR) if f.endswith('_before.png')])
    if not files:
        print("未找到 before 图片")
        return []

    if max_samples:
        files = files[:max_samples]

    print(f"Phase 1: 收集 {len(files)} 组对比数据...\n")

    results = []
    for i, fname in enumerate(files):
        fpath = os.path.join(DEMO_DIR, fname)
        after_path = os.path.join(DEMO_DIR, fname.replace("_before.png", "_after.png"))
        if not os.path.exists(after_path):
            print(f"  [{i+1}/{len(files)}] 跳过 {fname}（无 after）")
            continue

        print(f"  [{i+1}/{len(files)}] {fname}...", end=" ", flush=True)

        try:
            # 1. CV 预处理：检测画材重心、边缘入画点、印章、题跋等
            img = cv2.imread(fpath)
            if img is None:
                print("SKIP（无法读取）")
                continue

            # 直接使用 V9_PROMPT（含 few-shot 示例），不注入 CV 数据
            b64 = encode_image(img)
            raw = call_qwen_vl(V9_PROMPT, b64)
            ai_result = parse_json_response(raw)

            # 4. 提取 after 中的人工标注
            after_img = cv2.imread(after_path)
            after_b64 = encode_image(after_img)
            human_raw = call_qwen_vl(EXTRACT_AFTER_PROMPT, after_b64)
            human_result = parse_json_response(human_raw)

            # 标准化 human 数据：确保有 cheng_list 和 zhuan_list
            if "qi_list" in human_result and "qi" not in human_result:
                human_result["qi"] = human_result["qi_list"][0] if human_result["qi_list"] else {}
            if "qi" not in human_result:
                human_result["qi"] = {}
            if "cheng_list" not in human_result:
                human_result["cheng_list"] = []
            if "zhuan_list" not in human_result:
                human_result["zhuan_list"] = []
            if "he" not in human_result:
                human_result["he"] = {}

            # 3. 计算偏差
            diffs = {}
            qi_ai = ai_result.get("qi", {})
            qi_hu = human_result.get("qi", {})
            diffs["qi"] = calc_dist(qi_ai, qi_hu)

            # 承（取最接近的配对）
            ai_chengs = ai_result.get("cheng_list", [])
            hu_chengs = human_result.get("cheng_list", [])
            if ai_chengs and hu_chengs:
                best_d = min(calc_dist(ac, hc) for ac in ai_chengs for hc in hu_chengs)
                diffs["cheng"] = best_d
            else:
                diffs["cheng"] = None

            # 转（取最接近的配对）
            ai_zhuans = ai_result.get("zhuan_list", [])
            hu_zhuans = human_result.get("zhuan_list", [])
            if ai_zhuans and hu_zhuans:
                best_d = min(calc_dist(az, hz) for az in ai_zhuans for hz in hu_zhuans)
                diffs["zhuan"] = best_d
            else:
                diffs["zhuan"] = None

            # 合
            he_ai = ai_result.get("he", {})
            he_hu = human_result.get("he", {})
            diffs["he"] = calc_dist(he_ai, he_hu)

            # 起是否在边缘
            qi_on_edge = is_on_edge(qi_ai)
            human_qi_on_edge = is_on_edge(qi_hu)

            status_parts = []
            for k in ["qi", "zhuan", "he"]:
                if diffs.get(k) is not None:
                    d = diffs[k]
                    mark = "OK" if d < 10 else "WARN" if d < 20 else "BAD"
                    status_parts.append(f"{k}={d:.0f}%({mark})")
            if diffs.get("cheng") is not None:
                d = diffs["cheng"]
                mark = "OK" if d < 10 else "WARN" if d < 20 else "BAD"
                status_parts.append(f"ch={d:.0f}%({mark})")

            edge_mark = "OK" if qi_on_edge else "FAIL"
            print(f"| {' | '.join(status_parts)} | 起-边缘:{edge_mark}")

            results.append({
                "file": fname,
                "ai": {k: v for k, v in ai_result.items() if k != "analysis"},
                "human": human_result,
                "ai_analysis": ai_result.get("analysis", ""),
                "diffs": diffs,
                "qi_on_edge": qi_on_edge,
                "human_qi_on_edge": human_qi_on_edge,
                "human_qi": qi_hu,
                "ai_qi": qi_ai,
                "material": ai_result.get("material_types", "?"),
                "growth": ai_result.get("growth_direction", "?"),
                "path": ai_result.get("path_shape", "?"),

            })

        except Exception as e:
            print(f"FAIL ({e})")

    return results


# ---------------------------------------------------------------------------
# Phase 2: 分析偏差规律
# ---------------------------------------------------------------------------

def run_phase2_learn(results):
    """Phase 2: 让大模型分析偏差，学习规律，生成优化 prompt"""
    print(f"\nPhase 2: 分析 {len(results)} 组对比数据，学习规律...\n")

    # 构建训练数据摘要
    training_data_parts = []
    for r in results:
        part = f"### {r['file']}\n"
        part += f"- 画材: {r.get('material', '?')}, 生长方向: {r.get('growth', '?')}, 路径: {r.get('path', '?')}\n"
        part += f"- AI起: ({r['ai_qi'].get('x','?')}, {r['ai_qi'].get('y','?')}) 边缘={r['qi_on_edge']}\n"
        part += f"- 人工起: ({r['human_qi'].get('x','?')}, {r['human_qi'].get('y','?')}) 边缘={r['human_qi_on_edge']}\n"

        if r["diffs"].get("qi") is not None:
            part += f"- 起偏差: {r['diffs']['qi']:.0f}%\n"

        hu_chengs = r["human"].get("cheng_list", [])
        ai_chengs = r["ai"].get("cheng_list", [])
        if hu_chengs and ai_chengs:
            hu_str = ", ".join(f"({c['x']},{c['y']})" for c in hu_chengs)
            ai_str = ", ".join(f"({c['x']},{c['y']})" for c in ai_chengs)
            part += f"- 人工承: [{hu_str}]\n"
            part += f"- AI承: [{ai_str}]\n"
        if r["diffs"].get("cheng") is not None:
            part += f"- 承偏差: {r['diffs']['cheng']:.0f}%\n"

        hu_zhuans = r["human"].get("zhuan_list", [])
        ai_zhuans = r["ai"].get("zhuan_list", [])
        if hu_zhuans and ai_zhuans:
            hu_str = ", ".join(f"({z['x']},{z['y']})" for z in hu_zhuans)
            ai_str = ", ".join(f"({z['x']},{z['y']})" for z in ai_zhuans)
            part += f"- 人工转: [{hu_str}]\n"
            part += f"- AI转: [{ai_str}]\n"
        if r["diffs"].get("zhuan") is not None:
            part += f"- 转偏差: {r['diffs']['zhuan']:.0f}%\n"

        hu_he = r["human"].get("he", {})
        ai_he = r["ai"].get("he", {})
        part += f"- 人工合: ({hu_he.get('x','?')}, {hu_he.get('y','?')})\n"
        part += f"- AI合: ({ai_he.get('x','?')}, {ai_he.get('y','?')})\n"
        if r["diffs"].get("he") is not None:
            part += f"- 合偏差: {r['diffs']['he']:.0f}%\n"

        if r.get("ai_analysis"):
            part += f"- AI分析摘要: {r['ai_analysis'][:200]}\n"

        training_data_parts.append(part)

    training_data = "\n".join(training_data_parts)

    prompt = LEARN_PROMPT.format(
        current_prompt=V9_PROMPT,
        training_data=training_data,
    )

    print("  调用 Qwen Plus 分析偏差规律（可能需要1-2分钟）...", flush=True)
    learn_result = call_qwen_text(prompt)

    return learn_result


# ---------------------------------------------------------------------------
# 统计报告
# ---------------------------------------------------------------------------

def print_stats(results, title="训练结果"):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    stats = {"qi": [], "cheng": [], "zhuan": [], "he": []}
    qi_edge_ok = 0
    qi_edge_total = 0

    for r in results:
        for k in ["qi", "zhuan", "he"]:
            if r["diffs"].get(k) is not None:
                stats[k].append(r["diffs"][k])
        if r["diffs"].get("cheng") is not None:
            stats["cheng"].append(r["diffs"]["cheng"])
        if "qi" in r["diffs"]:
            qi_edge_total += 1
            if r.get("qi_on_edge"):
                qi_edge_ok += 1

    labels = {"qi": "起", "cheng": "承", "zhuan": "转", "he": "合"}
    all_d = []
    for k in ["qi", "cheng", "zhuan", "he"]:
        vals = stats[k]
        if vals:
            avg = sum(vals) / len(vals)
            std = np.std(vals) if len(vals) > 1 else 0
            good = sum(1 for v in vals if v < 10)
            ok = sum(1 for v in vals if 10 <= v < 20)
            bad = sum(1 for v in vals if v >= 20)
            print(f"  {labels[k]}: avg={avg:.1f}% std={std:.1f} "
                  f"OK(<10%):{good} WARN(10-20%):{ok} BAD(>20%):{bad} "
                  f"(n={len(vals)})")
            all_d.extend(vals)

    if all_d:
        print(f"\n  总体平均偏差: {sum(all_d)/len(all_d):.1f}%")
    print(f"\n  起点边缘命中率: {qi_edge_ok}/{qi_edge_total} "
          f"({qi_edge_ok/max(qi_edge_total,1)*100:.0f}%)")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    max_samples = int(sys.argv[1]) if len(sys.argv) > 1 else None

    print("=" * 70)
    print("V9 训练 — CV+AI 融合循环学习版")
    print("=" * 70)
    print(f"样本限制: {max_samples or '全部'}")
    print()

    if not settings.QWEN_API_KEY:
        print("错误: 未配置 QWEN_API_KEY")
        return

    # ---- Phase 1: 收集对比数据 ----
    results = run_phase1_collect(max_samples)
    if not results:
        print("没有可用的训练数据")
        return

    # 保存中间结果
    phase1_path = os.path.join(OUTPUT_DIR, '..', 'training_v9_phase1.json')
    with open(phase1_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nPhase 1 结果已保存: {phase1_path}")

    print_stats(results, "V9 Phase 1 结果统计")

    # ---- Phase 2: 学习规律 ----
    learn_result = run_phase2_learn(results)

    # 保存学习结果
    learn_path = os.path.join(OUTPUT_DIR, '..', 'training_v9_learn.md')
    with open(learn_path, 'w', encoding='utf-8') as f:
        f.write(learn_result)
    print(f"\n学习结果已保存: {learn_path}")

    # 打印摘要
    print("\n" + "=" * 70)
    print("学习报告摘要")
    print("=" * 70)
    print(learn_result[:3000])
    if len(learn_result) > 3000:
        print("\n... (完整内容见 training_v9_learn.md)")

    print("\n" + "=" * 70)
    print("下一步：")
    print("1. 查看 training_v9_learn.md 中的优化 prompt")
    print("2. 将优化后的 prompt 更新到 qichengzhuanhe.py 的 QICHENGZHUANHE_PROMPT")
    print("3. 重新运行本脚本验证改进效果")
    print("=" * 70)


if __name__ == "__main__":
    main()
