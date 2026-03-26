from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, TypeVar

from app.modules.pantianshou_composition import eta
from app.modules.pantianshou_composition.progress import get_redis, update_job

T = TypeVar("T")


@dataclass
class StageMaps:
    text: Dict[str, str]
    progress: Dict[str, int]


def try_get_redis() -> Any | None:
    r = None
    try:
        r = get_redis()
        r.ping()
    except Exception:
        r = None
    return r


def estimate_and_update(task_id: str, r: Any | None, bucket: str, stage: str, stage_started_at: float) -> None:
    try:
        expected = eta.get_expected_seconds(r, bucket) if r else dict(eta.DEFAULT_EXPECTED_SECONDS)
        eta_conf = eta.estimate_eta_confidence(r, bucket, stage) if r else 0.4
    except Exception:
        expected = dict(eta.DEFAULT_EXPECTED_SECONDS)
        eta_conf = 0.4
    elapsed = time.time() - stage_started_at
    eta_seconds = eta.estimate_eta_seconds(expected, stage, elapsed)
    update_job(task_id, eta_seconds=eta_seconds, eta_confidence=eta_conf)


def run_stage(
    task_id: str,
    r: Any | None,
    bucket: str,
    stage: str,
    maps: StageMaps,
    message: str,
    fn: Callable[[], T],
) -> T:
    stage_started = time.time()
    update_job(
        task_id,
        stage=stage,
        stage_text=maps.text.get(stage) or stage,
        progress=maps.progress.get(stage, 0),
        message=message,
    )
    estimate_and_update(task_id, r, bucket, stage, stage_started)
    try:
        return fn()
    finally:
        if r:
            try:
                eta.update_expected_seconds(r, bucket, stage, time.time() - stage_started)
            except Exception:
                pass
