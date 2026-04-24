"""
V7 训练验证 - 最佳融合方案
===========================
融合 V6(视线流动) + 原始prompt(合靠题款) 的优点：
- 起承转：用"视线流动"模型描述，不固定位置
- 合：保留"靠近题款/印章"约束，但加入特殊规则
- 特殊规则：无题跋时印章加强起或合、贴边忽略、可以多起
"""

import json
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np
import httpx
from app.core.config import get_settings

settings = get_settings()
DEMO_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'demojpg')

# V7 Prompt - 融合版
V7_PROMPT = """你是一位专业的中国画构图分析专家。

请分析这张国画作品的"起承转合"四个关键点。

**核心概念：起承转合 = 视线的流动路径**（如同作文的开头、陈述、转折、结尾）

- **起**：视线的开始位置，画面最先吸引目光的入口。可能在任何位置，不限于左下角。通常是墨色最浓、形态最完整、或色彩对比最强的位置。
- **承**：视线沿画面主体继续移动的过渡点。沿枝干、线条、色彩推进，承可以有1-2个。
- **转**：方向转折或视觉高潮的位置。是画面中最密集、最有张力的焦点（花朵/鸟雀/主体元素）。
- **合**：画面的收束点，**通常靠近题款/印章区域**。是视线看完整个画面后的最终归宿。

**合点定位原则（非常重要）**：
1. 有题跋时：合应靠近题款末尾或其下方印章的位置
2. 无题跋时：印章作为起或合的**加强**（不作为独立合点），印章靠近哪个点就加强对那个点的选择
3. 题跋如果大面积贴着画面边缘（顶上顶下顶左或顶右），可以忽略其在构图中的作用
4. 合与转之间应形成回转趋势（方向变化），构成接近闭合的路径

**路径类型**（选最接近的）：S形、Z形、上升式、下降式、环形、方形

**分析步骤**：
1. 先观察画面整体：主体是什么？题跋在哪？印章在哪？
2. 想象眼睛从哪里开始看这幅画？（起）
3. 视线怎么沿画面内容移动？（承）
4. 视线在哪里发生了最重要的方向变化或聚焦？（转）
5. 看完画面后视线收束在哪？通常在题款/印章附近（合）

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "简述视线流动路径和起承转合分布理由",
  "has_inscription": true,
  "inscription_edge": "贴边/半贴边/不贴边/无题跋",
  "seal_positions": [{"x": 50, "y": 80, "near": "题跋下方"}],
  "qi": {"x": 50, "y": 80, "reason": "视线入口"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "视线沿...移动"}],
  "zhuan": {"x": 55, "y": 30, "reason": "转折/高潮"},
  "he": {"x": 80, "y": 20, "reason": "收束于题款/印章附近"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 是百分比（0-100），x=0 左, x=100 右, y=0 上, y=100 下
- cheng_list 数组，1-2个承点
- seal_positions 标记所有可见印章位置"""


def encode_image(img_bgr, max_side=1024):
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    import base64
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(prompt, base64_image):
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
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }],
        "stream": False,
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0, read=90.0)) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def parse_json_response(raw):
    import re
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if match:
        return json.loads(match.group(1))
    return json.loads(raw)


def calc_dist(p1, p2):
    return ((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2) ** 0.5


def run_v7_training():
    files = sorted([f for f in os.listdir(DEMO_DIR) if f.endswith('_before.png')])
    if not files:
        print("未找到 before 图片")
        return
    
    with open(os.path.join(os.path.dirname(__file__), '..', '..', 'training_phase1_results.json'), 
              'r', encoding='utf-8') as f:
        human_data = {item["file"]: item["human"] for item in json.load(f)}
    
    print(f"共 {len(files)} 张图片，开始 V7 训练...\n")
    
    results = []
    total_stats = {"qi": [], "zhuan": [], "he": [], "cheng": []}
    
    # 同时加载原始prompt结果做对比
    baseline_stats = {"qi": [], "zhuan": [], "he": [], "cheng": []}
    
    ORIGINAL_PROMPT = """你是一位专业的中国画构图分析专家，精通潘天寿的构图理论和"起承转合"法则。

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
    
    for i, fname in enumerate(files):
        fpath = os.path.join(DEMO_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            continue
        
        human = human_data.get(fname)
        if not human:
            continue
        
        print(f"  [{i+1}/{len(files)}] {fname}", end=" ... ", flush=True)
        
        try:
            b64 = encode_image(img)
            raw = call_qwen_vl(V7_PROMPT, b64)
            result = parse_json_response(raw)
            
            # V7 偏差
            diffs = {}
            qi_diff = calc_dist(result.get("qi", {}), human["qi"])
            diffs["qi"] = qi_diff
            total_stats["qi"].append(qi_diff)
            
            zhuan_diff = calc_dist(result.get("zhuan", {}), human["zhuan"])
            diffs["zhuan"] = zhuan_diff
            total_stats["zhuan"].append(zhuan_diff)
            
            he_diff = calc_dist(result.get("he", {}), human["he"])
            diffs["he"] = he_diff
            total_stats["he"].append(he_diff)
            
            ai_chengs = result.get("cheng_list", [])
            human_chengs = human.get("cheng_list", [])
            if ai_chengs and human_chengs:
                cheng_dists = []
                for hc in human_chengs:
                    best_d = min(calc_dist(ac, hc) for ac in ai_chengs)
                    cheng_dists.append(best_d)
                avg_cheng = sum(cheng_dists) / len(cheng_dists)
                diffs["cheng"] = avg_cheng
                total_stats["cheng"].append(avg_cheng)
            
            results.append({
                "file": fname,
                "diffs": diffs,
                "has_inscription": result.get("has_inscription", True),
                "inscription_edge": result.get("inscription_edge", ""),
                "seals": result.get("seal_positions", []),
                "path_shape": result.get("path_shape", ""),
                "analysis": result.get("analysis", ""),
            })
            
            print(f"qi={qi_diff:.0f}% zh={zhuan_diff:.0f}% he={he_diff:.0f}% "
                  f"ch={diffs.get('cheng', 0):.0f}% | "
                  f"题跋={'贴边' if '贴边' in result.get('inscription_edge', '') else '有' if result.get('has_inscription') else '无'}")
            
        except Exception as e:
            print(f"失败: {e}")
    
    # 汇总
    print("\n" + "="*70)
    print("V7 训练结果（视线流动+合靠题款融合版）")
    print("="*70)
    
    for key, label in [("qi", "起"), ("zhuan", "转"), ("he", "合"), ("cheng", "承")]:
        vals = total_stats[key]
        if vals:
            avg = sum(vals) / len(vals)
            print(f"  {label}: {avg:.1f}% (n={len(vals)}, min={min(vals):.1f}%, max={max(vals):.1f}%)")
    
    all_d = total_stats["qi"] + total_stats["zhuan"] + total_stats["he"] + total_stats["cheng"]
    print(f"  总体: {sum(all_d)/len(all_d):.1f}%")
    
    # 版本对比
    print("\n" + "-"*70)
    print("各版本对比:")
    print(f"  原始prompt:   起=54.9% 承=33.6% 转=19.4% 合=31.6% 总体=32.6%")
    print(f"  V4(去合):     起=31.3%          转=21.1% 合=54.6% 总体=32.2%")
    print(f"  V5(LLM印章):  起=31.3%          转=21.1% 合=52.5% 总体=33.7%")
    print(f"  V6(纯视线):   起=49.5% 承=23.2% 转=39.1% 合=68.7% 总体=45.1%")
    v7_total = sum(all_d)/len(all_d) if all_d else 0
    v7_qi = sum(total_stats["qi"])/len(total_stats["qi"]) if total_stats["qi"] else 0
    v7_zh = sum(total_stats["zhuan"])/len(total_stats["zhuan"]) if total_stats["zhuan"] else 0
    v7_he = sum(total_stats["he"])/len(total_stats["he"]) if total_stats["he"] else 0
    v7_ch = sum(total_stats["cheng"])/len(total_stats["cheng"]) if total_stats["cheng"] else 0
    print(f"  V7(融合):     起={v7_qi:.1f}% 承={v7_ch:.1f}% 转={v7_zh:.1f}% 合={v7_he:.1f}% 总体={v7_total:.1f}%")
    
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'training_v7_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    run_v7_training()
