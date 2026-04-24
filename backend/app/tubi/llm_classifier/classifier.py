"""
LLM语义分类器核心

基于CV输出的候选区域特征向量，调用LLM进行语义分类。
分类逻辑：
1. 将CV特征和画群规律组织成prompt
2. 调用LLM判断每个候选区域的类别（题跋/绘画/留白/印章）
3. 解析LLM输出，计算置信度
4. 低置信度区域标记为待校验

设计原则：
- LLM只看数值特征，不看图像
- 所有特征都是相对值
- 注入当前画群的规律作为上下文
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.core.config import get_settings
from app.tubi.preprocessing import StandardizedImage, GroupClassification
from app.tubi.cv_mask_extractor import MaskSet
from .rule_library import load_rule_library, RuleLibrary


settings = get_settings()


@dataclass
class ClassifiedRegion:
    """分类后的区域"""
    region_id: int
    category: str          # inscription / painting / blank / seal / unknown
    confidence: float      # 0-1
    features: Dict         # 原始特征
    reason: str            # 分类理由
    needs_verification: bool  # 是否需要VL校验


@dataclass
class ClassificationResult:
    """分类结果"""
    regions: List[ClassifiedRegion]
    overall_confidence: float
    low_confidence_count: int
    summary: str


def _build_classification_prompt(
    group: GroupClassification,
    features: List[Dict],
    rule_library: RuleLibrary,
    image_stats: Dict,
) -> str:
    """
    构建LLM分类prompt
    
    包含：
    1. 画作特征上下文
    2. 画群规律
    3. 候选区域特征列表
    4. 分类要求
    """
    group_name = group.primary_group.value
    group_rules = rule_library.get_rules_for_group(group_name)
    
    rules_text = "\n".join([f"- {r}" for r in group_rules])
    
    # 特征列表
    features_text = ""
    for i, f in enumerate(features[:30]):  # 最多30个区域，避免超出token限制
        src = f.get('source', 'unknown')
        src_note = "[CV初判:题跋候选]" if src == "inscription_candidate" else "[CV初判:绘画候选]"
        features_text += f"""
区域{i} {src_note}:
  - 面积占比: {f.get('area_ratio', 0):.4f}
  - 中心偏移X: {f.get('center_offset_x', 0):.3f} (0=中心, ±1=边缘)
  - 中心偏移Y: {f.get('center_offset_y', 0):.3f}
  - 长宽比: {f.get('aspect_ratio', 0):.2f}
  - 墨迹密度: {f.get('density', 0):.3f}
  - 印章重叠度: {f.get('seal_overlap', 0):.3f}
  - 文字重叠度: {f.get('text_overlap', 0):.3f}
  - 纹理密度(相对): {f.get('texture_relative', 0):.3f}
"""
    
    prompt = f"""你是一位专业的中国画题跋分析专家。请根据以下CV计算机视觉提取的候选区域特征，判断每个区域属于哪一类。

## 当前画作特征
- 画群分类: {group_name}
- 亮度中位数: {image_stats.get('brightness_median', 0):.1f}
- 饱和度中位数: {image_stats.get('saturation_median', 0):.1f}
- 纹理复杂度: {image_stats.get('texture_complexity', 0):.0f}
- 对比度: {image_stats.get('contrast_score', 0):.1f}

## 该画群的题跋/绘画规律
{rules_text}

## 候选区域特征（共{len(features)}个，显示前{min(30, len(features))}个）
{features_text}

## 分类要求
对每个区域，判断其类别：
- "inscription" = 题跋区域（书法文字、款识）
- "painting" = 绘画区域（山水、花鸟、竹石等主体）
- "seal" = 印章区域
- "blank" = 留白区域
- "unknown" = 不确定

## 输出格式（JSON）
```json
{{
    "classifications": [
        {{"region_id": 0, "category": "inscription", "confidence": 0.92, "reason": "面积小，长宽比高，位于画面右侧边缘，文字重叠度高"}},
        {{"region_id": 1, "category": "painting", "confidence": 0.88, "reason": "面积大，位于画面中心，纹理密度中等"}}
    ],
    "overall_confidence": 0.85,
    "summary": "题跋位于右上和左下，绘画占据主体..."
}}
```

注意：
1. confidence 必须是 0-1 的浮点数
2. 必须返回所有区域的分类结果
3. confidence < 0.6 的区域应该标记为 unknown
"""
    return prompt


def _call_llm_for_classification(prompt: str) -> Optional[Dict]:
    """
    调用LLM进行分类
    
    复用现有的硅基流动/Qwen API调用逻辑
    """
    try:
        import httpx
        import time
        
        # 使用与现有系统相同的模型配置
        model = getattr(settings, "QWEN_MODEL", "qwen-vl-plus")
        api_key = getattr(settings, "QWEN_API_KEY", "")
        base_url = getattr(settings, "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        if not api_key:
            print("WARNING: QWEN_API_KEY not set, using mock classification")
            return None
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 8192,
            "temperature": 0.1,
        }
        
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url.rstrip('/')}/chat/completions"
        
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=120.0)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 解析JSON
            try:
                parsed = json.loads(content.strip())
                return parsed
            except json.JSONDecodeError:
                # 尝试从markdown代码块中提取
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_str = content[json_start:json_end].strip()
                    return json.loads(json_str)
                return None
    except Exception as e:
        print(f"ERROR: LLM classification failed: {e}")
        return None


def _fallback_classification(features: List[Dict]) -> List[ClassifiedRegion]:
    """
    LLM调用失败时的降级分类策略
    
    基于规则的简单分类：
    - 印章重叠度高 -> seal
    - 文字重叠度高 + 长宽比大 -> inscription
    - 面积大 + 中心偏移小 -> painting
    - 其他 -> unknown
    """
    regions = []
    for i, f in enumerate(features):
        seal_overlap = f.get('seal_overlap', 0)
        text_overlap = f.get('text_overlap', 0)
        area_ratio = f.get('area_ratio', 0)
        aspect_ratio = f.get('aspect_ratio', 0)
        density = f.get('density', 0)
        
        if seal_overlap > 0.3:
            category = "seal"
            confidence = min(0.9, 0.5 + seal_overlap)
            reason = f"印章重叠度高({seal_overlap:.2f})"
        elif text_overlap > 0.2 and aspect_ratio > 1.5:
            category = "inscription"
            confidence = min(0.85, 0.5 + text_overlap)
            reason = f"文字重叠度高({text_overlap:.2f})，长宽比大({aspect_ratio:.1f})"
        elif area_ratio > 0.1 and density < 0.5:
            category = "painting"
            confidence = min(0.8, 0.4 + area_ratio * 2)
            reason = f"面积大({area_ratio:.4f})，密度中等"
        else:
            category = "unknown"
            confidence = 0.3
            reason = "特征不明确，需要校验"
        
        regions.append(ClassifiedRegion(
            region_id=i,
            category=category,
            confidence=confidence,
            features=f,
            reason=reason,
            needs_verification=(confidence < 0.6),
        ))
    
    return regions


def classify_regions(
    std_img: StandardizedImage,
    group: GroupClassification,
    masks: MaskSet,
    use_llm: bool = True,
) -> ClassificationResult:
    """
    主入口：对CV提取的候选区域进行分类
    
    参数：
        std_img: 标准化图像
        group: 画群分类结果
        masks: CV mask集合
        use_llm: 是否使用LLM分类（False时用规则降级）
    
    返回：
        ClassificationResult对象
    """
    features = masks.region_features
    
    if not features:
        return ClassificationResult(
            regions=[],
            overall_confidence=0.0,
            low_confidence_count=0,
            summary="未检测到候选区域",
        )
    
    # 加载规律库
    rule_library = load_rule_library()
    
    # 构建图像统计信息
    image_stats = {
        "brightness_median": std_img.brightness_median,
        "saturation_median": std_img.saturation_median,
        "texture_complexity": std_img.texture_complexity,
        "contrast_score": std_img.contrast_score,
    }
    
    if use_llm:
        prompt = _build_classification_prompt(group, features, rule_library, image_stats)
        llm_result = _call_llm_for_classification(prompt)
    else:
        llm_result = None
    
    if llm_result and "classifications" in llm_result:
        # 解析LLM结果
        regions = []
        low_confidence_count = 0
        
        for c in llm_result["classifications"]:
            region_id = c.get("region_id", 0)
            if region_id < len(features):
                confidence = float(c.get("confidence", 0.5))
                region = ClassifiedRegion(
                    region_id=region_id,
                    category=c.get("category", "unknown"),
                    confidence=confidence,
                    features=features[region_id],
                    reason=c.get("reason", ""),
                    needs_verification=(confidence < 0.6),
                )
                regions.append(region)
                if confidence < 0.6:
                    low_confidence_count += 1
        
        overall_confidence = float(llm_result.get("overall_confidence", 0.5))
        summary = llm_result.get("summary", "")
    else:
        # LLM失败，使用降级策略
        print("WARNING: LLM classification failed, using fallback rules")
        regions = _fallback_classification(features)
        low_confidence_count = sum(1 for r in regions if r.confidence < 0.6)
        overall_confidence = sum(r.confidence for r in regions) / len(regions) if regions else 0.0
        summary = "LLM分类失败，使用规则降级策略"
    
    return ClassificationResult(
        regions=regions,
        overall_confidence=overall_confidence,
        low_confidence_count=low_confidence_count,
        summary=summary,
    )
