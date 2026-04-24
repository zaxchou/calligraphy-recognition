"""
VL校验核心

对LLM分类结果中置信度低的区域，调用VL模型进行视觉校验。

策略：
1. 从原图裁切低置信度区域
2. 调用VL模型判断该区域类别
3. 综合VL判断和LLM判断，给出最终分类
4. 记录校验结果用于迭代学习

设计原则：
- 只在必要时调用VL，控制成本
- 裁切区域包含上下文（周围一定边距）
- VL判断作为辅助，不直接替代LLM
"""

import os
import json
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from app.core.config import get_settings
from app.tubi.llm_classifier import ClassifiedRegion, ClassificationResult


settings = get_settings()


@dataclass
class VerificationResult:
    """校验结果"""
    region_id: int
    vl_category: str
    vl_confidence: float
    final_category: str
    final_confidence: float
    used_vl: bool


def _crop_region_with_context(
    image_path: str,
    region_mask: np.ndarray,
    context_ratio: float = 0.15,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    裁切区域并保留上下文边距
    
    返回: (裁切图像, (x1, y1, x2, y2))
    """
    h, w = region_mask.shape[:2]
    ys, xs = np.where(region_mask > 0)
    
    if len(xs) == 0:
        return np.zeros((100, 100, 3), dtype=np.uint8), (0, 0, 100, 100)
    
    rx1, rx2 = int(xs.min()), int(xs.max())
    ry1, ry2 = int(ys.min()), int(ys.max())
    
    # 添加上下文边距
    margin_x = int((rx2 - rx1) * context_ratio)
    margin_y = int((ry2 - ry1) * context_ratio)
    
    cx1 = max(0, rx1 - margin_x)
    cy1 = max(0, ry1 - margin_y)
    cx2 = min(w, rx2 + margin_x)
    cy2 = min(h, ry2 + margin_y)
    
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        return np.zeros((100, 100, 3), dtype=np.uint8), (0, 0, 100, 100)
    
    cropped = img[cy1:cy2, cx1:cx2]
    return cropped, (cx1, cy1, cx2, cy2)


def _encode_image_to_base64(img_bgr: np.ndarray, max_side: int = 1024) -> str:
    """将图像编码为base64"""
    import base64
    import io
    from PIL import Image
    
    # 缩放
    h, w = img_bgr.shape[:2]
    long_edge = max(h, w)
    if long_edge > max_side:
        scale = max_side / float(long_edge)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # BGR -> RGB
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_vl_for_verification(cropped_image: np.ndarray) -> Optional[Dict]:
    """
    调用VL模型校验裁切区域
    
    使用简单的prompt，只判断类别
    """
    try:
        import httpx
        
        api_key = getattr(settings, "QWEN_API_KEY", "")
        base_url = getattr(settings, "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model = getattr(settings, "QWEN_MODEL", "qwen-vl-plus")
        
        if not api_key:
            return None
        
        base64_img = _encode_image_to_base64(cropped_image, max_side=1024)
        
        prompt = """这是一幅中国画作品的局部裁切图。请判断这个区域属于哪一类：

A. 题跋区域（书法文字、款识、题字）
B. 绘画区域（山水、花鸟、竹石等绘画主体）
C. 印章区域
D. 留白区域（空白纸张）

请只回答一个字母（A/B/C/D），并给出置信度（0-1）。格式：{"category": "A", "confidence": 0.85}"""
        
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }],
            "stream": False,
            "max_tokens": 512,
            "temperature": 0.0,
        }
        
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base_url.rstrip('/')}/chat/completions"
        
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # 解析结果
            content = content.strip()
            if "A" in content or "题跋" in content or "inscription" in content.lower():
                return {"category": "inscription", "confidence": 0.8}
            elif "B" in content or "绘画" in content or "painting" in content.lower():
                return {"category": "painting", "confidence": 0.8}
            elif "C" in content or "印章" in content or "seal" in content.lower():
                return {"category": "seal", "confidence": 0.8}
            elif "D" in content or "留白" in content or "blank" in content.lower():
                return {"category": "blank", "confidence": 0.8}
            
            # 尝试JSON解析
            try:
                parsed = json.loads(content)
                cat_map = {"A": "inscription", "B": "painting", "C": "seal", "D": "blank"}
                cat = cat_map.get(parsed.get("category", ""), "unknown")
                conf = float(parsed.get("confidence", 0.5))
                return {"category": cat, "confidence": conf}
            except:
                return {"category": "unknown", "confidence": 0.3}
    except Exception as e:
        print(f"ERROR: VL verification failed: {e}")
        return None


def verify_low_confidence_regions(
    image_path: str,
    classification: ClassificationResult,
    inscription_candidates: np.ndarray,
    confidence_threshold: float = 0.6,
    max_verify_count: int = 5,
) -> List[VerificationResult]:
    """
    对低置信度区域进行VL校验
    
    参数：
        image_path: 原始图像路径
        classification: LLM分类结果
        inscription_candidates: 题跋候选区域mask
        confidence_threshold: 低于此阈值才校验
        max_verify_count: 最多校验多少个区域
    
    返回：
        校验结果列表
    """
    results = []
    verified_count = 0
    
    for region in classification.regions:
        if region.confidence >= confidence_threshold:
            # 置信度足够高，无需校验
            results.append(VerificationResult(
                region_id=region.region_id,
                vl_category=region.category,
                vl_confidence=region.confidence,
                final_category=region.category,
                final_confidence=region.confidence,
                used_vl=False,
            ))
            continue
        
        if verified_count >= max_verify_count:
            # 超过最大校验数，保持原分类
            results.append(VerificationResult(
                region_id=region.region_id,
                vl_category="unknown",
                vl_confidence=0.0,
                final_category=region.category,
                final_confidence=region.confidence,
                used_vl=False,
            ))
            continue
        
        # 构建区域mask（从候选区域中提取该连通域）
        # 注意：这里简化处理，实际应该根据region_features中的位置信息重构mask
        # 由于region_features中没有精确位置，这里用inscription_candidates作为近似
        
        vl_result = _call_vl_for_verification_from_region(image_path, region)
        verified_count += 1
        
        if vl_result:
            # 综合LLM和VL判断
            vl_cat = vl_result["category"]
            vl_conf = vl_result["confidence"]
            
            # 如果VL和LLM一致，提升置信度
            if vl_cat == region.category:
                final_cat = region.category
                final_conf = min(1.0, region.confidence + vl_conf * 0.3)
            else:
                # 不一致时，取置信度更高的
                if vl_conf > region.confidence:
                    final_cat = vl_cat
                    final_conf = vl_conf * 0.9  # VL单独判断略有折扣
                else:
                    final_cat = region.category
                    final_conf = region.confidence
            
            results.append(VerificationResult(
                region_id=region.region_id,
                vl_category=vl_cat,
                vl_confidence=vl_conf,
                final_category=final_cat,
                final_confidence=final_conf,
                used_vl=True,
            ))
        else:
            # VL调用失败，保持原分类
            results.append(VerificationResult(
                region_id=region.region_id,
                vl_category="unknown",
                vl_confidence=0.0,
                final_category=region.category,
                final_confidence=region.confidence,
                used_vl=False,
            ))
    
    return results


def _call_vl_for_verification_from_region(image_path: str, region: ClassifiedRegion) -> Optional[Dict]:
    """
    从区域特征重构裁切图并调用VL
    
    简化实现：由于region_features中只有相对特征，没有精确像素坐标，
    这里使用一个简化的策略：如果region在题跋候选区域内，就裁切候选区域的一部分
    """
    try:
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            return None
        
        h, w = img.shape[:2]
        
        # 从相对位置重构大致的裁切区域
        offset_x = region.features.get("center_offset_x", 0)
        offset_y = region.features.get("center_offset_y", 0)
        area_ratio = region.features.get("area_ratio", 0.01)
        
        cx = int(w * 0.5 + offset_x * w * 0.5)
        cy = int(h * 0.5 + offset_y * h * 0.5)
        
        # 估算区域大小
        total_area = w * h
        region_area = int(total_area * area_ratio)
        side = int(np.sqrt(region_area))
        
        x1 = max(0, cx - side)
        y1 = max(0, cy - side)
        x2 = min(w, cx + side)
        y2 = min(h, cy + side)
        
        if x2 - x1 < 50 or y2 - y1 < 50:
            # 区域太小，扩大裁切
            x1 = max(0, cx - 100)
            y1 = max(0, cy - 100)
            x2 = min(w, cx + 100)
            y2 = min(h, cy + 100)
        
        cropped = img[y1:y2, x1:x2]
        return _call_vl_for_verification(cropped)
    except Exception as e:
        print(f"ERROR: Region verification failed: {e}")
        return None
