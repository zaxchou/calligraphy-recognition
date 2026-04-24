"""
起承转合 Prompt 训练脚本
========================
通过对比 AI 分析结果和人工标注，迭代优化 prompt。

流程：
1. 用当前 prompt 分析所有 before 图片
2. 从 after 图片中提取人工标注的坐标
3. 计算差异，分析规律
4. 生成优化建议
"""

import base64
import cv2
import httpx
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

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


def encode_image_to_base64(img_path: Path) -> str:
    """读取图片并 base64 编码"""
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Cannot read image: {img_path}")
    
    # 缩放到最大 1024
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 1024:
        scale = 1024 / max_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def call_qwen_vl(image_b64: str, prompt: str) -> Dict[str, Any]:
    """调用 Qwen VL 分析图片"""
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
    
    return result


def extract_points_from_after(img_path: Path) -> Optional[Dict[str, Any]]:
    """
    从 after 图片中提取人工标注的坐标。
    
    after 图片是带箭头标注的线稿图，我们需要检测：
    - 箭头的起点和终点
    - 标签（起/承/转/合）
    
    策略：检测箭头上的彩色圆圈和文字标签
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return None
    
    h, w = img.shape[:2]
    
    # 检测颜色标记点
    # 起: 红色 (229, 57, 53) BGR
    # 承: 橙色 (255, 152, 0) BGR
    # 转: 蓝色 (25, 118, 210) BGR
    # 合: 绿色 (46, 125, 50) BGR
    
    # 使用 BGR 直接检测颜色点
    # 起: 红色 (B=53, G=57, R=229)
    # 承: 橙色 (B=0, G=152, R=255)
    # 转: 蓝色 (B=210, G=118, R=25)
    # 合: 绿色 (B=50, G=125, R=46)
    
    colors_bgr = {
        "qi": (53, 57, 229),    # 红色 BGR
        "cheng": (0, 152, 255), # 橙色 BGR
        "zhuan": (210, 118, 25),# 蓝色 BGR
        "he": (50, 125, 46),    # 绿色 BGR
    }
    
    points = {}
    
    for name, target_color in colors_bgr.items():
        # 在 BGR 空间中查找接近的颜色
        b, g, r = target_color
        # 允许的误差范围
        tolerance = 50
        
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype=np.uint8)
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype=np.uint8)
        
        mask = cv2.inRange(img, lower, upper)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # 找最大的轮廓
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                points[name] = {
                    "x": int(cx * 100 / w),
                    "y": int(cy * 100 / h),
                    "pixel_x": cx,
                    "pixel_y": cy,
                }
    
    return points if points else None


def compare_points(ai_result: Dict, human_points: Dict) -> Dict[str, Any]:
    """对比 AI 和人工标注的差异"""
    diff = {}
    
    for key in ["qi", "zhuan", "he"]:
        if key in ai_result and key in human_points:
            ai_pt = ai_result[key]
            hu_pt = human_points[key]
            
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
    if "cheng_list" in ai_result:
        ai_cheng = ai_result["cheng_list"]
        if "cheng" in human_points:
            hu_cheng = human_points["cheng"]
            # 简化：只对比第一个承点
            if ai_cheng:
                dx = abs(ai_cheng[0]["x"] - hu_cheng["x"])
                dy = abs(ai_cheng[0]["y"] - hu_cheng["y"])
                diff["cheng"] = {
                    "ai": ai_cheng[0],
                    "human": hu_cheng,
                    "dx": dx,
                    "dy": dy,
                    "dist": (dx**2 + dy**2) ** 0.5,
                }
    
    return diff


def analyze_training_session(results: List[Dict]) -> str:
    """分析一轮训练的结果，生成优化建议"""
    # 统计各点的平均偏差
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
            if "cheng" in r["diff"]:
                cheng_errors.append(r["diff"]["cheng"]["dist"])
    
    report = []
    report.append("=" * 60)
    report.append("训练结果分析")
    report.append("=" * 60)
    report.append(f"样本数: {len(results)}")
    report.append("")
    
    if qi_errors:
        avg = sum(qi_errors) / len(qi_errors)
        report.append(f"起点平均偏差: {avg:.1f}% (标准差 {np.std(qi_errors):.1f})")
    
    if cheng_errors:
        avg = sum(cheng_errors) / len(cheng_errors)
        report.append(f"承点平均偏差: {avg:.1f}% (标准差 {np.std(cheng_errors):.1f})")
    
    if zhuan_errors:
        avg = sum(zhuan_errors) / len(zhuan_errors)
        report.append(f"转点平均偏差: {avg:.1f}% (标准差 {np.std(zhuan_errors):.1f})")
    
    if he_errors:
        avg = sum(he_errors) / len(he_errors)
        report.append(f"合点平均偏差: {avg:.1f}% (标准差 {np.std(he_errors):.1f})")
    
    report.append("")
    report.append("=" * 60)
    report.append("优化建议")
    report.append("=" * 60)
    
    # 分析偏差模式
    if he_errors and sum(he_errors) / len(he_errors) > 15:
        report.append("⚠️ 合点偏差较大，建议强化以下规则：")
        report.append("  1. 更明确地识别题款/印章位置")
        report.append("  2. 强调合必须在题款附近（距离<10%）")
        report.append("  3. 强调合与转形成回转闭合趋势")
    
    if zhuan_errors and sum(zhuan_errors) / len(zhuan_errors) > 15:
        report.append("⚠️ 转点偏差较大，建议强化：")
        report.append("  1. 转应在主体焦点位置（花朵/鸟雀/叶密集处）")
        report.append("  2. 转通常在画面中上部（y=20-40%）")
    
    if qi_errors and sum(qi_errors) / len(qi_errors) > 15:
        report.append("⚠️ 起点偏差较大，建议强化：")
        report.append("  1. 起应在墨迹起始处（枝干根部）")
        report.append("  2. 起通常在画面边缘角落")
    
    return "\n".join(report)


def run_training_iteration(prompt: str) -> List[Dict]:
    """运行一轮训练"""
    results = []
    
    # 找所有 before 图片
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    
    print(f"找到 {len(before_files)} 组训练数据")
    
    for before_path in before_files:
        # 对应的 after 文件
        after_path = DEMO_DIR / before_path.name.replace("_before.png", "_after.png")
        
        if not after_path.exists():
            print(f"跳过 {before_path.name}（无 after 文件）")
            continue
        
        print(f"\n处理: {before_path.name}")
        
        try:
            # 1. AI 分析 before
            img_b64 = encode_image_to_base64(before_path)
            ai_result = call_qwen_vl(img_b64, prompt)
            print(f"  AI 分析完成")
            
            # 2. 提取 after 中的人工标注
            human_points = extract_points_from_after(after_path)
            
            if human_points:
                print(f"  人工标注: {list(human_points.keys())}")
                
                # 3. 对比
                diff = compare_points(ai_result, human_points)
                
                results.append({
                    "file": before_path.name,
                    "ai": ai_result,
                    "human": human_points,
                    "diff": diff,
                })
                
                # 打印关键差异
                for key in ["qi", "zhuan", "he"]:
                    if key in diff:
                        d = diff[key]["dist"]
                        status = "✓" if d < 10 else "⚠" if d < 20 else "✗"
                        print(f"  {key}: 偏差 {d:.1f}% {status}")
            else:
                print(f"  无法提取人工标注")
        
        except Exception as e:
            print(f"  错误: {e}")
    
    return results


def main():
    """主函数：迭代训练"""
    print("=" * 60)
    print("起承转合 Prompt 训练")
    print("=" * 60)
    
    if not settings.QWEN_API_KEY:
        print("错误：未配置 QWEN_API_KEY")
        return
    
    # 第一轮：用当前 prompt
    print("\n【第 1 轮训练】")
    results = run_training_iteration(CURRENT_PROMPT)
    
    # 分析结果
    report = analyze_training_session(results)
    print("\n" + report)
    
    # 保存结果
    output_file = DEMO_DIR.parent / "training_results_round1.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    import numpy as np
    import sys
    import io
    # Windows 控制台编码修复
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    main()
