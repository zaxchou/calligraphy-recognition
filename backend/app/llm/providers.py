"""v2.0 §2.4 — LLM 统一网关：供应商解析（配置驱动）。"""
from typing import Any, Dict, Optional, Tuple

from app.core.config import get_settings
from app.llm.errors import ProviderError


def resolve_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[str, str, str, str, Dict[str, Any]]:
    """解析出 (name, api_key, base_url, model, body_defaults)。

    provider 为 None/"auto" 时按密钥可用性自动选择：deepseek → qwen → zhipu。
    body_defaults 是各供应商必需的请求体默认值（如关闭思考模式）。
    """
    s = get_settings()
    name = (provider or "auto").lower()

    if name == "auto":
        if s.DEEPSEEK_API_KEY:
            name = "deepseek"
        elif s.QWEN_API_KEY:
            name = "qwen"
        elif s.ZHIPU_ENABLED and s.ZHIPU_API_KEY:
            name = "zhipu"
        else:
            raise ProviderError("未配置任何可用的 LLM 供应商密钥")

    if name == "deepseek":
        return (name, s.DEEPSEEK_API_KEY, s.DEEPSEEK_BASE_URL,
                model or s.DEEPSEEK_TEXT_MODEL,
                {"thinking": {"type": "disabled"}})
    if name == "qwen":
        return (name, s.QWEN_API_KEY, s.QWEN_BASE_URL,
                model or "qwen3.5-plus",
                {"enable_thinking": s.QWEN_THINKING_ENABLED})
    if name == "siliconflow":
        return (name, s.SILICONFLOW_API_KEY, "https://api.siliconflow.cn/v1",
                model or "deepseek-ai/DeepSeek-V3", {})
    if name == "zhipu":
        return (name, s.ZHIPU_API_KEY, s.ZHIPU_BASE_URL,
                model or s.ZHIPU_MODEL, {})
    raise ProviderError(f"未知供应商: {name}")
