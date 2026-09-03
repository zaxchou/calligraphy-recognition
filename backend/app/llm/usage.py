"""v2.0 §2.4 — LLM 调用计量。

当前实现：结构化日志 + 进程内聚合计数器。
后续可无感升级为入库（usage 表）——只改本模块，调用方无感知。
"""
import logging
import threading
import time
from collections import defaultdict
from typing import Optional

logger = logging.getLogger("llm.usage")

_lock = threading.Lock()
_stats: dict = defaultdict(lambda: {"calls": 0, "failures": 0, "latency_sum": 0.0, "tokens": 0})


def record(provider: str, model: str, latency: float, ok: bool,
           total_tokens: Optional[int] = None, error: Optional[str] = None) -> None:
    key = f"{provider}:{model}"
    with _lock:
        stat = _stats[key]
        stat["calls"] += 1
        stat["latency_sum"] += latency
        if not ok:
            stat["failures"] += 1
        if total_tokens:
            stat["tokens"] += total_tokens
    level = logging.INFO if ok else logging.WARNING
    logger.log(level, "llm_call provider=%s model=%s latency=%.2fs ok=%s tokens=%s error=%s",
               provider, model, latency, ok, total_tokens, error or "")


def snapshot() -> dict:
    with _lock:
        return {k: dict(v) for k, v in _stats.items()}
