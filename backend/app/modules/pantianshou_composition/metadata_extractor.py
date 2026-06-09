"""从 PDF 内容中用 LLM 提取结构化元数据"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """分析以下学术文献内容，提取结构化元数据。
只返回 JSON，不要其他文字。

返回格式：
{{
  "title": "文献标题",
  "authors": ["作者1", "作者2"],
  "journal": "期刊/出版社名",
  "publish_year": 2019,
  "doi": "10.xxxx/xxxxx"
}}

如果某字段无法确定，设为 null。

文献内容：
{content}
"""


async def extract_metadata(full_md: str) -> Dict[str, Any]:
    """从 Markdown 内容中提取元数据"""
    if not full_md:
        return {}

    # 取前 3000 字符（约前 2 页）
    content = full_md[:3000]

    try:
        import httpx
        from app.core.config import get_settings
        settings = get_settings()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                json={
                    "model": settings.DEEPSEEK_TEXT_MODEL,
                    "messages": [
                        {"role": "user", "content": EXTRACTION_PROMPT.format(content=content)}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]

        # 解析 JSON（处理 markdown code block 包裹）
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        return result
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return {}
