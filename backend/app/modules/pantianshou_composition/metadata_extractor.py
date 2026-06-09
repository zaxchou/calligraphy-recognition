"""从 PDF 内容中用 LLM 提取结构化元数据"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """分析以下学术文献内容，提取结构化元数据。
只返回 JSON，不要其他文字。尽可能从文中推断，不要轻易放弃。

返回格式：
{{
  "title": "文献标题",
  "authors": ["作者1", "作者2"],
  "journal": "期刊名或出版社名（从文中出现的刊名、版权页、页眉页脚推断）",
  "publish_year": 2019,
  "doi": "10.xxxx/xxxxx",
  "abstract": "摘要内容（如果文中有摘要段落，提取100-200字）",
  "keywords": ["关键词1", "关键词2"],
  "source_type": "论文/专著/期刊文章/会议论文/学位论文"
}}

提示：
- 作者通常在标题下方或首页底部
- 期刊名可能出现在页眉、页脚、引用格式中（如"美术研究，2019年第3期"）
- 年份可能出现在期刊信息、引用格式、或正文提及中
- DOI 通常在首页底部或末页
- 如果确实无法确定某字段，设为 null

文献内容：
{content}
"""


async def extract_metadata(full_md: str) -> Dict[str, Any]:
    """从 Markdown 内容中提取元数据"""
    if not full_md:
        return {}

    # 采样策略：首页 + 第2-3页，覆盖摘要/关键词/期刊信息
    part1 = full_md[:2000]
    part2 = full_md[2000:5000] if len(full_md) > 2000 else ""
    content = part1
    if part2:
        content += "\n\n--- 后续内容 ---\n\n" + part2

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
                    "max_tokens": 800,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]

        # 解析 JSON
        text = text.strip()
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 { 到最后一个 }
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                try:
                    result = json.loads(text[start:end+1])
                except json.JSONDecodeError:
                    logger.warning(f"JSON parse failed: {text[start:start+200]}")
                    return {}
            else:
                logger.warning(f"No JSON in response: {text[:200]}")
                return {}
        return result
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return {}
