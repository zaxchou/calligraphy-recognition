"""
统一 Qwen LLM 调用客户端
所有 httpx 调用必须通过此模块，确保 enable_thinking 全局统一
"""
import httpx
from typing import Dict, List, Optional, Any
from app.core.config import get_settings


def call_qwen_chat(
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    统一 Qwen Chat Completions 调用

    Args:
        model: 模型名称（如 qwen3.5-plus）
        messages: 对话消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数
        extra_body: 额外请求参数

    Returns:
        API 响应结果字典
    """
    settings = get_settings()

    request_body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_thinking": settings.QWEN_THINKING_ENABLED,
    }

    if extra_body:
        request_body.update(extra_body)

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            response = client.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.QWEN_API_KEY}",
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
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    异步版本 Qwen Chat Completions 调用

    Args:
        model: 模型名称（如 qwen3.5-plus）
        messages: 对话消息列表
        max_tokens: 最大 token 数
        temperature: 温度参数
        extra_body: 额外请求参数

    Returns:
        API 响应结果字典
    """
    settings = get_settings()

    request_body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_thinking": settings.QWEN_THINKING_ENABLED,
    }

    if extra_body:
        request_body.update(extra_body)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            response = await client.post(
                f"{settings.QWEN_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.QWEN_API_KEY}",
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
