"""从 PDF 内容中用 LLM 提取结构化元数据"""

import json
import logging
import re
from typing import Dict, Any, Optional

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

# 文件名模式：Title_Author.pdf 或 Title—Author.pdf 或 Title_作者.pdf
FILENAME_PATTERN = re.compile(
    r'^(.+?)[_—－]([^_—－]+)\.pdf$'
)

# UUID 模式
UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def extract_from_filename(filename: str) -> dict:
    """从文件名解析标题和作者（兜底策略）"""
    if not filename:
        return {}
    # 去掉路径
    basename = filename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    m = FILENAME_PATTERN.match(basename)
    if not m:
        return {}
    title = m.group(1).strip()
    author = m.group(2).strip()
    # 过滤明显非人名的（纯数字、UUID、括号标记）
    if UUID_RE.match(author) or len(author) < 1 or len(author) > 10:
        return {'title': title}
    return {'title': title, 'author': author}


def _extract_json(text: str) -> dict:
    """鲁棒 JSON 提取"""
    text = text.strip()
    if not text:
        return {}

    stack = []
    json_start = -1
    json_end = -1
    in_string = False
    escape = False
    for i, c in enumerate(text):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            if not stack:
                json_start = i
            stack.append(i)
        elif c == '}':
            if stack:
                stack.pop()
                if not stack:
                    json_end = i + 1
                    break

    if json_start < 0 or json_end <= json_start:
        return {}

    json_str = text[json_start:json_end]
    json_str = json_str.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
    json_str = json_str.replace(', }', '}').replace(',}', '}')
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"JSON parse failed after cleanup")
            return {}


async def _call_llm(content: str, timeout: int = 60) -> dict:
    """调用 DeepSeek LLM 提取元数据，返回解析后的 dict"""
    import httpx
    from app.core.config import get_settings
    settings = get_settings()

    async with httpx.AsyncClient(timeout=timeout) as client:
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

    result = _extract_json(text)
    if not result:
        logger.warning(f"LLM returned no valid JSON (len={len(text)})")
    return result


async def extract_metadata(full_md: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """从 Markdown 内容中提取元数据。filename 用于兜底提取标题/作者。"""
    if not full_md:
        return {}

    # 优先从文件名提取（兜底）
    file_meta = extract_from_filename(filename) if filename else {}

    # 采样（最可能含元数据的段落）
    md_len = len(full_md)
    part1 = full_md[:3000]              # 开头：标题/作者
    part2 = full_md[3000:8000] if md_len > 3000 else ""     # 中段：摘要/关键词
    part3 = full_md[-3000:] if md_len > 10000 else ""       # 末尾：参考文献/期刊信息

    # 首次：完整采样
    content = part1
    if part2:
        content += "\n\n--- 后续内容 ---\n\n" + part2
    if part3:
        content += "\n\n--- 末尾内容 ---\n\n" + part3

    # 首次 LLM 调用
    llm_meta = {}
    for attempt in range(2):
        try:
            # 第2次尝试时用不同采样（只取开头+结尾，跳过中段干扰）
            if attempt == 1:
                alt_content = part1
                if part3:
                    alt_content += "\n\n--- 末尾内容 ---\n\n" + part3
                llm_meta = await _call_llm(alt_content)
            else:
                llm_meta = await _call_llm(content)
            if llm_meta:
                break
        except Exception as e:
            logger.warning(f"LLM attempt {attempt + 1} failed: {e}")

    # 合并：文件名优先（已包含作者），LLM 补充其他字段
    result = {}
    # 标题：文件名优先
    if file_meta.get('title'):
        result['title'] = file_meta['title']
    elif llm_meta.get('title'):
        result['title'] = llm_meta['title']
    # 作者：文件名优先
    if file_meta.get('author'):
        result['authors'] = [file_meta['author']]
    elif llm_meta.get('authors'):
        result['authors'] = llm_meta['authors']
    # 其余字段只取 LLM
    for field in ('journal', 'publish_year', 'doi', 'abstract', 'keywords', 'source_type'):
        if llm_meta.get(field):
            result[field] = llm_meta[field]

    if not result:
        logger.warning("Metadata extraction returned empty")
    return result
