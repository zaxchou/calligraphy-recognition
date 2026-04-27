"""
统一 LLM 调用客户端
- 文本模型：DeepSeek V4 Flash 优先 → Qwen 兜底
- 图像模型：保持 Qwen VL（不变）
所有 httpx 调用必须通过此模块，确保 enable_thinking 全局统一
"""
import httpx
from typing import Dict, List, Optional, Any, Tuple
from app.core.config import get_settings


def get_text_llm_config() -> Tuple[str, str, str]:
    """
    获取文本 LLM 配置。
    优先 DeepSeek → 兜底 Qwen。
    返回 (api_key, base_url, model)
    """
    settings = get_settings()
    if settings.DEEPSEEK_API_KEY:
        return settings.DEEPSEEK_API_KEY, settings.DEEPSEEK_BASE_URL, settings.DEEPSEEK_TEXT_MODEL
    return settings.QWEN_API_KEY, settings.QWEN_BASE_URL, "qwen3.5-plus"


def call_qwen_chat(
    model: str = None,
    messages: List[Dict[str, str]] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    统一 Chat Completions 调用（文本模型 — DeepSeek 优先）

    Args:
        model: 模型名称，不传则自动选择（DeepSeek 或 Qwen 兜底）
        messages: 对话消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数
        extra_body: 额外请求参数

    Returns:
        API 响应结果字典
    """
    settings = get_settings()

    if settings.DEEPSEEK_API_KEY:
        api_key = settings.DEEPSEEK_API_KEY
        base_url = settings.DEEPSEEK_BASE_URL
        model = model or settings.DEEPSEEK_TEXT_MODEL
    else:
        api_key = settings.QWEN_API_KEY
        base_url = settings.QWEN_BASE_URL
        model = model or "qwen3.5-plus"

    request_body = {
        "model": model,
        "messages": messages or [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # DeepSeek 默认关闭思考模式
    if settings.DEEPSEEK_API_KEY:
        body_defaults = {"thinking": {"type": "disabled"}}
    else:
        body_defaults = {"enable_thinking": settings.QWEN_THINKING_ENABLED}

    if extra_body:
        body_defaults.update(extra_body)
    request_body.update(body_defaults)

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {"error": f"HTTP error: {str(e)[:100]}"}
    except Exception as e:
        return {"error": f"Request error: {str(e)[:100]}"}


async def call_qwen_chat_async(
    model: str = None,
    messages: List[Dict[str, str]] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    异步版本 Chat Completions 调用（文本模型 — DeepSeek 优先）
    """
    settings = get_settings()

    if settings.DEEPSEEK_API_KEY:
        api_key = settings.DEEPSEEK_API_KEY
        base_url = settings.DEEPSEEK_BASE_URL
        model = model or settings.DEEPSEEK_TEXT_MODEL
    else:
        api_key = settings.QWEN_API_KEY
        base_url = settings.QWEN_BASE_URL
        model = model or "qwen3.5-plus"

    request_body = {
        "model": model,
        "messages": messages or [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # DeepSeek 默认关闭思考模式
    if settings.DEEPSEEK_API_KEY:
        body_defaults = {"thinking": {"type": "disabled"}}
    else:
        body_defaults = {"enable_thinking": settings.QWEN_THINKING_ENABLED}

    if extra_body:
        body_defaults.update(extra_body)
    request_body.update(body_defaults)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_body
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {"error": f"HTTP error: {str(e)[:100]}"}
    except Exception as e:
        return {"error": f"Request error: {str(e)[:100]}"}
