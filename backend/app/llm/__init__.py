"""v2.0 §2.4 — LLM 统一网关（全项目 Chat Completions 调用唯一出口）。

公开接口：
    from app.llm import chat_completion, chat_completion_async, LLMError, parse_json_loose
"""
from app.llm.client import chat_completion, chat_completion_async
from app.llm.errors import LLMError, ProviderError
from app.llm.providers import resolve_provider
from app.llm.usage import snapshot


def parse_json_loose(text: str):
    """从 LLM 输出中提取并解析 JSON：容忍 ```json 围栏与前后缀文本。

    解析失败抛 json.JSONDecodeError，由调用方决定兜底。
    """
    import json
    if not text:
        raise ValueError("empty text")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        raise json.JSONDecodeError("no JSON found", text, 0)
    return json.loads(text[start:])
