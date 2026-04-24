from __future__ import annotations

from typing import Dict

import redis


DEFAULT_EXPECTED_SECONDS: Dict[str, float] = {
    "preprocess": 2.0,
    "detect": 6.0,
    "feature_extract": 6.0,
    "vector_search": 2.0,
    "report": 3.0,
}

STAGE_ORDER = ["preprocess", "detect", "feature_extract", "vector_search", "report"]


def megapixels_bucket(width: int, height: int) -> str:
    mp = (max(width, 1) * max(height, 1)) / 1_000_000.0
    if mp <= 1.0:
        return "lt1"
    if mp <= 3.0:
        return "1_3"
    if mp <= 6.0:
        return "3_6"
    return "gt6"


def _expected_hash_key(bucket: str) -> str:
    return f"composition:eta:expected:{bucket}"


def _count_hash_key(bucket: str) -> str:
    return f"composition:eta:count:{bucket}"


def get_expected_seconds(r: redis.Redis, bucket: str) -> Dict[str, float]:
    key = _expected_hash_key(bucket)
    raw = r.hgetall(key)
    expected = dict(DEFAULT_EXPECTED_SECONDS)
    for k, v in raw.items():
        try:
            stage = k.decode("utf-8")
            expected[stage] = float(v.decode("utf-8"))
        except Exception:
            continue
    return expected


def update_expected_seconds(r: redis.Redis, bucket: str, stage: str, duration_seconds: float, alpha: float = 0.25) -> None:
    key = _expected_hash_key(bucket)
    prev = r.hget(key, stage)
    if prev is None:
        new_val = duration_seconds
    else:
        try:
            prev_f = float(prev.decode("utf-8"))
            new_val = alpha * duration_seconds + (1.0 - alpha) * prev_f
        except Exception:
            new_val = duration_seconds
    r.hset(key, stage, f"{new_val:.4f}")
    r.hincrby(_count_hash_key(bucket), stage, 1)


def estimate_eta_seconds(expected: Dict[str, float], current_stage: str, elapsed_in_stage: float) -> int:
    if current_stage not in STAGE_ORDER:
        future = sum(expected.get(s, 0.0) for s in STAGE_ORDER)
        return int(max(future, 0.0))

    remain_current = max(expected.get(current_stage, 0.0) - max(elapsed_in_stage, 0.0), 0.0)
    idx = STAGE_ORDER.index(current_stage)
    remain_future = sum(expected.get(s, 0.0) for s in STAGE_ORDER[idx + 1 :])
    return int(max(remain_current + remain_future, 0.0))


def estimate_eta_confidence(r: redis.Redis, bucket: str, stage: str) -> float:
    try:
        cnt = r.hget(_count_hash_key(bucket), stage)
        n = int(cnt.decode("utf-8")) if cnt else 0
    except Exception:
        n = 0
    if n <= 0:
        return 0.2
    if n < 3:
        return 0.4
    if n < 10:
        return 0.7
    return 0.85

