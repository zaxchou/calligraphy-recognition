"""
起承转合 Prompt 学习脚本
=========================
通过对比 before/after 人工标注，让大模型分析偏差规律，生成优化后的 prompt。

使用方法: python scripts/qichengzhuanhe_learn.py [样本数]
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

# Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.core.config import get_settings
import numpy as np

settings = get_settings()
DEMO_DIR = Path(__file__).parent.parent.parent / "demojpg"

CURRENT_PROMPT = """你是一位专业的中国画构图分析专家，精通潘天寿的构图理论和"起承转合"法则。

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


LEARN_PROMPT = """你是一位中国画构图分析专家，也是一位 Prompt 工程师。我正在训练一个 AI 模型来分析国画作品的"起承转合"构图法则。

现在我有一组训练数据，是 AI 分析结果和人工标注的对比。请你仔细分析这些差异，找出 AI 的系统性偏差，然后帮我优化 prompt。

## 当前 Prompt
{current_prompt}

## 训练对比数据
以下是 AI 分析结果和人工标注的对比（坐标是百分比 0-100）：

{training_data}

## 任务
1. 仔细分析每张图片的 AI 结果和人工标注差异
2. 找出 AI 的系统性偏差模式（比如：AI 总是把起放在左下角，但人工标注可能在任何角落）
3. 分析人工标注的规律（起承转合的实际定位原则）
4. 输出一个优化后的 prompt

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
- 在定义和规则部分加入从人工标注中学到的改进
- 只优化 prompt 的指导性内容，不要改变 JSON schema"""


def encode_image_to_base64(img_path: Path) -> str:
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Cannot read: {img_path}")
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 1024:
        scale = 1024 / max_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(image_b64: str, prompt: str, model: str = None) -> Dict[str, Any]:
    if model is None:
        model = settings.QWEN_MODEL.strip() or "qwen-vl-max"
    
    url = settings.QWEN_BASE_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
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
        result = json.loads(json_match.group(1))
    else:
        result = json.loads(raw)
    
    return result, raw


def call_qwen_text(prompt: str, model: str = None) -> str:
    """调用 Qwen 文本模型（不用图片）"""
    if model is None:
        model = "qwen-plus"
    
    url = settings.QWEN_BASE_URL.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "max_tokens": 8192,
        "temperature": 0.7,
    }
    
    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0, read=120.0)) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    
    return data["choices"][0]["message"]["content"]


def run_phase1_collect(max_samples: int = None) -> List[Dict]:
    """Phase 1: 收集 AI 和人工标注的对比数据"""
    results = []
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    
    if max_samples:
        before_files = before_files[:max_samples]
    
    print(f"Phase 1: 收集 {len(before_files)} 组对比数据...")
    
    for i, before_path in enumerate(before_files):
        after_path = DEMO_DIR / before_path.name.replace("_before.png", "_after.png")
        
        if not after_path.exists():
            print(f"  [{i+1}] 跳过 {before_path.name}（无 after）")
            continue
        
        print(f"  [{i+1}/{len(before_files)}] {before_path.name}...", end=" ", flush=True)
        
        try:
            before_b64 = encode_image_to_base64(before_path)
            ai_result, _ = call_qwen_vl(before_b64, CURRENT_PROMPT)
            
            after_b64 = encode_image_to_base64(after_path)
            human_result, _ = call_qwen_vl(after_b64, EXTRACT_AFTER_PROMPT)
            
            # 计算差异
            diffs = {}
            for key in ["qi", "zhuan", "he"]:
                if key in ai_result and key in human_result:
                    dx = abs(ai_result[key]["x"] - human_result[key]["x"])
                    dy = abs(ai_result[key]["y"] - human_result[key]["y"])
                    diffs[key] = {"dx": dx, "dy": dy, "dist": (dx**2+dy**2)**0.5}
            
            if "cheng_list" in ai_result and "cheng_list" in human_result:
                for a, h in zip(ai_result["cheng_list"][:len(human_result["cheng_list"])], 
                               human_result["cheng_list"]):
                    dx = abs(a["x"] - h["x"])
                    dy = abs(a["y"] - h["y"])
                    diffs.setdefault("cheng_list", []).append({"dx": dx, "dy": dy, "dist": (dx**2+dy**2)**0.5})
            
            status = " | ".join(f"{k}={v['dist']:.0f}%" for k, v in diffs.items() if isinstance(v, dict))
            print(f"OK ({status})")
            
            results.append({
                "file": before_path.name,
                "ai": {k: v for k, v in ai_result.items() if k != "analysis"},
                "human": human_result,
                "ai_analysis": ai_result.get("analysis", ""),
                "diffs": diffs,
            })
        
        except Exception as e:
            print(f"FAIL ({e})")
    
    return results


def run_phase2_learn(results: List[Dict]) -> str:
    """Phase 2: 让大模型分析差异，学习规律，生成优化 prompt"""
    print(f"\nPhase 2: 分析差异，学习人工标注规律...")
    
    # 构建训练数据摘要
    training_data_parts = []
    for r in results:
        part = f"### {r['file']}\n"
        part += f"- AI 分析: {r.get('ai_analysis', 'N/A')[:200]}\n"
        part += f"- AI: qi=({r['ai'].get('qi',{}).get('x','?')},{r['ai'].get('qi',{}).get('y','?')}), "
        
        ai_cheng = r["ai"].get("cheng_list", [])
        if ai_cheng:
            cheng_str = ", ".join(f"({c['x']},{c['y']})" for c in ai_cheng)
            part += f"cheng=[{cheng_str}], "
        
        part += f"zhuan=({r['ai'].get('zhuan',{}).get('x','?')},{r['ai'].get('zhuan',{}).get('y','?')}), "
        part += f"he=({r['ai'].get('he',{}).get('x','?')},{r['ai'].get('he',{}).get('y','?')})\n"
        
        part += f"- 人工: qi=({r['human'].get('qi',{}).get('x','?')},{r['human'].get('qi',{}).get('y','?')}), "
        
        hu_cheng = r["human"].get("cheng_list", [])
        if hu_cheng:
            cheng_str = ", ".join(f"({c['x']},{c['y']})" for c in hu_cheng)
            part += f"cheng=[{cheng_str}], "
        
        part += f"zhuan=({r['human'].get('zhuan',{}).get('x','?')},{r['human'].get('zhuan',{}).get('y','?')}), "
        part += f"he=({r['human'].get('he',{}).get('x','?')},{r['human'].get('he',{}).get('y','?')})\n"
        
        if r["diffs"]:
            diff_strs = []
            for k, v in r["diffs"].items():
                if isinstance(v, dict):
                    diff_strs.append(f"{k}: dx={v['dx']:.0f}, dy={v['dy']:.0f}, dist={v['dist']:.0f}%")
            part += f"- 偏差: {', '.join(diff_strs)}\n"
        
        training_data_parts.append(part)
    
    training_data = "\n".join(training_data_parts)
    
    prompt = LEARN_PROMPT.format(
        current_prompt=CURRENT_PROMPT,
        training_data=training_data,
    )
    
    print("  调用 Qwen 分析中（可能需要1-2分钟）...", flush=True)
    
    result = call_qwen_text(prompt)
    
    return result


def main():
    max_samples = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("起承转合 Prompt 学习系统")
    print("=" * 60)
    
    if not settings.QWEN_API_KEY:
        print("错误: 未配置 QWEN_API_KEY")
        return
    
    # Phase 1: 收集对比数据
    results = run_phase1_collect(max_samples)
    
    if not results:
        print("没有可用的训练数据")
        return
    
    # 保存中间结果
    with open(DEMO_DIR.parent / "training_phase1_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nPhase 1 结果已保存: training_phase1_results.json")
    
    # Phase 2: 分析差异，学习规律
    learn_result = run_phase2_learn(results)
    
    # 保存学习结果
    learn_file = DEMO_DIR.parent / "training_learn_result.md"
    with open(learn_file, "w", encoding="utf-8") as f:
        f.write(learn_result)
    
    print(f"\n学习结果已保存: {learn_file}")
    print("\n" + "=" * 60)
    print("学习报告摘要:")
    print("=" * 60)
    
    # 打印前 2000 字
    print(learn_result[:2000])
    if len(learn_result) > 2000:
        print("\n... (完整内容见 training_learn_result.md)")


if __name__ == "__main__":
    main()
