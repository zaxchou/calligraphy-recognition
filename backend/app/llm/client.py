"""v2.0 §2.4 — LLM 统一网关核心。

全项目所有 Chat Completions 调用的唯一出口：
- 连接复用（模块级 httpx 客户端单例，而非每调用新建）
- 统一重试：仅 429/5xx/网络错误指数退避；4xx（鉴权/参数错误）立即失败
- 每请求独立超时（timeout 参数不被共享客户端覆盖）
- 统一错误语义（失败抛 LLMError，不再把 error 塞进响应 dict）
- 统一计量（app/llm/usage）与供应商解析（app/llm/providers）
"""
import random
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from app.llm.errors import LLMError
from app.llm.providers import resolve_provider
from app.llm.usage import record

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TIMEOUT = 120.0
CONNECT_TIMEOUT = 15.0

_async_client: Optional[httpx.AsyncClient] = None
_async_lock = threading.Lock()
_sync_client: Optional[httpx.Client] = None
_sync_lock = threading.Lock()


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


def _backoff(attempt: int) -> float:
    return 0.5 * (2 ** attempt) + random.uniform(0, 0.25)


def _build_body(name: str, model: str, messages: List[Dict[str, str]],
                max_tokens: int, temperature: float,
                body_defaults: Dict[str, Any], extra_body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages or [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body.update(body_defaults)
    if extra_body:
        body.update(extra_body)
    return body


def _chat_request(
    name: str, api_key: str, base_url: str, resolved_model: str,
    messages: List[Dict[str, str]], max_tokens: int, temperature: float,
    body_defaults: Dict[str, Any], extra_body: Optional[Dict[str, Any]],
    retries: int, timeout: float, is_async: bool,
) -> Dict[str, Any]:
    """同步/异步共用的请求-重试循环。"""
    body: Dict[str, Any] = {
        "model": resolved_model,
        "messages": messages or [],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body.update(body_defaults)
    if extra_body:
        body.update(extra_body)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = "unknown"
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            if is_async:
                resp = _get_async_client().post(f"{base_url}/chat/completions",
                                                headers=headers, json=body,
                                                timeout=timeout)
            else:
                resp = _get_sync_client().post(f"{base_url}/chat/completions",
                                               headers=headers, json=body,
                                               timeout=timeout)
            if resp.status_code in RETRYABLE_STATUS:
                # 仅可重试状态码进入退避；4xx（鉴权/参数错误）立即失败不重试
                raise _RetryableStatus(resp.status_code, resp.text[:200])
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage") or {}
            record(name, resolved_model, time.monotonic() - start, True,
                   usage.get("total_tokens"))
            return data
        except _RetryableStatus as e:
            last_error = str(e)
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            if attempt < retries:
                time.sleep(_backoff(attempt))
            continue
        except httpx.HTTPStatusError as e:
            last_error = str(e)[:200]
            record(name, resolved_model, time.monotonic() - start, False, error=last_error)
            break  # 不可重试的 4xx
        except httpx.HTTPError as e:
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


class _RetryableStatus(Exception):
    def __init__(self, status: int, text: str):
        self.status = status
        super().__init__(f"HTTP {status}: {text}")


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
    """同步 Chat Completions。失败抛 LLMError。"""
    name, api_key, base_url, resolved_model, body_defaults = resolve_provider(provider, model)
    return _chat_request(name, api_key, base_url, resolved_model, messages,
                         max_tokens, temperature, body_defaults, extra_body,
                         retries, timeout, is_async=False)


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
    """异步 Chat Completions。失败抛 LLMError。"""
    name, api_key, base_url, resolved_model, body_defaults = resolve_provider(provider, model)
    return _chat_request(name, api_key, base_url, resolved_model, messages,
                         max_tokens, temperature, body_defaults, extra_body,
                         retries, timeout, is_async=True)
