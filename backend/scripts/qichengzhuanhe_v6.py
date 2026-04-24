"""
V6 训练验证 - 视线流动模型
===========================
基于豪哥的实际标注规则重新设计 prompt：

核心概念：起承转合 = 视线的流动路径（如作文的开头/陈述/转折/结尾）
- 起：视线开始的位置，画面的视觉入口
- 承：视线继续移动，沿画面主体推进
- 转：视线到达画面边缘开始转弯，或画面内容高潮
- 合：视线看完一幅画后的收束点

特殊规则：
1. 没有题跋时，印章作为起或合的加强
2. 题跋大面积贴边（顶上顶下顶左/右）时可忽略
3. 可以有多个起
4. 无法判断起承转合时（脱节、不连贯、以留空为主），退回疏密判定
5. 路径可以是：S线、Z线、圆形、方形、顺流直下、跌宕起伏等
"""

import json
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加后端目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np
import httpx
from app.core.config import get_settings

settings = get_settings()
DEMO_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'demojpg')

# V6 Prompt - 基于视线流动模型
V6_PROMPT = """你是一位专业的中国画构图分析专家。

请分析这张国画作品的"视线流动路径"，找出起承转合四个关键点。

**起承转合的本质 = 视线的流动路径**（如同作文的开头、陈述、转折、结尾）：
- **起**：视线的开始位置。是画面最先吸引目光的地方，是视觉入口。可能在任何位置，不一定是左下角。
- **承**：视线沿画面主体继续移动的过渡点。视线跟随线条、墨色、色彩推进。承可以有1-3个。
- **转**：视线到达画面边缘开始转弯，或画面内容出现高潮/转折的位置。是情节最密集或方向变化最大的地方。
- **合**：视线看完整个画面后的收束点。是视觉旅程的结束位置。

**路径类型**（可选）：
- S形/S线：视线呈S曲线流动
- Z线/Z形：视线呈Z字形流动
- 圆形/环形：视线绕一圈看完
- 方形/矩线：视线沿矩形路径流动
- 上升式/下降式：视线顺流直上或直下
- 跌宕起伏：视线反复跳跃

**特殊判断规则（非常重要！）**：
1. **无题跋时**：印章不是合点，而是对起或合的加强。印章在哪里就加强最近的那个点。
2. **题跋贴边时**：如果题跋大面积贴着画面边缘（顶上顶下且贴左/右），可以忽略它在起承转合中的作用。
3. **多起**：可以有多个起点，形成环形或闭合路径。
4. **不适用起承转合的情况**：如果画面脱节、不连贯、没有题跋且以留空为主，请在 analysis 中说明"此画不适用起承转合，以疏密判定"，但仍然给出四个点。

**分析步骤**：
1. 先观察画面整体：主体是什么？有没有题跋？印章在哪里？
2. 想象自己是一双眼睛，从哪里开始看这幅画？（起）
3. 眼睛怎么沿着画面内容移动？（承）
4. 视线在哪里发生了最重要的方向变化或聚焦？（转）
5. 看完整个画面后，视线最终收束在哪里？（合）
6. 如果没有题跋，印章在哪个点（起或合）附近？加强对那个点的选择。
7. 判断路径类型

**输出格式**（只返回 JSON）：
```json
{
  "analysis": "分析视线流动路径的理由，特别是起在哪里、合在哪里、路径类型",
  "has_inscription": true/false,
  "inscription_position": "题跋位置描述（如：右上角贴边/左侧中间/无题跋）",
  "seal_positions": [{"x": 50, "y": 80, "note": "印章描述"}],
  "qi": {"x": 50, "y": 80, "reason": "视线从这里开始"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "视线沿...移动到这里"}],
  "zhuan": {"x": 55, "y": 30, "reason": "视线在这里转弯/高潮"},
  "he": {"x": 80, "y": 20, "reason": "视线收束在这里"},
  "path_shape": "S形",
  "applicable": true
}
```

**注意**：
- x, y 是百分比（0-100），x=0 左边, x=100 右边, y=0 上边, y=100 下边
- cheng_list 是数组，可以有1-3个承点
- applicable=false 表示不适用起承转合（但仍需给出四个点）
- seal_positions 列出所有可见的印章位置（至少要标记"题跋下方的那枚印章"）"""


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
        data = r.json()
    
    return data["choices"][0]["message"]["content"]


def parse_json_response(raw):
    import re
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if match:
        return json.loads(match.group(1))
    return json.loads(raw)


def calc_dist(p1, p2):
    return ((p1["x"] - p2["x"])**2 + (p1["y"] - p2["y"])**2) ** 0.5


def run_v6_training():
    # 获取所有 before 文件
    files = sorted([f for f in os.listdir(DEMO_DIR) if f.endswith('_before.png')])
    if not files:
        print("未找到 before 图片")
        return
    
    # 读取人工标注
    with open(os.path.join(os.path.dirname(__file__), '..', '..', 'training_phase1_results.json'), 
              'r', encoding='utf-8') as f:
        human_data = {item["file"]: item["human"] for item in json.load(f)}
    
    print(f"共 {len(files)} 张图片，开始 V6 训练...\n")
    
    results = []
    total_stats = {"qi": [], "zhuan": [], "he": [], "cheng": []}
    
    for i, fname in enumerate(files):
        fpath = os.path.join(DEMO_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            print(f"  [{i+1}/{len(files)}] {fname} - 读取失败")
            continue
        
        human = human_data.get(fname)
        if not human:
            print(f"  [{i+1}/{len(files)}] {fname} - 无人工标注")
            continue
        
        print(f"  [{i+1}/{len(files)}] {fname} ...", end=" ", flush=True)
        
        try:
            b64 = encode_image(img)
            raw = call_qwen_vl(V6_PROMPT, b64)
            result = parse_json_response(raw)
            
            # 计算偏差
            diffs = {}
            
            # 起
            qi_diff = calc_dist(result.get("qi", {}), human["qi"])
            diffs["qi"] = {"ai": result.get("qi", {}), "human": human["qi"], "dist": qi_diff}
            total_stats["qi"].append(qi_diff)
            
            # 转
            zhuan_diff = calc_dist(result.get("zhuan", {}), human["zhuan"])
            diffs["zhuan"] = {"ai": result.get("zhuan", {}), "human": human["zhuan"], "dist": zhuan_diff}
            total_stats["zhuan"].append(zhuan_diff)
            
            # 合
            he_diff = calc_dist(result.get("he", {}), human["he"])
            diffs["he"] = {"ai": result.get("he", {}), "human": human["he"], "dist": he_diff}
            total_stats["he"].append(he_diff)
            
            # 承（取偏差最小的对应）
            ai_chengs = result.get("cheng_list", [])
            human_chengs = human.get("cheng_list", [])
            if ai_chengs and human_chengs:
                cheng_dists = []
                for hc in human_chengs:
                    best_d = min(calc_dist(ac, hc) for ac in ai_chengs)
                    cheng_dists.append(best_d)
                avg_cheng = sum(cheng_dists) / len(cheng_dists)
                diffs["cheng"] = {"dist": avg_cheng, "count": len(ai_chengs)}
                total_stats["cheng"].append(avg_cheng)
            
            # 印章检测
            seals = result.get("seal_positions", [])
            has_inscription = result.get("has_inscription", True)
            inscription_pos = result.get("inscription_position", "")
            applicable = result.get("applicable", True)
            path_shape = result.get("path_shape", "")
            analysis = result.get("analysis", "")
            
            results.append({
                "file": fname,
                "ai_qi": result.get("qi", {}),
                "ai_cheng": ai_chengs,
                "ai_zhuan": result.get("zhuan", {}),
                "ai_he": result.get("he", {}),
                "human_qi": human["qi"],
                "human_cheng": human_chengs,
                "human_zhuan": human["zhuan"],
                "human_he": human["he"],
                "diffs": diffs,
                "seals": seals,
                "has_inscription": has_inscription,
                "inscription_position": inscription_pos,
                "applicable": applicable,
                "path_shape": path_shape,
                "analysis": analysis,
            })
            
            print(f"qi={qi_diff:.0f}% zhuan={zhuan_diff:.0f}% he={he_diff:.0f}% | "
                  f"题跋={'有' if has_inscription else '无'} | "
                  f"路径={path_shape} | 适用={applicable}")
            
        except Exception as e:
            print(f"失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 统计总结
    print("\n" + "="*70)
    print("V6 训练结果总结")
    print("="*70)
    
    for key, label in [("qi", "起"), ("zhuan", "转"), ("he", "合"), ("cheng", "承")]:
        vals = total_stats[key]
        if vals:
            avg = sum(vals) / len(vals)
            print(f"  {label}: 平均偏差 {avg:.1f}% (样本数: {len(vals)}, 最小: {min(vals):.1f}%, 最大: {max(vals):.1f}%)")
    
    all_dists = total_stats["qi"] + total_stats["zhuan"] + total_stats["he"] + total_stats["cheng"]
    if all_dists:
        print(f"  总体平均: {sum(all_dists)/len(all_dists):.1f}%")
    
    # 特殊案例分析
    print("\n特殊案例分析:")
    for r in results:
        fname = r["file"]
        he_diff = r["diffs"].get("he", {}).get("dist", 999)
        if he_diff > 40:
            print(f"  {fname}: 合偏差={he_diff:.0f}% | "
                  f"题跋={'有' if r['has_inscription'] else '无'} | "
                  f"位置={r['inscription_position']} | "
                  f"路径={r['path_shape']} | "
                  f"AI合=({r['ai_he'].get('x','?')},{r['ai_he'].get('y','?')}) "
                  f"人工合=({r['human_he']['x']},{r['human_he']['y']})")
            print(f"    分析: {r['analysis'][:100]}...")
    
    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'training_v6_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    run_v6_training()
