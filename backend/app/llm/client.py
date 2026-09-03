"""v2.0 §2.4 — LLM 统一网关核心。

全项目所有 Chat Completions 调用的唯一出口：
- 连接复用（模块级 httpx 客户端单例，而非每调用新建）
- 统一重试（指数退避 + 抖动，仅对 429/5xx 与网络错误）
- 统一超时 / 统一错误语义（失败抛 LLMError，不再把 error 塞进响应 dict）
- 统一计量（app/llm/usage）
- 统一供应商选择（app/llm/providers）
"""
import asyncio
import random
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from app.llm.providers import resolve_provider, ProviderError
from app.llm.usage import record

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TIMEOUT = 120.0
CONNECT_TIMEOUT = 15.0

_async_client: Optional[httpx.AsyncClient] = None
_async_lock = threading.Lock()
_sync_client: Optional[httpx.Client] = None
_sync_lock = threading.Lock()


class LLMError(Exception):
    """LLM 调用最终失败（重试耗尽/配置错误/不可重试错误）。"""


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        with _async_lock:
            if _async_client is None:
                _async_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=CONNECT_TIMEOUT))
    return _async_client


def _get_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None:
        with _sync_lock:
            if _sync_client is None:
                _sync_client = httpx.Client(
                    timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=CONNECT_TIMEOUT))
    return _sync_client


def _build_body(name: str, model: str, messages: List[Dict[str, str]],
                max_tokens: int, temperature: float,
                body_defaults: Dict[str, Any], extra_body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    body = {
        "model": model,
        "messages": messages or [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body.update(body_defaults)
    if extra_body:
        body.update(extra_body)
    return body


def _backoff(attempt: int) -> float:
    return 0.5 * (2 ** attempt) + random.uniform(0, 0.25)


def chat_completion(
    messages: List[Dict[str, str]],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
    retries: int = 2,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """同步版 Chat Completions。失败抛 LLMError。"""
    name, api_key, base_url, resolved_model, body_defaults = resolve_provider(provider, model)
    body = _build_body(name, resolved_model, messages, max_tokens, temperature, body_defaults, extra_body)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = "unknown"
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            resp = _get_sync_client().post(f"{base_url}/chat/completions",
                                           headers=headers, json=body)
            if resp.status_code in RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            record(name, resolved_model, time.monotonic() - start, True,
                   usage.get("total_tokens"))
            return data
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            last_error = str(e)[:200]
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            if attempt < retries:
                time.sleep(_backoff(attempt))
            continue
        except Exception as e:
            last_error = str(e)[:200]
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            break
    raise LLMError(f"LLM 调用失败（{name}:{resolved_model}）: {last_error}")


async def chat_completion_async(
    messages: List[Dict[str, str]],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
    retries: int = 2,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """异步版 Chat Completions。失败抛 LLMError。"""
    name, api_key, base_url, resolved_model, body_defaults = resolve_provider(provider, model)
    body = _build_body(name, resolved_model, messages, max_tokens, temperature, body_defaults, extra_body)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = "unknown"
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            resp = await _get_async_client().post(f"{base_url}/chat/completions",
                                                  headers=headers, json=body)
            if resp.status_code in RETRYABLE_STATUS:
                raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            record(name, resolved_model, time.monotonic() - start, True,
                   usage.get("total_tokens"))
            return data
        except (httpx.HTTPError, httpx.HTTPStatusError) as e:
            last_error = str(e)[:200]
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            if attempt < retries:
                await asyncio.sleep(_backoff(attempt))
            continue
        except Exception as e:
            last_error = str(e)[:200]
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            break
    raise LLMError(f"LLM 调用失败（{name}:{resolved_model}）: {last_error}")
