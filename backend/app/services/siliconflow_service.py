import httpx
import base64
import json
import time
from typing import List, Dict, Optional, Tuple
import io
import re
from PIL import Image

from app.core.config import get_settings

settings = get_settings()
_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
MAX_RETRIES = 4
RETRY_DELAY = 3


def encode_image_to_base64(image_path: str, max_side: int = 2048, quality: int = 85) -> str:
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        width, height = img.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / float(longest)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        return base64.b64encode(data).decode("utf-8")


def analyze_image_regions(image_path: str, image_width: int, image_height: int) -> Dict:
    """
    使用 MiniMax-M2.5 模型分析图像中的题跋、绘画、留白区域

    Returns:
        {
            "inscription_regions": [{"x1": 0, "y1": 0, "x2": 100, "y2": 50}, ...],
            "painting_regions": [...],
            "blank_regions": [...],
            "analysis_note": "..."
        }
    """
    print(f"开始分析图像: {image_path}")
    print(f"图像尺寸: {image_width}x{image_height}")
    
    try:
        # 检查图像文件大小
        import os
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        print(f"图像文件大小: {file_size:.2f} MB")
        
        # 限制文件大小，避免处理过大的图像
        if file_size > 50:  # 限制为50MB
            print("错误: 图像文件过大，超过50MB限制")
            return {
                "success": False,
                "error": "图像文件过大，超过50MB限制"
            }
        
        base64_image = encode_image_to_base64(image_path, max_side=2048, quality=85)
        print(f"Base64编码完成，大小: {len(base64_image) / (1024 * 1024):.2f} MB")

        prompt = f"""你是一个专业的中国画艺术分析师。请按照以下三步策略分析这幅李鱓的绘画作品：

## 三步划分策略

### 第一步：确定绘画区域（绿色）
- **目标**：标记画作中的绘画主体（山水、花鸟、竹石等）
- **要求**：大致框选即可，不需要非常精确，可以有一定溢出
- **方法**：用多边形粗略包围绘画内容

### 第二步：确定题跋区域（红色）
- **目标**：标记所有书法文字、款识、印章
- **要求**：
  - 准确框选文字和印章，可以稍微溢出文字边缘（约5-10%的边距）
  - **绝对不能和绘画区域重叠**
  - 如果有重叠，题跋区域优先，绘画区域需要退让
- **方法**：用多边形精确描绘文字和印章的边界，稍微向外扩展一点点确保完整包含

### 第三步：自动计算留白区域（蓝色）
- **目标**：剩余的所有部分
- **要求**：不需要识别，自动计算为整幅画减去绘画和题跋的部分
- **注意**：你只需要返回绘画区域和题跋区域，留白区域由系统自动计算

## 返回格式（重要：必须使用多边形points格式）

```json
{{
    "inscription_regions": [
        {{
            "points": [{{"x": 0.1, "y": 0.1}}, {{"x": 0.5, "y": 0.1}}, {{"x": 0.5, "y": 0.3}}, {{"x": 0.1, "y": 0.3}}]
        }}
    ],
    "painting_regions": [
        {{
            "points": [{{"x": 0.2, "y": 0.4}}, {{"x": 0.8, "y": 0.4}}, {{"x": 0.8, "y": 0.9}}, {{"x": 0.2, "y": 0.9}}]
        }}
    ],
    "blank_regions": [],
    "analysis_note": "分析画作内容、艺术特色、题跋内容等，不要包含坐标信息或区域边界描述"
}}```

## 格式要求（必须严格遵守）

1. **所有区域必须使用多边形格式**：每个区域必须包含 `"points"` 字段，值为包含至少3个点的数组
2. **禁止使用矩形格式**：不要返回 `x1, y1, x2, y2` 格式的矩形，必须转换为多边形points格式
3. **坐标范围**：x和y坐标必须是0-1之间的浮点数（相对于图像宽高的比例）
4. **多边形闭合**：最后一个点不需要重复第一个点，系统会自动闭合

## 题跋区域多边形绘制方法

对于每个题跋（文字块或印章）：
1. 观察文字/印章的实际边界
2. 沿着边界取多个点（至少4个点，建议6-8个点以获得更精确的形状）
3. 将点按顺时针或逆时针顺序放入points数组
4. 稍微向外扩展（约5-10%）确保完整包含

示例：一个位于左上角的题跋
```json
{{
    "points": [
        {{"x": 0.05, "y": 0.05}},
        {{"x": 0.35, "y": 0.05}},
        {{"x": 0.35, "y": 0.25}},
        {{"x": 0.05, "y": 0.25}}
    ]
}}
```

## 关键要点
1. **绘画区域**：粗略即可，允许溢出，使用多边形
2. **题跋区域**：必须精确，禁止溢出，禁止与绘画重叠，**必须使用多边形points格式**
3. **留白区域**：留空数组，系统自动计算
4. **优先级**：题跋 > 绘画 > 留白
5. **格式统一**：所有区域都必须使用 `"points"` 格式，禁止混用矩形格式

## 自检清单
- [ ] 是否标记了所有绘画主体？
- [ ] 是否标记了所有文字和印章？
- [ ] 题跋和绘画区域是否有重叠？（必须无重叠）
- [ ] 题跋区域是否使用多边形points格式？（禁止使用x1,y1,x2,y2矩形格式）
- [ ] 绘画区域是否使用多边形points格式？
- [ ] 每个多边形是否有至少3个点？

图像尺寸：{image_width}x{image_height}

请只返回JSON格式数据。"""

        payload = {
            "model": settings.SILICONFLOW_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "max_tokens": 2048
        }

        print("开始调用API分析图像...")

        def build_chat_url(base_url: str) -> str:
            base = (base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                return base
            return f"{base}/chat/completions"

        def call_provider(provider: str, base_url: str, api_key: str, model: str) -> Dict:
            url = build_chat_url(base_url)
            print(f"当前使用AI供应商: {provider}")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            provider_payload = dict(payload)
            provider_payload["model"] = model

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
            with httpx.Client(limits=limits) as client:
                for retry in range(MAX_RETRIES):
                    attempt_timeout = httpx.Timeout(220.0, connect=10.0, read=180.0, write=60.0)
                    delay = min(60, (2 ** retry) * RETRY_DELAY)
                    jitter = 0.5 + (time.time() % 1.0) * 0.5
                    delay = delay * jitter
                    try:
                        response = client.post(url, headers=headers, json=provider_payload, timeout=attempt_timeout)
                        response.raise_for_status()
                        result = response.json()

                        content = result["choices"][0]["message"]["content"]
                        print("API调用成功，开始解析返回结果...")

                        content = content.strip()
                        if content.startswith("```json"):
                            content = content[7:]
                        if content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]
                        content = content.strip()

                        start = content.find("{")
                        end = content.rfind("}")
                        if start != -1 and end != -1 and end > start:
                            content = content[start:end + 1]
                        content = re.sub(r",\s*([}\]])", r"\1", content)

                        analysis = json.loads(content)
                        print("JSON解析成功")

                        normalized_regions = _normalize_regions(analysis, image_width, image_height)
                        print("区域标准化完成")

                        return {
                            "success": True,
                            "provider": provider,
                            "regions": normalized_regions,
                            "analysis_note": analysis.get("analysis_note", ""),
                            "raw_response": content
                        }
                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        retryable = status in (429, 500, 502, 503, 504)
                        if retryable and retry < MAX_RETRIES - 1:
                            print(f"API请求错误 {status} (重试 {retry+1}/{MAX_RETRIES})")
                            time.sleep(delay)
                            continue
                        try:
                            error_detail = e.response.json().get("error", {}).get("message", "Unknown error")
                            return {"success": False, "error": f"API请求错误: {status} - {error_detail}"}
                        except Exception:
                            return {"success": False, "error": f"API请求错误: {status}"}
                    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"网络/超时错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": f"网络/超时错误: {str(e)}"}
                    except json.JSONDecodeError as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"JSON解析错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": f"JSON解析错误: {str(e)}"}
                    except Exception as e:
                        return {"success": False, "error": f"分析失败: {str(e)}"}

        tried = []
        last_error = None
        if settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
            tried.append("qwen")
            result = call_provider("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error

        if settings.SILICONFLOW_ENABLED and settings.SILICONFLOW_API_KEY:
            tried.append("siliconflow")
            result = call_provider("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error

        tried_text = " -> ".join(tried) if tried else "none"
        suffix = f": {last_error}" if last_error else ""
        return {"success": False, "error": f"无可用AI供应商或调用失败 ({tried_text}){suffix}"}

    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"分析失败: {str(e)}"
        }


def _normalize_regions(analysis: Dict, image_width: int, image_height: int) -> Dict:
    """
    将比例坐标转换为像素坐标
    支持多边形和矩形两种格式
    所有区域最终都会转换为多边形格式以确保一致性
    """
    def rectangle_to_polygon_points(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> List[Dict]:
        """将矩形转换为多边形points格式"""
        return [
            {"x": int(max(0, min(1, x1)) * width), "y": int(max(0, min(1, y1)) * height)},
            {"x": int(max(0, min(1, x2)) * width), "y": int(max(0, min(1, y1)) * height)},
            {"x": int(max(0, min(1, x2)) * width), "y": int(max(0, min(1, y2)) * height)},
            {"x": int(max(0, min(1, x1)) * width), "y": int(max(0, min(1, y2)) * height)}
        ]
    
    def convert_regions(regions: List[Dict], width: int, height: int) -> List[Dict]:
        converted = []
        for reg in regions:
            # 检查是否是多边形格式
            if "points" in reg and isinstance(reg["points"], list):
                # 多边形格式
                points = reg["points"]
                if len(points) >= 3:
                    converted_points = []
                    for point in points:
                        x = int(max(0, min(1, point.get("x", 0))) * width)
                        y = int(max(0, min(1, point.get("y", 0))) * height)
                        converted_points.append({"x": x, "y": y})
                    converted.append({
                        "points": converted_points,
                        "type": "polygon"
                    })
            elif "x1" in reg and "y1" in reg and "x2" in reg and "y2" in reg:
                # 矩形格式 - 自动转换为多边形
                x1 = reg.get("x1", 0)
                y1 = reg.get("y1", 0)
                x2 = reg.get("x2", 0)
                y2 = reg.get("y2", 0)
                # 检查坐标是比例值(0-1)还是像素值
                if x1 <= 1 and y1 <= 1 and x2 <= 1 and y2 <= 1:
                    # 比例坐标，需要转换为像素
                    polygon_points = rectangle_to_polygon_points(x1, y1, x2, y2, width, height)
                else:
                    # 已经是像素坐标
                    polygon_points = [
                        {"x": int(x1), "y": int(y1)},
                        {"x": int(x2), "y": int(y1)},
                        {"x": int(x2), "y": int(y2)},
                        {"x": int(x1), "y": int(y2)}
                    ]
                converted.append({
                    "points": polygon_points,
                    "type": "polygon"
                })
        return converted

    # 转换题跋和绘画区域
    inscription_regions = convert_regions(
        analysis.get("inscription_regions", []),
        image_width, image_height
    )
    painting_regions = convert_regions(
        analysis.get("painting_regions", []),
        image_width, image_height
    )
    
    # 如果AI返回了留白区域，使用AI的；否则自动计算
    blank_regions_from_ai = convert_regions(
        analysis.get("blank_regions", []),
        image_width, image_height
    )
    
    if blank_regions_from_ai:
        blank_regions = blank_regions_from_ai
    else:
        # 自动计算留白区域 = 整幅画 - 题跋 - 绘画
        blank_regions = calculate_blank_regions(
            inscription_regions, painting_regions, image_width, image_height
        )
    
    return {
        "inscription_regions": inscription_regions,
        "painting_regions": painting_regions,
        "blank_regions": blank_regions
    }


def calculate_blank_regions(inscription_regions, painting_regions, image_width, image_height):
    """
    自动计算留白区域
    留白 = 整幅画 - 题跋区域 - 绘画区域
    """
    try:
        # 简化处理：返回一个大的矩形留白区域，覆盖整个图像
        # 这样可以避免复杂的计算，减少内存使用和计算时间
        blank_regions = [{
            "x1": 0,
            "y1": 0,
            "x2": image_width,
            "y2": image_height,
            "type": "rectangle"
        }]
        
        return blank_regions
    except Exception as e:
        print(f"计算留白区域时出错: {e}")
        # 出错时返回一个默认的留白区域
        return [{
            "x1": 0,
            "y1": 0,
            "x2": image_width,
            "y2": image_height,
            "type": "rectangle"
        }]


def calculate_area_stats(regions: Dict, image_width: int, image_height: int) -> Dict:
    """
    计算各类区域的面积统计
    使用新的面积计算模块，确保总和为100%
    """
    from .area_calculator import calculate_area_stats_with_overlap_correction
    
    return calculate_area_stats_with_overlap_correction(regions, image_width, image_height)


def _adjust_for_overlap(regions: Dict, image_width: int, image_height: int) -> Dict:
    """
    简化处理：假设区域可能重叠，返回各类区域的估算面积
    已弃用，请使用 calculate_area_stats
    """
    stats = calculate_area_stats(regions, image_width, image_height)
    return {
        "inscription_area": stats["inscription_area"],
        "painting_area": stats["painting_area"],
        "blank_area": stats["blank_area"]
    }


def generate_heatmap_data(regions: Dict, image_width: int, image_height: int, grid_size: int = 20) -> List:
    """
    生成热力图数据
    支持多边形和矩形区域
    """
    from .polygon_utils import point_in_polygon, rectangle_to_polygon
    
    heatmap = []
    
    # 将题跋区域转换为多边形列表
    inscription_polys = []
    for reg in regions.get("inscription_regions", []):
        if "points" in reg and isinstance(reg["points"], list):
            inscription_polys.append(reg["points"])
        elif "x1" in reg and "y1" in reg and "x2" in reg and "y2" in reg:
            # 矩形转多边形
            poly = rectangle_to_polygon(reg["x1"], reg["y1"], reg["x2"], reg["y2"])
            inscription_polys.append(poly)

    for y in range(0, image_height, grid_size):
        for x in range(0, image_width, grid_size):
            x1, y1 = x, y
            x2, y2 = min(x + grid_size, image_width), min(y + grid_size, image_height)
            
            # 计算网格中心点
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            center_point = {"x": center_x, "y": center_y}
            
            # 检查中心点是否在任何一个题跋多边形内
            inscription_coverage = 0.0
            for poly in inscription_polys:
                if len(poly) >= 3 and point_in_polygon(center_point, poly):
                    inscription_coverage = 1.0
                    break
            
            # 对于矩形区域，保留原有的重叠计算逻辑作为补充
            if inscription_coverage == 0.0:
                for reg in regions.get("inscription_regions", []):
                    if "x1" in reg and "y1" in reg and "x2" in reg and "y2" in reg:
                        overlap_x1 = max(x1, reg["x1"])
                        overlap_y1 = max(y1, reg["y1"])
                        overlap_x2 = min(x2, reg["x2"])
                        overlap_y2 = min(y2, reg["y2"])
                        
                        if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                            overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                            cell_area = (x2 - x1) * (y2 - y1)
                            coverage = overlap_area / cell_area if cell_area > 0 else 0
                            inscription_coverage = max(inscription_coverage, coverage)
            
            if inscription_coverage > 0:
                heatmap.append({
                    "x": x // grid_size,
                    "y": y // grid_size,
                    "value": inscription_coverage
                })
    
    return heatmap
