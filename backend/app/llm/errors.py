"""v2.0 §2.4 — LLM 网关错误类型。"""


class LLMError(Exception):
    """LLM 调用最终失败（重试耗尽/配置错误/不可重试错误）。"""


class ProviderError(LLMError):
    """供应商不可用（密钥未配置等）。LLMError 子类，兼容层统一捕获。"""
