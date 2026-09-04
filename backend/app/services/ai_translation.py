"""AI 分析内容的读时英文替换服务。

- ai_text_translations 表按「原文精确匹配」存中文→英文译文
- collect_cjk_strings(): 从 tiba_analysis 的 content_analysis / analysis_note 提取全部中文串
- translate_strings(): 调 DeepSeek 批量翻译（供回填脚本用）
- translate_json(): 读接口用，递归替换 JSON 里的中文（内存缓存，TTL 刷新）
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.ai_text_translation import AiTextTranslation

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_MIN_LEN = 2          # 短于该长度的串不收集
_CACHE_TTL = 600      # 秒；到期后下次请求重新加载
_cache_lock = threading.Lock()
_cache: Optional[dict] = None
_cache_loaded_at = 0.0


def has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))


def _translatable(s: str) -> bool:
    """值得翻译的字符串：含中文、长度达标、非纯符号。"""
    if not isinstance(s, str) or len(s) < _MIN_LEN or not has_cjk(s):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", s))


# ── 收集 ─────────────────────────────────────────────────────────────

def _walk_collect(obj: Any, out: set) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_collect(v, out)
    elif isinstance(obj, str):
        if _translatable(obj):
            out.add(obj)


def collect_cjk_strings(db: Session, limit_rows: Optional[int] = None) -> List[str]:
    """扫全表，返回待翻译的中文串（去重、排序）。"""
    from app.models.tiba_analysis import TibaAnalysis

    query = db.query(TibaAnalysis).filter(
        TibaAnalysis.content_analysis.isnot(None) | TibaAnalysis.analysis_note.isnot(None)
    )
    if limit_rows:
        query = query.limit(limit_rows)
    out: set = set()
    for row in query.all():
        if row.analysis_note:
            _walk_collect(row.analysis_note, out)
        ca = row.content_analysis
        if ca:
            try:
                _walk_collect(json.loads(ca), out)
            except (ValueError, TypeError):
                # 非 JSON 的纯文本也收
                if _translatable(ca):
                    out.add(ca)
    return sorted(out)


# ── 翻译（回填用） ────────────────────────────────────────────────────

TRANSLATE_PROMPT = """You are a translator for a Chinese painting & calligraphy analysis website.
Translate each Chinese snippet below into concise, natural English suitable for a museum-style analysis UI.
Rules:
- Keep proper nouns (artist names, seal inscriptions, painting titles) in Chinese, adding pinyin where helpful, e.g. "Li Shan (李鱓)".
- Keep the original meaning; do not add explanations.
- If a snippet is a label or a short phrase, translate it as a short phrase.

Return ONLY a JSON array of objects: [{"i": <index>, "en": "<translation>"}]

Snippets:
{payload}
"""


def _translate_one_batch(batch: List[str]) -> dict:
    from app.llm.client import chat_completion

    payload = json.dumps([{"i": i, "zh": s} for i, s in enumerate(batch)],
                         ensure_ascii=False, indent=0)
    prompt = TRANSLATE_PROMPT.replace("{payload}", payload)
    resp = chat_completion(
        [{"role": "user", "content": prompt}],
        max_tokens=8000, temperature=0.1, retries=3, timeout=180,
    )
    content = resp["choices"][0]["message"]["content"]
    m = re.search(r"\[.*\]", content, re.S)
    parsed = json.loads(m.group(0)) if m else []
    out = {}
    for item in parsed:
        i, en = int(item["i"]), str(item["en"]).strip()
        if 0 <= i < len(batch) and en:
            out[batch[i]] = en
    return out


def translate_strings(strings: List[str], batch_size: int = 20) -> dict:
    """批量调 LLM 翻译，返回 {中文: 英文}。整批失败则二分重试。"""

    def run(batch: List[str], out: dict) -> None:
        if not batch:
            return
        try:
            out.update(_translate_one_batch(batch))
        except Exception as e:  # noqa: BLE001 — 单批失败降级为二分重试
            if len(batch) == 1:
                print(f"  [skip 1 item] {e}")
                return
            mid = len(batch) // 2
            run(batch[:mid], out)
            run(batch[mid:], out)

    result: dict = {}
    for start in range(0, len(strings), batch_size):
        run(strings[start:start + batch_size], result)
    return result


def backfill(db: Session, batch_size: int = 20, limit_rows: Optional[int] = None,
             dry: bool = False) -> dict:
    """全量回填：收集→过滤已译→LLM 翻译→入库。返回统计。"""
    existing = {row.zh for row in db.query(AiTextTranslation.zh).all()}
    strings = [s for s in collect_cjk_strings(db, limit_rows=limit_rows) if s not in existing]
    stats = {"total_unique": len(strings), "translated": 0, "failed": 0}
    if dry:
        stats["skipped_dry"] = True
        return stats
    for start in range(0, len(strings), batch_size):
        batch = strings[start:start + batch_size]
        translated = translate_strings(batch, batch_size=batch_size)
        for zh in batch:
            en = translated.get(zh)
            if en:
                db.merge(AiTextTranslation(zh=zh, en=en, source="llm"))
                stats["translated"] += 1
            else:
                stats["failed"] += 1
        db.commit()
        print(f"  progress: {min(start + batch_size, len(strings))}/{len(strings)}"
              f" (ok {stats['translated']}, fail {stats['failed']})")
    invalidate_cache()
    return stats


# ── 读时替换 ─────────────────────────────────────────────────────────

# 只翻译纯展示文本字段。枚举/逻辑字段（name/type/emotion/theme/tags/position/
# size_category/layout_type 等）是前端做匹配计算的键，翻译会破坏渲染逻辑
# （如 getInscriptionAreaClass 按 form_types[].name 匹配、'左上' 方位查表）。
_DISPLAY_KEYS = {
    "reasoning", "detail", "desc", "description", "note", "summary",
    "analysis_note", "blank_analysis", "combined_spatial_sentiment",
    "overall_reasoning", "themes_reasoning", "inscription_modern",
}


def _load_cache(db: Session) -> dict:
    return {row.zh: row.en for row in db.query(AiTextTranslation.zh, AiTextTranslation.en).all()}


def get_cache(db: Session, force: bool = False) -> dict:
    """进程内缓存；TTL 到期或 force 时重载。"""
    global _cache, _cache_loaded_at
    with _cache_lock:
        now = time.time()
        if _cache is None or force or now - _cache_loaded_at > _CACHE_TTL:
            _cache = _load_cache(db)
            _cache_loaded_at = now
        return _cache


def invalidate_cache() -> None:
    global _cache, _cache_loaded_at
    with _cache_lock:
        _cache = None
        _cache_loaded_at = 0.0


def _walk_replace(obj: Any, cache: dict, in_display: bool = False) -> Any:
    if isinstance(obj, dict):
        return {k: _walk_replace(v, cache, k in _DISPLAY_KEYS) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_replace(v, cache, in_display) for v in obj]
    if isinstance(obj, str):
        if in_display and obj in cache:
            return cache[obj]
        # 接口可能把整个分析 JSON 作为字符串返回：解析后按白名单替换再序列化；
        # 无变化则原样返回（避免 float 格式/键序抖动）
        stripped = obj.lstrip()
        if len(stripped) > 1 and stripped[0] in "{[" and has_cjk(obj):
            try:
                parsed = json.loads(obj)
                replaced = _walk_replace(parsed, cache)
                if replaced != parsed:
                    return json.dumps(replaced, ensure_ascii=False)
            except (ValueError, TypeError):
                pass
        return obj
    return obj


def translate_json(data: Any, db: Session) -> Any:
    """EN 请求的响应体替换：仅展示字段、且精确命中缓存才换英文，否则原样。"""
    return _walk_replace(data, get_cache(db))
