"""
起承转合 Prompt 训练脚本 v2
============================
改进版：用大模型对比 before/after，直接分析差异

流程：
1. 用当前 prompt 分析 before 图片 → 得到 AI 结果
2. 让大模型读取 after 图片 → 提取人工标注坐标
3. 对比差异，分析规律
4. 生成优化建议
"""

import base64
import cv2
import httpx
import json
import os
import re
import sys
import io
from pathlib import Path
from typing import Dict, List, Any, Optional

# Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
import numpy as np

settings = get_settings()
DEMO_DIR = Path(__file__).parent.parent.parent / "demojpg"

# 当前 prompt
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

# 提取 after 图标注的 prompt
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
    """读取图片并 base64 编码"""
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Cannot read image: {img_path}")
    
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 1024:
        scale = 1024 / max_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(image_b64: str, prompt: str, model: str = None) -> Dict[str, Any]:
    """调用 Qwen VL 分析图片"""
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
    
    raw_content = data["choices"][0]["message"]["content"]
    
    # 解析 JSON
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_content)
    if json_match:
        result = json.loads(json_match.group(1))
    else:
        result = json.loads(raw_content)
    
    return result, raw_content


def compare_points(ai_result: Dict, human_result: Dict) -> Dict[str, Any]:
    """对比 AI 和人工标注的差异"""
    diff = {}
    
    for key in ["qi", "zhuan", "he"]:
        if key in ai_result and key in human_result:
            ai_pt = ai_result[key]
            hu_pt = human_result[key]
            
            dx = abs(ai_pt["x"] - hu_pt["x"])
            dy = abs(ai_pt["y"] - hu_pt["y"])
            dist = (dx**2 + dy**2) ** 0.5
            
            diff[key] = {
                "ai": ai_pt,
                "human": hu_pt,
                "dx": dx,
                "dy": dy,
                "dist": dist,
            }
    
    # 承点对比
    if "cheng_list" in ai_result and "cheng_list" in human_result:
        ai_cheng = ai_result.get("cheng_list", [])
        hu_cheng = human_result.get("cheng_list", [])
        
        cheng_diffs = []
        for i, (ai_c, hu_c) in enumerate(zip(ai_cheng[:len(hu_cheng)], hu_cheng)):
            dx = abs(ai_c["x"] - hu_c["x"])
            dy = abs(ai_c["y"] - hu_c["y"])
            cheng_diffs.append({
                "index": i,
                "ai": ai_c,
                "human": hu_c,
                "dx": dx,
                "dy": dy,
                "dist": (dx**2 + dy**2) ** 0.5,
            })
        if cheng_diffs:
            diff["cheng_list"] = cheng_diffs
    
    return diff


def analyze_training_session(results: List[Dict]) -> str:
    """分析一轮训练的结果，生成优化建议"""
    qi_errors = []
    zhuan_errors = []
    he_errors = []
    cheng_errors = []
    
    for r in results:
        if "diff" in r:
            if "qi" in r["diff"]:
                qi_errors.append(r["diff"]["qi"]["dist"])
            if "zhuan" in r["diff"]:
                zhuan_errors.append(r["diff"]["zhuan"]["dist"])
            if "he" in r["diff"]:
                he_errors.append(r["diff"]["he"]["dist"])
            if "cheng_list" in r["diff"]:
                for c in r["diff"]["cheng_list"]:
                    cheng_errors.append(c["dist"])
    
    report = []
    report.append("=" * 60)
    report.append("训练结果分析")
    report.append("=" * 60)
    report.append(f"样本数: {len(results)}")
    report.append("")
    
    def format_stat(errors, name):
        if errors:
            avg = sum(errors) / len(errors)
            std = np.std(errors) if len(errors) > 1 else 0
            good = sum(1 for e in errors if e < 10)
            ok = sum(1 for e in errors if 10 <= e < 20)
            bad = sum(1 for e in errors if e >= 20)
            return f"{name}: 平均偏差 {avg:.1f}% (std={std:.1f}), 准确:{good} 一般:{ok} 偏差大:{bad}"
        return None
    
    for stat in [format_stat(qi_errors, "起点"),
                 format_stat(cheng_errors, "承点"),
                 format_stat(zhuan_errors, "转点"),
                 format_stat(he_errors, "合点")]:
        if stat:
            report.append(stat)
    
    report.append("")
    report.append("=" * 60)
    report.append("优化建议")
    report.append("=" * 60)
    
    suggestions = []
    
    if he_errors and sum(he_errors) / len(he_errors) > 15:
        suggestions.append("""
【合点偏差较大】建议强化以下规则：
1. 更明确地识别题款/印章位置（竖排文字、红色方形/圆形）
2. 强调合必须在题款附近（距离<10%）
3. 强调合与转形成回转闭合趋势，而非继续向外延伸
4. 示例：如果题款在右上角，合应靠近右上角而非左上角""")
    
    if zhuan_errors and sum(zhuan_errors) / len(zhuan_errors) > 15:
        suggestions.append("""
【转点偏差较大】建议强化：
1. 转应在主体焦点位置（花朵/鸟雀/叶密集处）
2. 转通常在画面中上部（y=20-40%）
3. 转是方向改变的关键点，不是简单的中间点""")
    
    if qi_errors and sum(qi_errors) / len(qi_errors) > 15:
        suggestions.append("""
【起点偏差较大】建议强化：
1. 起应在墨迹起始处（枝干根部）
2. 起通常在画面边缘角落
3. 起是视觉引导的入口，从边缘引入""")
    
    if not suggestions:
        suggestions.append("当前 prompt 效果较好，偏差都在可接受范围内。")
    
    report.extend(suggestions)
    return "\n".join(report)


def run_training_iteration(prompt: str, max_samples: int = None) -> List[Dict]:
    """运行一轮训练"""
    results = []
    
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    
    if max_samples:
        before_files = before_files[:max_samples]
    
    print(f"找到 {len(before_files)} 组训练数据")
    
    for i, before_path in enumerate(before_files):
        after_path = DEMO_DIR / before_path.name.replace("_before.png", "_after.png")
        
        if not after_path.exists():
            print(f"[{i+1}/{len(before_files)}] 跳过 {before_path.name}（无 after 文件）")
            continue
        
        print(f"\n[{i+1}/{len(before_files)}] 处理: {before_path.name}")
        
        try:
            # 1. AI 分析 before
            print("  -> 调用 Qwen VL 分析 before...")
            before_b64 = encode_image_to_base64(before_path)
            ai_result, ai_raw = call_qwen_vl(before_b64, prompt)
            print(f"  -> AI 结果: qi=({ai_result.get('qi',{}).get('x','?')},{ai_result.get('qi',{}).get('y','?')}) "
                  f"he=({ai_result.get('he',{}).get('x','?')},{ai_result.get('he',{}).get('y','?')})")
            
            # 2. 提取 after 中的人工标注
            print("  -> 调用 Qwen VL 提取 after 标注...")
            after_b64 = encode_image_to_base64(after_path)
            human_result, human_raw = call_qwen_vl(after_b64, EXTRACT_AFTER_PROMPT)
            print(f"  -> 人工标注: qi=({human_result.get('qi',{}).get('x','?')},{human_result.get('qi',{}).get('y','?')}) "
                  f"he=({human_result.get('he',{}).get('x','?')},{human_result.get('he',{}).get('y','?')})")
            
            # 3. 对比
            diff = compare_points(ai_result, human_result)
            
            # 打印关键差异
            status_parts = []
            for key in ["qi", "zhuan", "he"]:
                if key in diff:
                    d = diff[key]["dist"]
                    status = "OK" if d < 10 else "WARN" if d < 20 else "BAD"
                    status_parts.append(f"{key}:{d:.0f}%({status})")
            print(f"  -> 差异: {', '.join(status_parts)}")
            
            results.append({
                "file": before_path.name,
                "ai": ai_result,
                "human": human_result,
                "diff": diff,
                "ai_raw": ai_raw,
                "human_raw": human_raw,
            })
        
        except Exception as e:
            print(f"  -> 错误: {e}")
            import traceback
            traceback.print_exc()
    
    return results


def main():
    """主函数：迭代训练"""
    print("=" * 60)
    print("起承转合 Prompt 训练 v2")
    print("=" * 60)
    
    if not settings.QWEN_API_KEY:
        print("错误：未配置 QWEN_API_KEY")
        return
    
    # 第一轮：用当前 prompt（先用3张验证）
    max_samples = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"\n【第 1 轮训练】(样本数限制: {max_samples or '全部'})")
    results = run_training_iteration(CURRENT_PROMPT, max_samples=max_samples)
    
    if not results:
        print("没有成功处理的样本")
        return
    
    # 分析结果
    report = analyze_training_session(results)
    print("\n" + report)
    
    # 保存结果
    output_file = DEMO_DIR.parent / "training_results_round1.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n详细结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
