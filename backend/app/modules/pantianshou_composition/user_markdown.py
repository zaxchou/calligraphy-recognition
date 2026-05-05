from __future__ import annotations

import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

_USER_MARKDOWN_DIR: str | None = None


def _get_user_markdown_dir() -> str:
    global _USER_MARKDOWN_DIR
    if _USER_MARKDOWN_DIR is not None:
        return _USER_MARKDOWN_DIR
    module_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(module_dir, "..", "..", "..", "..", "data")
    _USER_MARKDOWN_DIR = os.path.normpath(os.path.join(data_dir, "user_markdown", "qczh"))
    return _USER_MARKDOWN_DIR


def load_user_qczh_markdowns() -> List[Dict[str, str]]:
    markdowns: List[Dict[str, str]] = []
    md_dir = _get_user_markdown_dir()
    if not os.path.isdir(md_dir):
        logger.debug("User markdown dir not found: %s", md_dir)
        return markdowns
    try:
        for fname in sorted(os.listdir(md_dir)):
            if not fname.lower().endswith(".md"):
                continue
            if fname.startswith("_") or fname.endswith(".bak"):
                continue
            fpath = os.path.join(md_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    markdowns.append({"filename": fname, "content": content})
                    logger.debug("Loaded user markdown: %s (%d chars)", fname, len(content))
            except Exception as e:
                logger.warning("Failed to read user markdown %s: %s", fname, e)
    except Exception as e:
        logger.warning("Failed to scan user markdown dir: %s", e)
    return markdowns


def build_user_markdown_context(markdowns: List[Dict[str, str]], max_total: int = 3000) -> str:
    if not markdowns:
        return "暂无用户自定义笔记"
    lines = []
    total = 0
    for md in markdowns:
        fname = md.get("filename", "")
        content = md.get("content", "")
        if not content:
            continue
        header = f"### {fname}"
        body = content[:max(0, max_total - total - len(header) - 10)]
        entry = f"{header}\n{body}"
        if total + len(entry) > max_total:
            lines.append(f"### {fname}\n...(内容过长，已截断)")
            break
        lines.append(entry)
        total += len(entry)
    return "\n\n".join(lines) if lines else "暂无用户自定义笔记"
