import httpx
import base64
import json
from typing import List, Dict, Optional, Tuple

import os
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

MODEL_NAME = "Pro/moonshotai/Kimi-K2.5"


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


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

    base64_image = encode_image_to_base64(image_path)

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
        "model": MODEL_NAME,
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

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            response = client.post(SILICONFLOW_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            content = result["choices"][0]["message"]["content"]

            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            analysis = json.loads(content)

            normalized_regions = _normalize_regions(analysis, image_width, image_height)

            return {
                "success": True,
                "regions": normalized_regions,
                "analysis_note": analysis.get("analysis_note", ""),
                "raw_response": content
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "API请求超时，请重试"
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"API请求错误: {e.response.status_code}"
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON解析错误: {str(e)}"
        }
    except Exception as e:
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
    from .polygon_utils import point_in_polygon
    
    blank_regions = []
    
    # 将题跋和绘画转换为多边形列表
    occupied_polys = []
    for reg in inscription_regions + painting_regions:
        if "points" in reg and len(reg["points"]) >= 3:
            occupied_polys.append(reg["points"])
        elif "x1" in reg:
            # 矩形转多边形
            poly = [
                {"x": reg["x1"], "y": reg["y1"]},
                {"x": reg["x2"], "y": reg["y1"]},
                {"x": reg["x2"], "y": reg["y2"]},
                {"x": reg["x1"], "y": reg["y2"]}
            ]
            occupied_polys.append(poly)
    
    # 使用网格采样找到留白区域的边界点
    grid_size = 20
    blank_points = set()
    
    for y in range(0, image_height, grid_size):
        for x in range(0, image_width, grid_size):
            point = {"x": x, "y": y}
            # 检查是否在题跋或绘画区域内
            is_occupied = any(
                point_in_polygon(point, poly) 
                for poly in occupied_polys
            )
            if not is_occupied:
                blank_points.add((x // grid_size, y // grid_size))
    
    # 简单的矩形留白区域（整幅画的外框减去已占用区域）
    # 这里简化处理，返回一个大的矩形留白区域
    # 实际应用中可以使用更复杂的算法来找到多个独立的留白区域
    
    # 找到留白的边界
    if blank_points:
        min_x = min(p[0] for p in blank_points) * grid_size
        max_x = (max(p[0] for p in blank_points) + 1) * grid_size
        min_y = min(p[1] for p in blank_points) * grid_size
        max_y = (max(p[1] for p in blank_points) + 1) * grid_size
        
        # 限制在图像范围内
        min_x = max(0, min_x)
        min_y = max(0, min_y)
        max_x = min(image_width, max_x)
        max_y = min(image_height, max_y)
        
        blank_regions.append({
            "x1": min_x,
            "y1": min_y,
            "x2": max_x,
            "y2": max_y,
            "type": "rectangle"
        })
    
    return blank_regions


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
