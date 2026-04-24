"""
起承转合 V5 — 混合方案
=========================
LLM 检测印章位置 + 几何算法计算合点

策略：
1. LLM 做两件事：
   a. 分析起、承、转三点（主任务）
   b. 检测题款/印章区域的位置（辅助任务）
2. 算法根据 LLM 给的印章位置 + 起承转三点，计算最佳合点
3. 合点的选择目标是形成回环闭合
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

# V5 Prompt: LLM 检测起承转 + 印章/题款位置
V5_PROMPT = """你是一位专业的中国画构图分析专家。

请分析这张国画作品，完成两个任务：

**任务1：找出"起、承、转"三个关键点**
- **起**：画家笔锋首次接触画面的物理落笔点。仔细观察墨迹源头——哪里的墨色最浓、线条最粗重、有枯笔飞白？起可以在画面任何位置，绝不默认左下角。
- **承**：从起沿主体走势延伸后的第一个重要转折处。通常只有1个承点。
- **转**：画面视觉高潮所在的主体结构中心。必须精确落在主体元素上。

**任务2：检测题款和印章的位置**
- 仔细寻找竖排文字（题款）和红色方形/圆形（印章）的位置
- 记录每个印章的坐标
- 记录题款文字区域的大致范围

**输出格式**（只返回 JSON）：
```json
{
  "analysis": "简要分析画面主体和走势",
  "qi": {"x": 50, "y": 80, "reason": "起在竹枝根部"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "承在枝干转折处"}],
  "zhuan": {"x": 55, "y": 30, "reason": "转在竹叶最密集处"},
  "seals": [{"x": 80, "y": 20, "desc": "右上角朱文印"}, {"x": 82, "y": 30, "desc": "右上角白文印"}],
  "inscription": {"x": 78, "y": 15, "w": 5, "h": 25, "desc": "右侧竖排题款"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 坐标是百分比（0-100）
- cheng_list 通常1个
- 起不一定在左下
- seals 列出所有印章，inscription 记录题款位置
- 如果没有印章/题款，seals 和 inscription 可以为空数组"""


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
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if json_match:
        text = json_match.group(1)
    else:
        text = raw
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        text2 = re.sub(r'"analysis":\s*"[^"]*"', '"analysis": ""', text, count=0)
        try:
            result = json.loads(text2)
        except:
            result = {"qi": {"x": 50, "y": 90}, "cheng_list": [], "zhuan": {"x": 50, "y": 30}, "seals": [], "inscription": {}}
    return result, raw


def compute_he_from_llm(ai_result: Dict) -> Dict:
    """
    基于 LLM 返回的起承转 + 印章/题款位置，算法计算合点。
    
    策略：
    1. 收集 LLM 检测到的印章和题款位置
    2. 计算起→转的主走势方向
    3. 在印章/题款附近选一个与转形成回环的点
    """
    qi = ai_result.get("qi", {"x": 50, "y": 90})
    cheng_list = ai_result.get("cheng_list", [])
    zhuan = ai_result.get("zhuan", {"x": 50, "y": 30})
    seals = ai_result.get("seals", [])
    inscription = ai_result.get("inscription", {})
    
    # 收集候选锚点
    anchors = []
    
    for seal in seals:
        if isinstance(seal, dict) and "x" in seal and "y" in seal:
            anchors.append({"x": seal["x"], "y": seal["y"], "weight": 1.5, "source": "seal"})
    
    if isinstance(inscription, dict) and "x" in inscription:
        # 题款的底部（竖排文字末端）
        ix = inscription["x"]
        ih = inscription.get("h", 20)
        iy_bottom = inscription.get("y", 20) + ih
        anchors.append({"x": ix, "y": iy_bottom, "weight": 1.0, "source": "inscription_end"})
        anchors.append({"x": ix, "y": inscription.get("y", 20), "weight": 0.7, "source": "inscription_start"})
    
    # 如果没有检测到印章/题款，用几何兜底
    if not anchors:
        return _geometric_fallback(qi, cheng_list, zhuan)
    
    # 计算走势方向
    trend_dx = zhuan["x"] - qi["x"]
    trend_dy = zhuan["y"] - qi["y"]
    trend_len = np.sqrt(trend_dx**2 + trend_dy**2) or 1
    
    # 在锚点中选择最佳合点
    best_he = None
    best_score = -999
    
    for anchor in anchors:
        ax, ay = anchor["x"], anchor["y"]
        weight = anchor["weight"]
        
        # 转→锚点 向量
        zh_to_a_dx = ax - zhuan["x"]
        zh_to_a_dy = ay - zhuan["y"]
        
        # 叉积衡量弯曲程度
        cross = trend_dx * zh_to_a_dy - trend_dy * zh_to_a_dx
        bend_score = min(abs(cross) / (trend_len * 50 + 1), 1.0)
        
        # 距离得分（不要太远也不要太近）
        dist = np.sqrt(zh_to_a_dx**2 + zh_to_a_dy**2)
        dist_score = 1.0 - min(abs(dist - 30) / 70, 1.0)  # 理想距离约30%
        
        score = bend_score * 0.5 + dist_score * 0.3 + weight * 0.2
        
        if score > best_score:
            best_score = score
            best_he = {"x": round(ax, 1), "y": round(ay, 1)}
    
    if best_he:
        best_he["reason"] = f"算法选择（基于{len(anchors)}个锚点中的最佳回环点）"
        best_he["method"] = "llm_anchor"
        return best_he
    
    return _geometric_fallback(qi, cheng_list, zhuan)


def _geometric_fallback(qi: Dict, cheng_list: List, zhuan: Dict) -> Dict:
    """几何兜底：无印章/题款时的合点计算"""
    # 与起点对角位置
    he_x = 100 - qi["x"]
    he_y = 100 - qi["y"]
    
    # 限制范围
    he_x = max(5, min(95, he_x))
    he_y = max(5, min(95, he_y))
    
    return {
        "x": round(he_x, 1),
        "y": round(he_y, 1),
        "reason": "几何兜底（无印章/题款，选择与起对角位置）",
        "method": "geometric_fallback",
    }


def compare_points(ai: Dict, human: Dict, keys=["qi", "zhuan", "he"]):
    diffs = {}
    for key in keys:
        if key in ai and key in human:
            dx = abs(ai[key]["x"] - human[key]["x"])
            dy = abs(ai[key]["y"] - human[key]["y"])
            diffs[key] = (dx**2 + dy**2) ** 0.5
    if "cheng_list" in ai and "cheng_list" in human:
        for a, h in zip(ai["cheng_list"][:len(human["cheng_list"])],
                       human["cheng_list"]):
            dx = abs(a["x"] - h["x"])
            dy = abs(a["y"] - h["y"])
            diffs["cheng"] = (dx**2 + dy**2) ** 0.5
    return diffs


def main():
    with open(DEMO_DIR.parent / "training_phase1_results.json", "r", encoding="utf-8") as f:
        phase1 = json.load(f)
    human_map = {r["file"]: r["human"] for r in phase1}
    
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    before_files = [f for f in before_files if f.name in human_map]
    
    print("=" * 60)
    print("V5 验证: LLM检测印章 + 算法计算合点")
    print(f"样本数: {len(before_files)}")
    print("=" * 60)
    
    qi_err, cheng_err, zhuan_err, he_err = [], [], [], []
    details = []
    
    for i, bp in enumerate(before_files):
        human = human_map[bp.name]
        print(f"  [{i+1}/{len(before_files)}] {bp.name}...", end=" ", flush=True)
        
        try:
            b64 = encode_image_to_base64(bp)
            ai, _ = call_qwen_vl(b64, V5_PROMPT)
            
            # 算法计算合点
            he = compute_he_from_llm(ai)
            ai["he"] = he
            
            diffs = compare_points(ai, human)
            
            if "qi" in diffs: qi_err.append(diffs["qi"])
            if "cheng" in diffs: cheng_err.append(diffs["cheng"])
            if "zhuan" in diffs: zhuan_err.append(diffs["zhuan"])
            if "he" in diffs: he_err.append(diffs["he"])
            
            parts = [f"{k}={v:.0f}" for k, v in diffs.items()]
            method = he.get("method", "?")
            seals = len(ai.get("seals", []))
            insc = "Y" if ai.get("inscription") else "N"
            print(f"OK ({', '.join(parts)}) [{method}, seals={seals}, insc={insc}]")
            details.append({"file": bp.name, "he_method": method, "seals": seals, "diffs": diffs})
            
        except Exception as e:
            print(f"FAIL ({str(e)[:80]})")
    
    print(f"\n{'='*60}")
    print("V5 结果统计")
    print(f"{'='*60}")
    print(f"  起: avg={np.mean(qi_err):.1f}%" if qi_err else "  起: N/A")
    print(f"  承: avg={np.mean(cheng_err):.1f}%" if cheng_err else "  承: N/A")
    print(f"  转: avg={np.mean(zhuan_err):.1f}%" if zhuan_err else "  转: N/A")
    print(f"  合: avg={np.mean(he_err):.1f}%" if he_err else "  合: N/A")
    
    all_err = qi_err + cheng_err + zhuan_err + he_err
    if all_err:
        print(f"  总体: avg={np.mean(all_err):.1f}%")
    
    # 对比基线
    print(f"\n{'='*60}")
    print("与基线对比")
    print(f"{'='*60}")
    
    r1_qi, r1_zhuan, r1_he, r1_cheng = [], [], [], []
    for r in phase1:
        d = r.get("diffs", {})
        if "qi" in d and isinstance(d["qi"], dict): r1_qi.append(d["qi"]["dist"])
        if "zhuan" in d and isinstance(d["zhuan"], dict): r1_zhuan.append(d["zhuan"]["dist"])
        if "he" in d and isinstance(d["he"], dict): r1_he.append(d["he"]["dist"])
        if "cheng_list" in d:
            for c in d["cheng_list"]:
                r1_cheng.append(c["dist"])
    
    for name, r1, r2 in [
        ("起", r1_qi, qi_err), ("承", r1_cheng, cheng_err),
        ("转", r1_zhuan, zhuan_err), ("合", r1_he, he_err),
    ]:
        if r1 and r2:
            a1, a2 = np.mean(r1), np.mean(r2)
            diff = a2 - a1
            arrow = "↓" if diff < 0 else "↑"
            print(f"  {name}: {a1:.1f}% → {a2:.1f}% ({arrow}{abs(diff):.1f}%)")
    
    all_r1 = r1_qi + r1_cheng + r1_zhuan + r1_he
    if all_r1 and all_err:
        a1, a2 = np.mean(all_r1), np.mean(all_err)
        diff = a2 - a1
        arrow = "↓" if diff < 0 else "↑"
        print(f"  总体: {a1:.1f}% → {a2:.1f}% ({arrow}{abs(diff):.1f}%)")
    
    # 详细分析合点偏差
    print(f"\n{'='*60}")
    print("合点详细分析")
    print(f"{'='*60}")
    for d in details:
        he_diff = d["diffs"].get("he", 0)
        he_method = d["he_method"]
        seals = d["seals"]
        file = d["file"]
        print(f"  {file}: he_diff={he_diff:.0f}%, method={he_method}, seals={seals}")
    
    # 保存
    with open(DEMO_DIR.parent / "training_v5_results.json", "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
