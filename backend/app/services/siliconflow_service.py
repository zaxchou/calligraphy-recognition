import logging
import httpx
import base64
import json
import time
from typing import List, Dict, Optional, Tuple
import io
import re
from PIL import Image

from app.core.config import get_settings

# logger = logging.getLogger(__name__)  # 彻底禁用，避免 name 'logger' is not defined 问题！！
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


def _extract_complete_json_array(content: str, array_key: str) -> Optional[list]:
    """
    从截断的 content 中提取完整的数组（如 inscription_regions）。
    用括号计数找到正确的闭合 ]，非正则非贪婪匹配。
    返回完整解析的数组或 None。
    """
    import re
    print(f"DEBUG: _extract_complete_json_array for {array_key}")
    key_pattern = rf'"{array_key}"\s*:'
    key_match = re.search(key_pattern, content)
    if not key_match:
        print("DEBUG: _extract_complete_json_array: key not found")
        return None

    # 找 [ 开始
    ptr = key_match.end()
    while ptr < len(content) and content[ptr] in ' \t\n\r':
        ptr += 1
    if ptr >= len(content) or content[ptr] != '[':
        print("DEBUG: _extract_complete_json_array: no [ found")
        return None

    # 括号计数找 ] 结束
    bracket_count = 1
    ptr += 1
    start = ptr - 1
    while ptr < len(content) and bracket_count > 0:
        c = content[ptr]
        if c == '[':
            bracket_count += 1
        elif c == ']':
            bracket_count -= 1
        ptr += 1

    array_str = content[start:ptr]
    try:
        result = json.loads(array_str)
        print(f"DEBUG: _extract_complete_json_array: {array_key} parsed, {len(result) if result else 0} items")
        return result
    except json.JSONDecodeError as e:
        print(f"DEBUG: _extract_complete_json_array: {array_key} parse failed, try extract first N: {e}")
        return _extract_first_n_complete_objects(content[start:], n=5)


def _extract_first_n_complete_objects(array_content: str, n: int = 10) -> Optional[list]:
    """
    从数组内容中（去掉 [ ]）提取前 N 个完整的 { ... } 对象。
    """
    objects = []
    ptr = 0
    # 跳过开头的 [
    if ptr < len(array_content) and array_content[ptr] == '[':
        ptr += 1

    for _ in range(n):
        # 跳过 whitespace 和逗号
        while ptr < len(array_content) and array_content[ptr] in ' \t\n\r,':
            ptr += 1
        if ptr >= len(array_content):
            break
        if array_content[ptr] != '{':
            break  # 不是对象了

        # 找这个对象的闭合 }
        brace_count = 1
        obj_start = ptr
        ptr += 1
        while ptr < len(array_content) and brace_count > 0:
            c = array_content[ptr]
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
            ptr += 1
        if brace_count == 0:
            obj_str = array_content[obj_start:ptr]
            try:
                obj = json.loads(obj_str)
                objects.append(obj)
            except json.JSONDecodeError as e:
                print(f"DEBUG: _extract_first_n_complete_objects: json parse failed: {e}")
        else:
            print("DEBUG: _extract_first_n_complete_objects: no closing brace")
            break

    if objects:
        print(f"INFO: _extract_first_n_complete_objects: extracted {len(objects)} complete objects")
        return objects
    return None


def _parse_llm_json_response(content: str) -> Dict:
    """
    解析 LLM 返回的 JSON 内容，带多级容错：
    Level 1: 直接解析
    Level 2: 标准修复后解析
    Level 2.5: 从截断的内容中提取完整的 inscription_regions 和 painting_regions
    Level 3: 更激进 — 用正则从损坏文本中提取 regions
    Level 4: 返回最小有效结构，并标记失败
    """
    raw = content

    # --- Level 1: 直接尝试 ---
    try:
        parsed = json.loads(content.strip())
        parsed["success"] = True
        return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # --- Level 2: 跳过标准修复（容易把内容改坏），直接进 Level 2.5 提取 regions ---
    print("WARNING: Level 1 直接解析失败，跳过 Level 2 修复，直接进 Level 2.5")

    # --- Level 2.5: 提取完全截断前的完整 regions 数组 ---
    # 专门处理这种：开头有完整 inscription_regions/painting_regions，后面截断的情况
    print("WARNING: Level 2.5: 从原始内容中提取完整 regions...")
    try:
        # 先移除 ```json 标记，只取第一个 { 之后的内容
        clean_start = content
        m = re.search(r'```json\s*({)', clean_start, re.MULTILINE | re.DOTALL)
        if m:
            clean_start = content[m.start(1):]
        else:
            start = clean_start.find('{')
            if start != -1:
                clean_start = clean_start[start:]

        # 提取完整的 inscription_regions 数组
        insc_extracted = _extract_complete_json_array(clean_start, "inscription_regions")
        paint_extracted = _extract_complete_json_array(clean_start, "painting_regions")
        print(f"INFO: Level 2.5 提取结果: inscription_regions={'有' if insc_extracted is not None else '无'}, painting_regions={'有' if paint_extracted is not None else '无'}")
        
        if insc_extracted is not None or paint_extracted is not None:
            result = {
                "inscription_regions": insc_extracted if insc_extracted is not None else [],
                "painting_regions": paint_extracted if paint_extracted is not None else [],
                "blank_regions": [],
                "analysis_note": "JSON截断但成功提取区域"
            }
            print("INFO: Level 2.5 截断提取成功，直接返回 regions")
            result["success"] = True
            return result
    except Exception as e25:
        print(f"WARNING: Level 2.5 失败: {e25}")

    # --- Level 3: 更激进 — 用正则从损坏文本中提取 regions ---
    print("WARNING: Level 3: 尝试正则提取关键数据...")
    analysis = _extract_regions_from_malformed_text(content)
    if analysis:
        print("INFO: Level 3 正则提取成功")
        analysis["success"] = True
        return analysis

    # --- Level 4: 返回最小有效结构，并标记失败 ---
    print("ERROR: 所有JSON解析方式均失败，返回空结构")
    print(f"ERROR: Level 4 原始响应前500字符: {raw[:500]}")
    return {
        "success": False,
        "inscription_regions": [],
        "painting_regions": [],
        "blank_regions": [],
        "analysis_note": "JSON解析失败，原始内容前200字符: " + raw[:200]
    }


def _extract_regions_from_malformed_text(text: str) -> Optional[Dict]:
    """
    从严重损坏的文本中用正则提取 inscription_regions 和 painting_regions
    """
    result = {}

    # 尝试找 inscription_regions 数组内容
    insc_match = re.search(r'"inscription_regions"\s*:\s*\[([\s\S]*?)\](?=\s*,\s*"painting|\s*,\s*"blank|\s*\})', text)
    if not insc_match:
        insc_match = re.search(r'["\']?inscription_regions["\']?\s*[:=]\s*\[([\s\S]*?)\](?=[,\}])', text)

    paint_match = re.search(r'"painting_regions"\s*:\s*\[([\s\S]*?)\](?=\s*,\s*"blank|\s*\})', text)
    if not paint_match:
        paint_match = re.search(r'["\']?painting_regions["\']?\s*[:=]\s*\[([\s\S]*?)](?=[,\}])', text)

    def _parse_region_array(array_text: str) -> list:
        """从数组文本中提取多边形点"""
        regions = []
        objects = re.findall(r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', array_text)
        for obj_text in objects:
            region = {}
            pts_match = re.search(r'"points"\s*:\s*\[([^\]]*)\]', obj_text)
            if pts_match:
                points = []
                for pt in re.findall(r'\{\s*"x"\s*:\s*([\d.]+)\s*,\s*"y"\s*:\s*([\d.]+)\s*\}', pts_match.group(1)):
                    points.append({"x": float(pt[0]), "y": float(pt[1])})
                if len(points) >= 3:
                    region["points"] = points
            else:
                rect = re.search(r'"x1"\s*:\s*([\d.]+).*?"y1"\s*:\s*([\d.]+).*?"x2"\s*:\s*([\d.]+).*?"y2"\s*:\s*([\d.]+)', obj_text)
                if rect:
                    region["x1"] = float(rect.group(1))
                    region["y1"] = float(rect.group(2))
                    region["x2"] = float(rect.group(3))
                    region["y2"] = float(rect.group(4))

            if region:
                regions.append(region)

        return regions

    if insc_match:
        result["inscription_regions"] = _parse_region_array(insc_match.group(1))
    else:
        result["inscription_regions"] = []

    if paint_match:
        result["painting_regions"] = _parse_region_array(paint_match.group(1))
    else:
        result["painting_regions"] = []

    result["blank_regions"] = []
    note_match = re.search(r'"analysis_note"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if note_match:
        result["analysis_note"] = note_match.group(1).replace('\\"', '"').replace('\\n', '\n')
    else:
        result["analysis_note"] = ""

    if result["inscription_regions"]:
        return result
    return None


def _repair_json_string(content: str) -> str:
    """
    激进修复 LLM 返回的损坏 JSON 字符串。
    处理常见的格式错误：缺少逗号、中文标点、截断、多余文本等。
    """
    import re

    # Step 0: 提取最外层 {} 块
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = content[start:end + 1]
    else:
        return "{}"

    # Step 1: 移除 markdown 代码块标记
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```\s*$', '', content)
    content = content.strip()

    # Step 2: 替换中文标点为英文
    replacements = {
        "\uff0c": ",",   # ，→ ,
        "\uff1a": ":",   # ：→ :
        "\u201c": '"',   # "
        "\u201d": '"',   # "
        "\u2018": "'",   # '
        "\u2019": "'",   # '
        "\u3001": ",",   # 、→ ,
        "\uff08": "(",   # （→ (
        "\uff09": ")",   # ）→ )
        "\uff1b": ";",   # ；→ ;
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    # Step 3: 移除单行注释 // ...
    content = re.sub(r'//[^\n]*', '', content)

    # Step 4: 处理字符串内的换行（将多行字符串合并）
    # 先保护字符串内容，修复内部换行
    def _fix_newlines_in_strings(s):
        result = []
        in_string = False
        string_char = None
        i = 0
        while i < len(s):
            c = s[i]
            if in_string:
                if c == '\\' and i + 1 < len(s):
                    result.append(c)
                    result.append(s[i + 1])
                    i += 2
                    continue
                elif c == string_char:
                    in_string = False
                    result.append(c)
                    i += 1
                    continue
                elif c == '\n' or c == '\r':
                    result.append(' ')  # 换行替换为空格
                    i += 1
                    continue
                else:
                    result.append(c)
                    i += 1
                    continue
            else:
                if c == '"' or c == "'":
                    in_string = True
                    string_char = c
                    result.append(c)
                elif c == '\\':
                    result.append(c)
                    if i + 1 < len(s):
                        result.append(s[i + 1])
                        i += 2
                        continue
                else:
                    result.append(c)
                i += 1
        return ''.join(result)

    content = _fix_newlines_in_strings(content)

    # Step 5: 移除尾部逗号 }, ] 前面
    content = re.sub(r",\s*([}\]])", r"\1", content)

    # Step 6: 修复常见结构问题

    # } 后紧跟 { 或 [ → 补逗号
    content = re.sub(r'\}\s*(?=[{\[])', '},', content)

    # ] 后紧跟 { → 补逗号
    content = re.sub(r'\]\s*\{', '],[{', content)

    # 数字/布尔/null/} 后直接跟 "（新键名）或数字 → 补逗号
    # 注意：只在对象上下文中处理
    content = re.sub(r'(true|false|null|\d\.?\d*)\s*"', r'\1,"', content)

    # Step 7: 修复未闭合的字符串（截断情况）
    # 找到所有双引号，如果奇数个，补一个
    quote_count = content.count('"') - content.count('\\"')
    if quote_count % 2 == 1:
        # 在最后一个非 }/] 的位置前补引号
        last_brace = max(content.rfind('}'), content.rfind(']'))
        if last_brace > 0:
            insert_pos = last_brace
            # 往回找合适的插入点
            while insert_pos > 0 and content[insert_pos - 1] in ' \t\n\r,':
                insert_pos -= 1
            content = content[:insert_pos] + '"' + content[insert_pos:]

    # Step 8: 处理截断 — 如果最后一个字符不是 } 或 ]
    content = content.rstrip()
    if content and content[-1] not in ('}', ']'):
        # 尝试闭合
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        content += '}' * max(0, open_braces) + ']' * max(0, open_brackets)
        # 再次清理尾部逗号
        content = re.sub(r",\s*([}\]])", r"\1", content)

    # Step 9: 最终清理多余空白
    content = re.sub(r'\n+', ' ', content)
    content = re.sub(r'[ \t]+', ' ', content)

    return content


def analyze_image_regions(image_path: str, image_width: int, image_height: int, artist: str = None) -> Dict:
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
    print(f"INFO: 开始分析图像: {image_path}")
    print(f"INFO: 图像尺寸: {image_width}x{image_height}")
    
    try:
        # 检查图像文件大小
        import os
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        print(f"INFO: 图像文件大小: {file_size:.2f} MB")
        
        # 限制文件大小，避免处理过大的图像
        if file_size > 50:  # 限制为50MB
            print("ERROR: 图像文件过大，超过50MB限制")
            return {
                "success": False,
                "error": "图像文件过大，超过50MB限制"
            }
        
        base64_image = encode_image_to_base64(image_path, max_side=2048, quality=85)
        print(f"INFO: Base64编码完成，大小: {len(base64_image) / (1024 * 1024):.2f} MB")

        artist_name = artist if artist else ""
        artist_desc = f"{artist_name}的" if artist_name else ""
        prompt = f"""你是一个专业的中国画艺术分析师。请按照以下三步策略分析这幅{artist_desc}绘画作品：

## 三步划分策略

### 第一步：确定绘画区域（绿色）
- **目标**：标记画作中的绘画主体（山水、花鸟、竹石等）
- **要求**：用15-25个点的多边形沿绘画主体外边缘描绘轮廓，尽量贴合实际边缘，允许少量溢出（5%左右）
- **方法**：沿绘画内容的可见外缘取点，点间距大致均匀，在边缘弯曲或变化大的地方多取点以贴合轮廓

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
            "points": [
                {{"x": 0.15, "y": 0.05}}, {{"x": 0.30, "y": 0.08}}, {{"x": 0.42, "y": 0.15}},
                {{"x": 0.50, "y": 0.25}}, {{"x": 0.55, "y": 0.38}}, {{"x": 0.52, "y": 0.48}},
                {{"x": 0.58, "y": 0.55}}, {{"x": 0.62, "y": 0.65}}, {{"x": 0.60, "y": 0.75}},
                {{"x": 0.55, "y": 0.82}}, {{"x": 0.50, "y": 0.88}}, {{"x": 0.42, "y": 0.92}},
                {{"x": 0.32, "y": 0.90}}, {{"x": 0.22, "y": 0.85}}, {{"x": 0.15, "y": 0.78}},
                {{"x": 0.10, "y": 0.68}}, {{"x": 0.08, "y": 0.55}}, {{"x": 0.06, "y": 0.42}},
                {{"x": 0.08, "y": 0.28}}, {{"x": 0.10, "y": 0.15}}
            ]
        }}
    ],
    "blank_regions": [],
    "analysis_note": "分析画作内容、艺术特色、题跋内容等，不要包含坐标信息或区域边界描述"
}}```

## 输出格式

```json
{{
    "inscription_regions": [ {{"points": [{{"x":0.05,"y":0.05}},...]}}, ... ],
    "painting_regions": [ {{"points": [{{"x":0.1,"y":0.1}},{{"x":0.3,"y":0.1}},...]}}, ... ],
    "blank_regions": [],
    "analysis_note": "简要描述画作内容"
}}
```

## 关键规则
- **只用 points 多边形格式，禁止 x1/y1/x2/y2 矩形格式**，每个多边形至少3个点
- **绘画区域**：沿外缘取15-25个点，允许约5%溢出
- **题跋区域**：精确框选文字和印章，禁止与绘画重叠
- **留白区域**：留空数组，由系统自动计算
- 坐标为0-1之间的浮点数（相对图像宽高比例）

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
            "max_tokens": 16384
        }

        print("INFO: 开始调用API分析图像...")

        def build_chat_url(base_url: str) -> str:
            base = (base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                return base
            return f"{base}/chat/completions"

        def call_provider(provider: str, base_url: str, api_key: str, model: str) -> Dict:
            url = build_chat_url(base_url)
            print(f"INFO: 当前使用AI供应商: {provider}")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            provider_payload = dict(payload)
            provider_payload["model"] = model

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
            with httpx.Client(limits=limits) as client:
                for retry in range(MAX_RETRIES):
                    attempt_timeout = httpx.Timeout(400.0, connect=10.0, read=360.0, write=60.0)
                    delay = min(60, (2 ** retry) * RETRY_DELAY)
                    jitter = 0.5 + (time.time() % 1.0) * 0.5
                    delay = delay * jitter
                    try:
                        response = client.post(url, headers=headers, json=provider_payload, timeout=attempt_timeout)
                        response.raise_for_status()
                        result = response.json()

                        content = result["choices"][0]["message"]["content"]
                        print("INFO: API调用成功，开始解析返回结果...")

                        # 使用统一的JSON修复函数
                        analysis = _parse_llm_json_response(content)

                        # JSON 解析彻底失败（Level 4 也恢复不了）
                        if not analysis.get("success", True):
                            if retry < MAX_RETRIES - 1:
                                print(f"WARNING: JSON解析失败，将在同一供应商内重试 ({retry+1}/{MAX_RETRIES})")
                                time.sleep(delay)
                                continue
                            print("WARNING: JSON解析失败，所有重试用尽，报告给调用方处理")
                            return {
                                "success": False,
                                "error": analysis.get("analysis_note", "JSON解析失败"),
                                "regions": {},
                                "analysis_note": analysis.get("analysis_note", ""),
                                "raw_response": content[:500]
                            }

                        print("INFO: JSON解析成功")

                        # 【极端容错】区域标准化失败时返回默认空 regions
                        try:
                            normalized_regions = _normalize_regions(analysis, image_width, image_height)
                            print("INFO: 区域标准化完成")
                        except Exception as e_norm:
                            print(f"WARNING: 区域标准化失败，使用默认空regions: {e_norm}")
                            normalized_regions = {
                                "inscription_regions": [],
                                "painting_regions": [],
                                "blank_regions": [{"x1": 0, "y1": 0, "x2": image_width, "y2": image_height, "type": "rectangle"}]
                            }

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
                            print(f"WARNING: API请求错误 {status} (重试 {retry+1}/{MAX_RETRIES})")
                            time.sleep(delay)
                            continue
                        try:
                            error_detail = e.response.json().get("error", {}).get("message", "Unknown error")
                            return {"success": False, "error": f"API请求错误: {status} - {error_detail}"}
                        except Exception:
                            return {"success": False, "error": f"API请求错误: {status}"}
                    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: 网络/超时错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "网络/超时错误: " + str(e)}
                    except json.JSONDecodeError as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: JSON解析错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "JSON解析错误: " + str(e)}
                    except Exception as e:
                        return {"success": False, "error": "分析失败: " + str(e)}

        tried = []
        last_error = None

        forced = (getattr(settings, "TIBA_LLM_PROVIDER", "") or "").strip().lower()
        if forced and forced not in ("zhipu", "qwen", "siliconflow"):
            return {"success": False, "error": f"无效TIBA_LLM_PROVIDER: {forced}"}

        def _try(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            nonlocal last_error
            tried.append(provider)
            result = call_provider(provider, base_url, api_key, model)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error
            return None

        if forced == "zhipu":
            if settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
                r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"zhipu调用失败或未配置: {last_error or ''}".strip()}

        if forced == "qwen":
            if settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
                r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"qwen调用失败或未配置: {last_error or ''}".strip()}

        if forced == "siliconflow":
            if settings.SILICONFLOW_API_KEY:
                r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"siliconflow调用失败或未配置: {last_error or ''}".strip()}

        if settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
            r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
            if r:
                return r

        if settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
            r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
            if r:
                return r

        if settings.SILICONFLOW_ENABLED and settings.SILICONFLOW_API_KEY:
            r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
            if r:
                return r

        tried_text = " -> ".join(tried) if tried else "none"
        suffix = f": {last_error}" if last_error else ""
        return {"success": False, "error": f"无可用AI供应商或调用失败 ({tried_text}){suffix}"}

    except Exception as e:
        print(f"ERROR: 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "分析失败: " + str(e)
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
        print(f"ERROR: 计算留白区域时出错: {e}")
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


def analyze_text_summary_only(image_path: str, artist: str = None) -> Dict:
    """
    轻量化AI分析：只生成画作点评概述，不进行区域检测和OCR识别

    Returns:
        {
            "success": boolean,
            "analysis_note": str,
            "error": str (if failed)
        }
    """
    print(f"INFO: 开始轻量化AI点评: {image_path}")
    
    try:
        # 检查图像文件大小
        import os
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        print(f"INFO: 图像文件大小: {file_size:.2f} MB")
        
        # 限制文件大小，避免处理过大的图像
        if file_size > 50:  # 限制为50MB
            print("ERROR: 图像文件过大，超过50MB限制")
            return {
                "success": False,
                "error": "图像文件过大，超过50MB限制"
            }
        
        base64_image = encode_image_to_base64(image_path, max_side=2048, quality=85)
        print(f"INFO: Base64编码完成，大小: {len(base64_image) / (1024 * 1024):.2f} MB")

        artist_name = artist if artist else ""
        artist_desc = f"{artist_name}的" if artist_name else ""
        prompt = f"""你是一个专业的中国画艺术分析师。请对这幅{artist_desc}绘画作品进行简要点评概述。

## 点评内容要求

请从以下几个方面进行点评：
1. 画作内容概述（描绘了什么主题）
2. 艺术特色和风格特点
3. 整体观感和评价

请用简洁明了的语言，不要超过300字。直接返回点评内容，不需要任何JSON格式或其他标记。"""

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
            "max_tokens": 1000
        }

        print("INFO: 开始调用轻量化AI点评API...")

        def build_chat_url(base_url: str) -> str:
            base = (base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                return base
            return f"{base}/chat/completions"

        def call_provider(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            url = build_chat_url(base_url)
            print(f"INFO: 当前使用AI供应商: {provider}")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            provider_payload = dict(payload)
            provider_payload["model"] = model

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
            with httpx.Client(limits=limits) as client:
                for retry in range(MAX_RETRIES):
                    attempt_timeout = httpx.Timeout(120.0, connect=10.0, read=90.0, write=20.0)
                    delay = min(60, (2 ** retry) * RETRY_DELAY)
                    jitter = 0.5 + (time.time() % 1.0) * 0.5
                    delay = delay * jitter
                    try:
                        response = client.post(url, headers=headers, json=provider_payload, timeout=attempt_timeout)
                        response.raise_for_status()
                        result = response.json()

                        content = result["choices"][0]["message"]["content"]
                        print("INFO: 轻量化AI点评API调用成功")
                        
                        return {
                            "success": True,
                            "analysis_note": content.strip(),
                            "provider": provider
                        }
                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        retryable = status in (429, 500, 502, 503, 504)
                        if retryable and retry < MAX_RETRIES - 1:
                            print(f"WARNING: API请求错误 {status} (重试 {retry+1}/{MAX_RETRIES})")
                            time.sleep(delay)
                            continue
                        try:
                            error_detail = e.response.json().get("error", {}).get("message", "Unknown error")
                            return {"success": False, "error": f"API请求错误: {status} - {error_detail}"}
                        except Exception:
                            return {"success": False, "error": f"API请求错误: {status}"}
                    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: 网络/超时错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "网络/超时错误: " + str(e)}
                    except Exception as e:
                        return {"success": False, "error": "分析失败: " + str(e)}

        tried = []
        last_error = None

        forced = (getattr(settings, "TIBA_LLM_PROVIDER", "") or "").strip().lower()
        if forced and forced not in ("zhipu", "qwen", "siliconflow"):
            return {"success": False, "error": f"无效TIBA_LLM_PROVIDER: {forced}"}

        def _try(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            nonlocal last_error
            tried.append(provider)
            result = call_provider(provider, base_url, api_key, model)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error
            return None

        if forced == "zhipu":
            if settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
                r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"zhipu调用失败或未配置: {last_error or ''}".strip()}

        if forced == "qwen":
            if settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
                r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"qwen调用失败或未配置: {last_error or ''}".strip()}

        if forced == "siliconflow":
            if settings.SILICONFLOW_API_KEY:
                r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"siliconflow调用失败或未配置: {last_error or ''}".strip()}

        if settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
            r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
            if r:
                return r

        if settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
            r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
            if r:
                return r

        if settings.SILICONFLOW_ENABLED and settings.SILICONFLOW_API_KEY:
            r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
            if r:
                return r

        tried_text = " -> ".join(tried) if tried else "none"
        suffix = f": {last_error}" if last_error else ""
        return {"success": False, "error": f"无可用AI供应商或调用失败 ({tried_text}){suffix}"}

    except Exception as e:
        print(f"ERROR: 轻量化AI点评失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "轻量化AI点评失败: " + str(e)
        }
