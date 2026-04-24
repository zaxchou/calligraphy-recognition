"""
起承转合 Prompt 学习 v3 — 精准微调版
======================================
策略：用当前 prompt 为基础，从人工标注中学习具体修正规则，做精准微调。
"""

import base64
import cv2
import httpx
import json
import re
import sys
import io
from pathlib import Path
from typing import Dict, List, Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.config import get_settings
import numpy as np

settings = get_settings()
DEMO_DIR = Path(__file__).parent.parent.parent / "demojpg"

# 原始 prompt（作为基础框架）
BASE_PROMPT = """你是一位专业的中国画构图分析专家，精通潘天寿的构图理论和"起承转合"法则。

请分析这张国画作品，找出"起承转合"四个关键点的位置。

**起承转合定义**：
- **起**：画面的起点，墨迹的起始位置，通常在画面边缘（左下/右下/右上/左上），是视觉引导的入口
- **承**：从起自然延伸的过渡点，沿主体枝干/线条分布，引导视线向上推进
- **转**：方向转折的关键点，情节高潮（花朵/鸟雀/主体元素），通常在画面中上部
- **合**：画面的收束点，**必须靠近题款/印章区域**。从"转"出发，视线应往下、往题跋方向回转，形成一个近似闭合的环形路径

**合点定位原则（非常重要）**：
1. 仔细观察画面中的题款（竖排文字）和印章（红色方形/圆形），合点应紧邻这些区域
2. 合的 y 坐标通常偏上（画面上部1/3区域），因为中国画题款多在画面上方
3. 如果题款在画面右侧，合应偏向右侧；题款在左侧则偏左
4. 合点与转点之间应形成回转趋势（类似闭合环），不要让合和转在同一方向
5. 即使没有明显题款，合也应选在画面与"起"对角的边缘位置

**分析步骤**：
1. 先识别画面主体（竹子/花/鸟等）的走势
2. 找出墨迹的起始点（起）
3. 沿主体找出过渡点（承）
4. 找出主体转折或焦点位置（转）
5. **仔细寻找题款/印章位置**，将合点放在题款附近，与转点形成回转闭合趋势

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "简要分析画面主体的走势和起承转合的分布理由，特别是合点为何在题款附近",
  "qi": {"x": 50, "y": 80, "reason": "起在左下角竹枝根部"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "承沿竹枝向上延伸"}],
  "zhuan": {"x": 55, "y": 30, "reason": "转在竹叶密集处"},
  "he": {"x": 80, "y": 20, "reason": "合在右上角题款旁，与转形成回转"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 坐标是百分比（0-100），x=0 左边, x=100 右边, y=0 上边, y=100 下边
- cheng_list 是数组，可以有1-3个承点
- 起承转合必须**沿着画面主体**分布
- **合必须靠近题款/印章**，与转形成回转闭合趋势
- path_shape 可选：S形、上升式、下降式、弧线、闭环"""


# V3 微调版 — 在原始基础上做最小改动
V3_PROMPT = """你是一位专业的中国画构图分析专家，精通潘天寿的构图理论和"起承转合"法则。

请分析这张国画作品，找出"起承转合"四个关键点的位置。

**核心原则：起承转合是一次书写性运动轨迹的自然四段解析。**
画家如何落笔、行笔、顿转、收笔——你就要如何分析。不要预设固定位置。

**起承转合定义**：
- **起**：画家笔锋**首次接触画面的物理落笔点**。仔细观察墨迹：哪里的墨色最浓、线条最粗重、有枯笔飞白源头？那里就是起。起可以在画面**任何位置**（包括右上、左上、右下），绝不默认左下角。判断方法：追踪画面主体（枝干/花茎/石脉）的起始端。
- **承**：从起沿主体走势延伸后的**第一个重要转折处**。承是起与转之间的过渡枢纽，通常只有1个。它是墨线走势开始变化的位置（如直线变弧线、粗变细、浓变淡）。
- **转**：画面**视觉高潮所在的主体结构中心**。转必须精确落在主体元素上（如花朵中心、鸟的身体中心、竹叶簇生点），而不是旁边的空白或次要元素。转通常在画面中间区域（x=30-70, y=25-55），但以主体实际位置为准。
- **合**：**题款和印章附近的收束点**。找到题款文字区域和红色印章，合应紧贴它们。关键是：合→起的方向应该和承→转的方向形成**弯曲回环**（类似字母 S 或 C 的弧度），不要让四个点排成直线或折线。

**分析步骤**：
1. 先识别画面主体（竹/花/鸟/石等）的完整走势，从起点到终点
2. **不要假设左下角是起**！仔细观察墨迹源头，找到真正最先落笔的位置
3. 沿主体走势找第一个转折处作为承
4. 找到主体视觉高潮的中心位置作为转（必须在主体上）
5. 找到题款/印章，将合放在附近，确保四点能形成弯曲回环

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "简要分析：起在哪落笔、承在哪转折、转在什么主体元素上、合为何在题款附近",
  "qi": {"x": 50, "y": 80, "reason": "起在竹枝根部，墨色最浓处"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "承在枝干由直变弧的第一转折处"}],
  "zhuan": {"x": 55, "y": 30, "reason": "转在竹叶最密集处，画面视觉中心"},
  "he": {"x": 80, "y": 20, "reason": "合在题款旁，与起承转形成S形回环"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 坐标是百分比（0-100），x=0 左边, x=100 右边, y=0 上边, y=100 下边
- cheng_list 通常只有1个承点
- 起承转合必须**严格沿同一主体**分布
- 四个点整体应构成弯曲的回环路径（S/C形），而非直线排列
- **起不一定在左下！** 仔细观察墨迹实际起始位置
- path_shape 可选：S形、上升式、下降式、弧线、闭环"""


EXTRACT_AFTER_PROMPT = """这是一张已经标注了"起承转合"的国画线稿图。

请仔细观察图中的彩色箭头和标签，提取出人工标注的四个关键点坐标：
- 红色标签"起"：起点
- 橙色标签"承"：过渡点
- 蓝色标签"转"：转折点
- 绿色标签"合"：收束点

**输出格式**（只返回 JSON）：
```json
{
  "qi": {"x": 50, "y": 80},
  "cheng_list": [{"x": 45, "y": 50}],
  "zhuan": {"x": 55, "y": 30},
  "he": {"x": 80, "y": 20}
}
```

x, y 坐标是百分比（0-100）。如果有多个"承"点，全部列出。"""


def encode_image_to_base64(img_path: Path) -> str:
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Cannot read: {img_path}")
    h, w = img.shape[:2]
    if max(h, w) > 1024:
        scale = 1024 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(image_b64: str, prompt: str) -> Dict[str, Any]:
    model = settings.QWEN_MODEL.strip() or "qwen-vl-max"
    url = settings.QWEN_BASE_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
        "stream": False,
        "max_tokens": 4096,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0, read=120.0)) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    
    raw = data["choices"][0]["message"]["content"]
    
    # 更宽容的 JSON 解析
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if json_match:
        text = json_match.group(1)
    else:
        text = raw
    
    # 尝试修复常见的 JSON 格式问题
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # 尝试去掉 analysis 中的换行
        text = re.sub(r'"analysis":\s*"[^"]*"', '"analysis": ""', text, count=0)
        try:
            result = json.loads(text)
        except:
            raise
    
    return result, raw


def compare_with_human(ai_result: Dict, human: Dict) -> Dict[str, float]:
    diffs = {}
    for key in ["qi", "zhuan", "he"]:
        if key in ai_result and key in human:
            dx = abs(ai_result[key]["x"] - human[key]["x"])
            dy = abs(ai_result[key]["y"] - human[key]["y"])
            diffs[key] = (dx**2 + dy**2) ** 0.5
    
    if "cheng_list" in ai_result and "cheng_list" in human:
        for a, h in zip(ai_result["cheng_list"][:len(human["cheng_list"])],
                       human["cheng_list"]):
            dx = abs(a["x"] - h["x"])
            dy = abs(a["y"] - h["y"])
            diffs["cheng"] = (dx**2 + dy**2) ** 0.5
    
    return diffs


def run_validation(prompt: str, prompt_name: str, human_map: Dict, before_files: List[Path]):
    """运行一轮验证"""
    print(f"\n{'='*60}")
    print(f"验证: {prompt_name}")
    print(f"{'='*60}")
    
    qi_err, cheng_err, zhuan_err, he_err = [], [], [], []
    results = []
    
    for i, bp in enumerate(before_files):
        if bp.name not in human_map:
            continue
        
        human = human_map[bp.name]
        print(f"  [{i+1}/{len(before_files)}] {bp.name}...", end=" ", flush=True)
        
        try:
            b64 = encode_image_to_base64(bp)
            ai, _ = call_qwen_vl(b64, prompt)
            diffs = compare_with_human(ai, human)
            
            if "qi" in diffs: qi_err.append(diffs["qi"])
            if "cheng" in diffs: cheng_err.append(diffs["cheng"])
            if "zhuan" in diffs: zhuan_err.append(diffs["zhuan"])
            if "he" in diffs: he_err.append(diffs["he"])
            
            parts = [f"{k}={v:.0f}" for k, v in diffs.items()]
            print(f"OK ({', '.join(parts)})")
            results.append({"file": bp.name, "diffs": diffs})
        
        except Exception as e:
            print(f"FAIL ({str(e)[:60]})")
    
    # 统计
    print(f"\n  起: avg={np.mean(qi_err):.1f}%" if qi_err else "  起: N/A")
    print(f"  承: avg={np.mean(cheng_err):.1f}%" if cheng_err else "  承: N/A")
    print(f"  转: avg={np.mean(zhuan_err):.1f}%" if zhuan_err else "  转: N/A")
    print(f"  合: avg={np.mean(he_err):.1f}%" if he_err else "  合: N/A")
    
    all_err = qi_err + cheng_err + zhuan_err + he_err
    if all_err:
        print(f"  总体: avg={np.mean(all_err):.1f}%")
    
    return {
        "name": prompt_name,
        "qi": np.mean(qi_err) if qi_err else 999,
        "cheng": np.mean(cheng_err) if cheng_err else 999,
        "zhuan": np.mean(zhuan_err) if zhuan_err else 999,
        "he": np.mean(he_err) if he_err else 999,
        "total": np.mean(all_err) if all_err else 999,
    }


def main():
    # 加载人工标注
    with open(DEMO_DIR.parent / "training_phase1_results.json", "r", encoding="utf-8") as f:
        phase1 = json.load(f)
    human_map = {r["file"]: r["human"] for r in phase1}
    
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    before_files = [f for f in before_files if f.name in human_map]
    
    print("=" * 60)
    print("起承转合 Prompt 迭代验证 v3")
    print(f"样本数: {len(before_files)}")
    print("=" * 60)
    
    # 轮次 1: 原始 prompt（基线）
    # 轮次 2: V3 微调版
    stats = []
    stats.append(run_validation(BASE_PROMPT, "原始 Prompt (基线)", human_map, before_files))
    stats.append(run_validation(V3_PROMPT, "V3 微调版", human_map, before_files))
    
    # 对比总结
    print(f"\n{'='*60}")
    print("对比总结")
    print(f"{'='*60}")
    
    baseline = stats[0]
    for s in stats[1:]:
        print(f"\n{s['name']} vs 基线:")
        for key, label in [("qi", "起"), ("cheng", "承"), ("zhuan", "转"), ("he", "合"), ("total", "总体")]:
            b = baseline[key]
            v = s[key]
            if b < 999 and v < 999:
                diff = v - b
                arrow = "↓" if diff < 0 else "↑"
                print(f"  {label}: {b:.1f}% → {v:.1f}% ({arrow}{abs(diff):.1f}%)")
    
    # 保存结果
    with open(DEMO_DIR.parent / "training_v3_results.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
