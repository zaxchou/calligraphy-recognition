"""
V8 训练验证 - 起点硬规则版
===========================
基于豪哥补充的三条"起"的硬规则：
1. 起必须在画面边缘处有画才的部分
2. 起遵循生长规律（根→干→枝→花/果，不会反过来）
3. 起一定从生长起始出发，不会从留白处出来
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

# V8 Prompt - 起点硬规则版
V8_PROMPT = """你是一位专业的中国画构图分析专家。

请分析这张国画作品的"起承转合"四个关键点。

**核心概念：起承转合 = 视线浏览一幅画的完整路径**（如同作文的开头、陈述、转折、结尾）

**起的硬规则（必须严格遵守）**：
1. **起必须在画面边缘处有画才的部分** — 不在画面中央，不在留白处。起是笔墨从画面外"进入"画面的位置。
2. **起遵循大自然的生长规律** — 从生长的起始出发。例如：树干→枝条→花/果实（不会反过来）；石头→枝条→花（不会从花到石头）；根部→干→梢。起永远在生长链的最前端。
3. **起一定从画材的生长起点出发** — 不会从留白处出来。如果画面主体是一棵树，起就在树根或树干入画处；如果是竹子，起就在竹竿入画处。
4. **注意**：起不一定在左下角，可能在任何边缘（上/下/左/右），取决于画材从哪个方向进入画面。

**承**：从起出发，视线沿画材的生长方向推进。沿枝干、茎叶、石头等笔墨实体前进，承可以有1-2个。

**转**：视线到达转折点或视觉高潮。通常是画面中笔墨最密集、形态张力最强的位置（花朵/鸟雀/果簇/叶簇）。

**合**：画面的收束点，视线浏览完整个画面后的归宿。
- 有题跋时：合靠近题款末尾或其下方印章
- 无题跋时：印章作为起或合的加强（印章靠近哪个点就加强对那个点的选择）
- 题跋大面积贴着画面边缘（顶上顶下且贴左/右）时：忽略题跋的构图作用
- 合与转之间应有回转趋势

**路径类型**（选最接近的）：S形、Z形、上升式、下降式、环形、方形

**分析步骤**（必须按此顺序）：
1. 识别画材类型：树/竹/花/鸟/石/菜等
2. 确定生长方向：画材从画面的哪个边缘进入？入画点在哪？
3. 找到"起"：画材在画面边缘的入画处（根部/底部/起笔处），必须在边缘且有墨迹
4. 从起出发，沿画材的生长路径找到"承"（1-2个过渡点）
5. 找到"转"：路径中最重要的转折或高潮
6. 找到"合"：视线的收束处（通常在题款/印章附近）

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "视线流动路径分析，重点说明起为什么在边缘入画处",
  "material_type": "梅/兰/竹/菊/鸟/石/蔬果等",
  "growth_direction": "从右下入画向左上生长/从左下入画向右上生长等",
  "has_inscription": true,
  "inscription_edge": "贴边/半贴边/不贴边/无题跋",
  "seal_positions": [{"x": 50, "y": 80, "near": "题跋下方"}],
  "qi": {"x": 50, "y": 80, "reason": "树干从右下边缘入画处"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "沿主干向上推进"}],
  "zhuan": {"x": 55, "y": 30, "reason": "花朵密集处/视觉高潮"},
  "he": {"x": 80, "y": 20, "reason": "收束于题款/印章附近"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 是百分比（0-100），x=0 左, x=100 右, y=0 上, y=100 下
- cheng_list 数组，1-2个承点
- seal_positions 标记所有可见印章位置
- **起的 x 或 y 必须接近 0 或 100（在边缘），不能在画面中央（x 和 y 都在 20-80 之间）**"""


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


def is_on_edge(point, threshold=25):
    """检查点是否在画面边缘（x或y接近0或100）"""
    return point["x"] <= threshold or point["x"] >= (100 - threshold) or \
           point["y"] <= threshold or point["y"] >= (100 - threshold)


def run_v8_training():
    files = sorted([f for f in os.listdir(DEMO_DIR) if f.endswith('_before.png')])
    if not files:
        print("未找到 before 图片")
        return
    
    with open(os.path.join(os.path.dirname(__file__), '..', '..', 'training_phase1_results.json'), 
              'r', encoding='utf-8') as f:
        human_data = {item["file"]: item["human"] for item in json.load(f)}
    
    print(f"共 {len(files)} 张图片，开始 V8 训练...\n")
    
    results = []
    total_stats = {"qi": [], "zhuan": [], "he": [], "cheng": []}
    qi_edge_correct = 0
    qi_edge_total = 0
    
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
            raw = call_qwen_vl(V8_PROMPT, b64)
            result = parse_json_response(raw)
            
            diffs = {}
            
            # 起
            qi_diff = calc_dist(result.get("qi", {}), human["qi"])
            diffs["qi"] = qi_diff
            total_stats["qi"].append(qi_diff)
            
            # 检查起是否在边缘
            ai_qi = result.get("qi", {})
            on_edge = is_on_edge(ai_qi)
            qi_edge_total += 1
            if on_edge:
                qi_edge_correct += 1
            
            # 转
            zhuan_diff = calc_dist(result.get("zhuan", {}), human["zhuan"])
            diffs["zhuan"] = zhuan_diff
            total_stats["zhuan"].append(zhuan_diff)
            
            # 合
            he_diff = calc_dist(result.get("he", {}), human["he"])
            diffs["he"] = he_diff
            total_stats["he"].append(he_diff)
            
            # 承
            ai_chengs = result.get("cheng_list", [])
            human_chengs = human.get("cheng_list", [])
            cheng_avg = 0
            if ai_chengs and human_chengs:
                cheng_dists = []
                for hc in human_chengs:
                    best_d = min(calc_dist(ac, hc) for ac in ai_chengs)
                    cheng_dists.append(best_d)
                cheng_avg = sum(cheng_dists) / len(cheng_dists)
                diffs["cheng"] = cheng_avg
                total_stats["cheng"].append(cheng_avg)
            
            material = result.get("material_type", "?")
            growth = result.get("growth_direction", "?")
            path = result.get("path_shape", "?")
            analysis = result.get("analysis", "")
            
            results.append({
                "file": fname,
                "diffs": diffs,
                "qi_on_edge": on_edge,
                "human_qi": human["qi"],
                "ai_qi": ai_qi,
                "material": material,
                "growth": growth,
                "path": path,
                "analysis": analysis,
            })
            
            edge_mark = "✓边缘" if on_edge else "✗中央"
            print(f"qi={qi_diff:.0f}%({edge_mark}) zh={zhuan_diff:.0f}% he={he_diff:.0f}% ch={cheng_avg:.0f}% | "
                  f"{material} {growth}")
            
        except Exception as e:
            print(f"失败: {e}")
    
    # 汇总
    print("\n" + "="*70)
    print("V8 训练结果（起点硬规则版）")
    print("="*70)
    
    for key, label in [("qi", "起"), ("zhuan", "转"), ("he", "合"), ("cheng", "承")]:
        vals = total_stats[key]
        if vals:
            avg = sum(vals) / len(vals)
            print(f"  {label}: {avg:.1f}% (n={len(vals)}, min={min(vals):.1f}%, max={max(vals):.1f}%)")
    
    all_d = total_stats["qi"] + total_stats["zhuan"] + total_stats["he"] + total_stats["cheng"]
    print(f"  总体: {sum(all_d)/len(all_d):.1f}%")
    
    print(f"\n  起点边缘命中: {qi_edge_correct}/{qi_edge_total} ({qi_edge_correct/max(qi_edge_total,1)*100:.0f}%)")
    
    # 版本对比
    print("\n" + "-"*70)
    print("各版本对比:")
    print(f"  V1 原始:     起=54.9% 承=33.6% 转=19.4% 合=31.6% 总体=32.6%")
    print(f"  V4 去合:     起=31.3%          转=21.1% 合=54.6% 总体=32.2%")
    print(f"  V7 融合:     起=52.2% 承=28.7% 转=25.0% 合=52.0% 总体=39.5%")
    v8_total = sum(all_d)/len(all_d) if all_d else 0
    v8_qi = sum(total_stats["qi"])/len(total_stats["qi"]) if total_stats["qi"] else 0
    v8_zh = sum(total_stats["zhuan"])/len(total_stats["zhuan"]) if total_stats["zhuan"] else 0
    v8_he = sum(total_stats["he"])/len(total_stats["he"]) if total_stats["he"] else 0
    v8_ch = sum(total_stats["cheng"])/len(total_stats["cheng"]) if total_stats["cheng"] else 0
    print(f"  V8 起硬规则: 起={v8_qi:.1f}% 承={v8_ch:.1f}% 转={v8_zh:.1f}% 合={v8_he:.1f}% 总体={v8_total:.1f}%")
    
    # 人工标注的起是否也在边缘？
    print(f"\n  人工标注的起点位置分布:")
    for r in results:
        hq = r["human_qi"]
        edge_h = is_on_edge(hq)
        print(f"    {r['file']}: 人工起=({hq['x']},{hq['y']}) {'边缘' if edge_h else '中央'} | "
              f"AI起=({r['ai_qi'].get('x','?')},{r['ai_qi'].get('y','?')}) {'边缘' if r['qi_on_edge'] else '中央'} | "
              f"偏差={r['diffs']['qi']:.0f}%")
    
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'training_v8_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到 {output_path}")


if __name__ == "__main__":
    run_v8_training()
