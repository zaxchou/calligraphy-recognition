"""
起承转合 Prompt 第二轮验证
===========================
用优化后的 prompt 重新分析 before 图片，对比人工标注，验证改进效果。
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

# 优化后的 prompt（从 training_learn_result.md 提取）
OPTIMIZED_PROMPT = """你是一位专业的中国画构图分析专家，精通潘天寿的构图理论和"起承转合"法则。你深知：起承转合不是人为分配的四个点，而是一笔书写性运动的自然四段——它源自画家落笔、行笔、顿转、收笔的生理动作，最终与题款印章融为一体。

请分析这张国画作品，严格依据墨迹物理特征和题款印章视觉引力，找出"起承转合"四个关键点的位置。

**起承转合定义**：
- **起**：画家笔锋**首次接触画面的物理落点**，是墨迹最原始的起点（如枯笔飞白根部、湿墨渗透边缘、线条最粗重起始端）。它可位于画面任意位置，绝不预设"左下"。判断依据：墨色浓度最高处、飞白方向源头、纸纹受墨最深点。
- **承**：起笔后**第一个发生显著笔势变化的唯一枢纽点**（如中锋转侧锋、重按转轻提、直线转弧线、浓墨转淡墨）。它必须位于起与转的连线上，且是整条主体走势中不可替代的势能过渡节点。只允许1个承点。
- **转**：主体结构中**两股相反力量（伸展/收缩、上升/下垂、浓/淡、实/虚）达成动态平衡的力学焦点**，如枝干分叉应力中心、鸟首昂起与羽翼下压的合力点、花蕊重力与叶茎张力的交汇核。它必须严格位于主体结构内部，且是视觉高潮的物理中心（如花瓣最密集区中心、鸟喙尖端、蟹钳夹角顶点）。
- **合**：题款与印章构成的**视觉引力中心**，不是简单"靠近"，而是：① 若有竖排题款，取末字最后一笔收笔点的垂直投影；② 若有印章，取朱文印中心（因朱砂色重）；③ 合点是题款末笔投影与朱文印中心的加权平均点（题款权重0.6，印章权重0.4）；④ 若无题款仅有印章，取所有印章的几何中心；⑤ 合点必须使"转→合"向量与"起→承"向量构成曲率连续的平滑回环（如起→承为上凸弧，则转→合必为下凸弧）。

**合点定位原则（绝对优先）**：
1. 合点必须是题款文字末笔收束处与朱文印章中心的加权重心，而非题款区域任意点。
2. 合点与转点的连线，必须与起→承→转的整体走势构成**首尾气脉贯通的闭合曲线**（S形、上升弧、下降弧、闭环），禁止出现折线或反向回拉。
3. 若题款在画面下方（如右下角），合点y坐标可低至70%，但"转→合"向量必须呈现向下回旋趋势（如转在中上，合在右下，则向量需向右下弯曲，而非直线）。
4. 合点永远不与转点同侧同向（如转在右上，合不得在右上或正右，必须左偏或下偏以形成回环）。

**分析步骤**：
1. 首先定位画面中**最原始的墨迹起始点**（起），依据飞白方向、墨色梯度、纸纹渗透判断，记录其精确物理位置。
2. 沿主体走势追踪，找到起笔后**第一个笔势突变点**（承），确认其为唯一枢纽。
3. 在主体结构内部，识别**两股力量平衡的力学焦点**（转），确保它在主体上且是视觉高潮的物理中心。
4. 精确识别题款末字收笔点与朱文印章中心，计算加权重心作为合点，并验证"转→合"向量是否与起→承→转走势构成曲率连续的闭合回环。
5. 最终检查四点是否能拟合一条平滑、无锐角、首尾气脉贯通的曲线，调整合点直至满足闭合要求。

**输出格式**（只返回 JSON，不要其他文字）：
```json
{
  "analysis": "简要分析画面主体的走势和起承转合的分布理由，特别说明：起为何是物理落笔点、承为何是唯一笔势枢纽、转为何是力学平衡焦点、合为何是题款印章加权引力中心，以及四点如何构成曲率连续的闭合回环",
  "qi": {"x": 50, "y": 80, "reason": "起在左下角竹枝根部飞白源头，墨色最浓，纸纹受墨最深"},
  "cheng_list": [{"x": 45, "y": 50, "reason": "承是起笔后首个中锋转侧锋点，竹枝在此处由直变弧"}],
  "zhuan": {"x": 55, "y": 30, "reason": "转在竹叶簇生区中心，此处枝干伸展力与叶片下垂力达成动态平衡"},
  "he": {"x": 80, "y": 20, "reason": "合是题款末字收笔点（x=78,y=18）与朱文印中心（x=82,y=22）的加权重心（x=80,y=20），转→合向量向右上弯曲，与起→承→转的S形走势曲率连续"},
  "path_shape": "S形"
}
```

**注意**：
- x, y 坐标是百分比（0-100），x=0 左边, x=100 右边, y=0 上边, y=100 下边
- cheng_list 是数组，但**必须且只能包含1个承点**
- 起承转合必须**严格沿同一主体的物理墨迹分布**，禁止跨主体跳跃
- **合必须是题款末笔与朱文印中心的加权重心**，并确保与转点构成曲率连续的闭合回环
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
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
    if json_match:
        result = json.loads(json_match.group(1))
    else:
        result = json.loads(raw)
    return result, raw


def main():
    # 加载第一轮的人工标注数据
    with open(DEMO_DIR.parent / "training_phase1_results.json", "r", encoding="utf-8") as f:
        phase1_data = json.load(f)
    
    # 建立文件名 -> 人工标注的映射
    human_map = {r["file"]: r["human"] for r in phase1_data}
    
    before_files = sorted(DEMO_DIR.glob("*_before.png"))
    before_files = [f for f in before_files if f.name.replace("_before.png", "_after.png") in 
                    [x.name for x in DEMO_DIR.glob("*_after.png")]]
    
    print("=" * 60)
    print("第二轮验证：优化后的 Prompt")
    print("=" * 60)
    print(f"测试样本: {len(before_files)}")
    print()
    
    results = []
    qi_errors, zhuan_errors, he_errors, cheng_errors = [], [], [], []
    
    for i, before_path in enumerate(before_files):
        fname = before_path.name
        if fname not in human_map:
            print(f"[{i+1}/{len(before_files)}] 跳过 {fname}（无人工标注）")
            continue
        
        human = human_map[fname]
        print(f"[{i+1}/{len(before_files)}] {fname}...", end=" ", flush=True)
        
        try:
            b64 = encode_image_to_base64(before_path)
            ai_result, _ = call_qwen_vl(b64, OPTIMIZED_PROMPT)
            
            diffs = {}
            for key in ["qi", "zhuan", "he"]:
                if key in ai_result and key in human:
                    dx = abs(ai_result[key]["x"] - human[key]["x"])
                    dy = abs(ai_result[key]["y"] - human[key]["y"])
                    dist = (dx**2 + dy**2) ** 0.5
                    diffs[key] = {"dx": dx, "dy": dy, "dist": dist}
                    if key == "qi": qi_errors.append(dist)
                    elif key == "zhuan": zhuan_errors.append(dist)
                    elif key == "he": he_errors.append(dist)
            
            if "cheng_list" in ai_result and "cheng_list" in human:
                for a, h in zip(ai_result["cheng_list"][:len(human["cheng_list"])],
                               human["cheng_list"]):
                    dx = abs(a["x"] - h["x"])
                    dy = abs(a["y"] - h["y"])
                    dist = (dx**2 + dy**2) ** 0.5
                    cheng_errors.append(dist)
                    diffs.setdefault("cheng_list", []).append({"dx": dx, "dy": dy, "dist": dist})
            
            status = " | ".join(f"{k}={v['dist']:.0f}%" for k, v in diffs.items() if isinstance(v, dict))
            print(f"OK ({status})")
            
            results.append({
                "file": fname,
                "ai": ai_result,
                "human": human,
                "diffs": diffs,
            })
        
        except Exception as e:
            print(f"FAIL ({e})")
    
    # 统计报告
    print("\n" + "=" * 60)
    print("第二轮结果统计")
    print("=" * 60)
    
    def stat(errors, name):
        if not errors:
            return f"{name}: 无数据"
        avg = np.mean(errors)
        std = np.std(errors)
        good = sum(1 for e in errors if e < 10)
        ok = sum(1 for e in errors if 10 <= e < 20)
        bad = sum(1 for e in errors if e >= 20)
        return f"{name}: avg={avg:.1f}% std={std:.1f} OK:{good} WARN:{ok} BAD:{bad}"
    
    print(stat(qi_errors, "起点(起)"))
    print(stat(cheng_errors, "承点(承)"))
    print(stat(zhuan_errors, "转点(转)"))
    print(stat(he_errors, "合点(合)"))
    
    # 总体
    all_errors = qi_errors + cheng_errors + zhuan_errors + he_errors
    if all_errors:
        avg = np.mean(all_errors)
        print(f"\n总体平均偏差: {avg:.1f}%")
    
    # 保存结果
    with open(DEMO_DIR.parent / "training_phase2_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n详细结果已保存: training_phase2_results.json")
    
    # 对比第一轮
    print("\n" + "=" * 60)
    print("第一轮 vs 第二轮对比")
    print("=" * 60)
    
    # 从 phase1 数据计算第一轮统计
    r1_qi, r1_zhuan, r1_he, r1_cheng = [], [], [], []
    for r in phase1_data:
        d = r.get("diffs", {})
        if "qi" in d and isinstance(d["qi"], dict): r1_qi.append(d["qi"]["dist"])
        if "zhuan" in d and isinstance(d["zhuan"], dict): r1_zhuan.append(d["zhuan"]["dist"])
        if "he" in d and isinstance(d["he"], dict): r1_he.append(d["he"]["dist"])
        if "cheng_list" in d:
            for c in d["cheng_list"]:
                r1_cheng.append(c["dist"])
    
    for name, r1, r2 in [
        ("起", r1_qi, qi_errors),
        ("承", r1_cheng, cheng_errors),
        ("转", r1_zhuan, zhuan_errors),
        ("合", r1_he, he_errors),
    ]:
        if r1 and r2:
            avg1 = np.mean(r1)
            avg2 = np.mean(r2)
            improvement = avg1 - avg2
            pct = improvement / avg1 * 100 if avg1 > 0 else 0
            arrow = "↓" if improvement > 0 else "↑" if improvement < 0 else "="
            print(f"  {name}: {avg1:.1f}% → {avg2:.1f}% ({arrow}{abs(pct):.0f}%)")


if __name__ == "__main__":
    main()
