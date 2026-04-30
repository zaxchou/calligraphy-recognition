from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional, Tuple

from app.core.config import get_settings
from app.modules.pantianshou_composition.knowledge_storage import ensure_knowledge_dirs
from app.modules.pantianshou_composition.storage import build_static_url

settings = get_settings()

_plog_path: str | None = None


def _plog(msg: str) -> None:
    global _plog_path
    import datetime
    try:
        if _plog_path is None:
            _plog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "pipeline.log")
        with open(_plog_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} [figure] {msg}\n")
    except Exception:
        pass


def _build_qdrant_cache() -> Dict[str, str]:
    try:
        from app.modules.pantianshou_composition.qdrant_client import scroll_by_filter, KNOWLEDGE_IMAGES_COLLECTION
        pts = scroll_by_filter(KNOWLEDGE_IMAGES_COLLECTION, {}, limit=500)
        out = {}
        for pt in (pts or []):
            p = pt.get("payload") or {}
            fid = p.get("figure_id", "")
            url = p.get("image_url") or p.get("stored_url", "")
            if fid and url:
                out[str(fid)] = url
        _plog(f"qdrant_cache built: {len(pts)} points, {len(out)} with url")
        return out
    except Exception as e:
        _plog(f"qdrant_cache FAIL: {e}")
        return {}


def figure_image_url_from_qdrant(figure_id: str) -> Optional[str]:
    global _qdrant_cache, _qdrant_full_cache
    if _qdrant_cache is None:
        _qdrant_cache = {}
    fid = str(figure_id)
    if fid in _qdrant_cache:
        return _qdrant_cache[fid] or None
    if _qdrant_full_cache is None:
        _qdrant_full_cache = _build_qdrant_cache()
    if not _qdrant_full_cache:
        _qdrant_cache[fid] = ""
        return None
    candidates = [fid]
    cleaned = re.sub(r'[\(\)（（）①②③④⑤⑥⑦⑧⑨⑩⑪⑫].*$', '', fid).strip()
    if cleaned and cleaned != fid:
        candidates.append(cleaned)
    for cid in candidates:
        if cid in _qdrant_full_cache:
            url = _qdrant_full_cache[cid]
            _qdrant_cache[fid] = url
            _plog(f"FOUND: {fid} → {url[:60]}")
            return url
    # Fuzzy: extract Chinese number from fid and try matching
    num_match = re.search(r'[一二三四五六七八九十百〇]+', fid)
    if num_match:
        num = num_match.group(0)
        for k, v in _qdrant_full_cache.items():
            if num in k:
                _qdrant_cache[fid] = v
                _plog(f"FUZZY_MATCH: {fid} → {v[:60]} (via num={num} matched key={k})")
                return v
    _qdrant_cache[fid] = ""
    _plog(f"MISS: {fid} tried={candidates}, qdrant_keys_sample={list(_qdrant_full_cache.keys())[:10]}")
    return None


_cache: Dict[str, Tuple[str, str]] | None = None
_bird_flower_cache: Dict[str, Tuple[str, str]] | None = None
_resolve_cache: Dict[str, Optional[str]] = {}

# ---------------------------------------------------------------------------
# Sub-figure normalisation: reduce "图一①", "图二(一)", "图二一(反例)" etc.
# to the main figure id that exists in mapping.json  (e.g. "图一", "图二", "图二一").
# ---------------------------------------------------------------------------

# Circled digits: ① ② ③ … ⑳
_CIRCLED_RE = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]")
# Parenthesised suffix: (一), (反例), (收梢局促), (觚形) …
_PAREN_SUFFIX_RE = re.compile(r"[（(][^）)]*[）)]")
# Chinese number list (used in rules like "六五" which means 图六五)
_ZH_NUM_RE = re.compile(
    r"^[一二三四五六七八九十〇零]+$"
)


def _resolve_figure_id(raw: str) -> Optional[str]:
    """Return the canonical figure_id that exists in the mapping cache.

    Strategies applied in order:
      1. Direct lookup
      2. Strip circled-digit sub-index  (图一① → 图一)
      3. Strip parenthesised qualifier  (图二一(反例) → 图二一)
      4. Prefix bare Chinese numbers    (十七 → 图十七, 六五 → 图六五)
      5. Try adding/correcting 〇        (图二五 → 图二五 already ok)
    """
    global _cache, _resolve_cache
    if not raw:
        return None
    raw = raw.strip()
    if raw in _resolve_cache:
        return _resolve_cache[raw]
    if _cache is None:
        _cache = _build_cache()

    def _try(sid: str) -> Optional[str]:
        sid = sid.replace(" ", "").replace("圖", "图").replace("○", "〇")
        v = _cache.get(sid)
        if v:
            return sid
        return None

    # 1. Direct
    hit = _try(raw)
    if hit:
        _resolve_cache[raw] = hit
        return hit

    s = raw

    # 2. Strip circled digits
    s2 = _CIRCLED_RE.sub("", s)
    if s2 != s:
        hit = _try(s2)
        if hit:
            _resolve_cache[raw] = hit
            return hit

    # 3. Strip parenthesised suffix
    s3 = _PAREN_SUFFIX_RE.sub("", s2 if s2 != s else s)
    s3 = s3.rstrip()
    if s3 != s:
        hit = _try(s3)
        if hit:
            _resolve_cache[raw] = hit
            return hit

    # 4. Bare Chinese number → prefix with 图
    if _ZH_NUM_RE.match(s):
        hit = _try("图" + s)
        if hit:
            _resolve_cache[raw] = hit
            return hit

    # 5. Combine 3 + 4: strip parens then prefix
    s4 = _PAREN_SUFFIX_RE.sub("", s).rstrip()
    if _ZH_NUM_RE.match(s4):
        hit = _try("图" + s4)
        if hit:
            _resolve_cache[raw] = hit
            return hit

    # Also try: "图十一对比图十三" → extract first "图XX" pattern
    m = re.match(r"(图[一二三四五六七八九十〇零]+)", s)
    if m:
        hit = _try(m.group(1))
        if hit:
            _resolve_cache[raw] = hit
            return hit

    _resolve_cache[raw] = None
    return None


def _build_cache() -> Dict[str, Tuple[str, str]]:
    dirs = ensure_knowledge_dirs()
    base = dirs["base"]
    extracted_root = os.path.join(base, "extracted")
    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    out: Dict[str, Tuple[str, str]] = {}
    bird_flower: Dict[str, Tuple[str, str]] = {}
    if not os.path.isdir(extracted_root):
        return out
    for root, _, files in os.walk(extracted_root):
        if "mapping.json" not in files:
            continue
        mapping_path = os.path.join(root, "mapping.json")
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f) or {}
        except Exception:
            continue
        # Detect if this is the bird_flower_tutorial extracted dir
        is_bird_flower = "花鸟" in root or "bird_flower" in root.lower()
        for file_name, figure_id in mapping.items():
            if not file_name or not figure_id:
                continue
            img_path = os.path.join(root, os.path.basename(str(file_name)))
            if not os.path.exists(img_path):
                continue
            rel = os.path.relpath(img_path, base_data_dir)
            url = build_static_url(rel)
            entry = (img_path, url)
            fid = str(figure_id)
            # Always add to the default cache (first-come, pan.md wins)
            if fid not in out:
                out[fid] = entry
            # If bird_flower dir, also add to bird_flower cache (always wins)
            if is_bird_flower:
                bird_flower[fid] = entry
    # Invalidate resolve cache when cache is rebuilt
    _resolve_cache.clear()
    # Store bird_flower cache globally
    global _bird_flower_cache
    _bird_flower_cache = bird_flower if bird_flower else None
    import logging
    logging.getLogger(__name__).debug(
        "figure_assets cache built: default=%d entries, bird_flower=%d entries",
        len(out), len(bird_flower),
    )
    return out


def figure_image_url(figure_id: str, *, bird_flower: bool = False) -> Optional[str]:
    """Look up image URL for a figure_id.

    Args:
        figure_id: The figure identifier (e.g. '图十四')
        bird_flower: If True, search in the bird_flower_tutorial cache first.
                     Use this for panplus.md rules to avoid returning pan.md images.
    """
    global _cache, _bird_flower_cache
    if not figure_id:
        return None
    if _cache is None:
        _cache = _build_cache()
    # Try resolved id first (handles sub-figure references)
    resolved = _resolve_figure_id(figure_id)
    # Determine which cache to search
    caches = []
    if bird_flower and _bird_flower_cache:
        caches.append(_bird_flower_cache)
    caches.append(_cache)
    for cache in caches:
        if resolved:
            v = cache.get(resolved)
            if v:
                return v[1]
        # Fallback: direct lookup
        v = cache.get(figure_id)
        if v:
            return v[1]
    return None


def figure_image_path(figure_id: str, *, bird_flower: bool = False) -> Optional[str]:
    global _cache, _bird_flower_cache
    if not figure_id:
        return None
    if _cache is None:
        _cache = _build_cache()
    resolved = _resolve_figure_id(figure_id)
    caches = []
    if bird_flower and _bird_flower_cache:
        caches.append(_bird_flower_cache)
    caches.append(_cache)
    for cache in caches:
        if resolved:
            v = cache.get(resolved)
            if v:
                return v[0]
        v = cache.get(figure_id)
        if v:
            return v[0]
    return v[0] if v else None


# Qdrant figure_id -> url cache
_qdrant_cache: Dict[str, str] | None = None
_qdrant_full_cache: Dict[str, str] | None = None
