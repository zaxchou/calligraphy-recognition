from __future__ import annotations

import base64
import io
import json
import re
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

from app.core.config import get_settings

settings = get_settings()


def _encode_image_to_base64(image_path: str, max_side: int = 1024, quality: int = 80) -> str:
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        width, height = img.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / float(longest)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        return base64.b64encode(data).decode("utf-8")


def _build_chat_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _safe_json(obj: Any, max_len: int = 6000) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def generate_composition_narrative(
    *,
    image_path: str,
    original_url: str,
    metrics: Dict[str, Any],
    checks: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    references: List[Dict[str, Any]],
    comparisons: List[Dict[str, Any]],
    theory_basis: List[Dict[str, Any]],
    example_images: List[Dict[str, Any]],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    if not (settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL):
        return {"ok": False, "error": "qwen_unavailable"}

    model = (model or settings.COMPOSITION_LLM_MODEL or settings.QWEN_MODEL).strip()
    b64 = _encode_image_to_base64(image_path)
    prompt = f"""你是“潘天寿教你构图”的专业讲评助手。你必须基于提供的客观数据（指标、案例相似检索、对比差异、以及 pan.md 规则条目）生成讲评，避免凭空猜测。

图像URL：{original_url}

【客观指标 metrics】{_safe_json(metrics)}
【环节打分 checks】{_safe_json(checks)}
【关键问题 issues】{_safe_json(issues)}
【相似案例 references】{_safe_json(references)}
【对比差异 comparisons】{_safe_json(comparisons)}
【原文依据 theory_basis（来自 pan.md 规则表）】{_safe_json(theory_basis)}
【可用示例图片（用于插入正文）example_images】{_safe_json(example_images)}

输出要求：
1) 必须输出 Markdown，结构参考：
   - ## 📘 一、整体构图结构
   - ## 📘 二、分项分析（起承转合/虚实与留白/疏密对比/势/题跋布局）
   - ## 📈 综合评分表（用 Markdown 表格输出）
   - ## 💡 改进建议（潘天寿式重构，编号列表）
   - ## 🧭 结语
2) 不要输出任何内部编号与算法术语：不得输出 rule_id、图号编号（如 KH-01-03）、不得输出 blank_ratio/角度差等原始数值。
3) 每条建议必须说明“依据”：用老师口吻引用原文要点（来自 theory_basis 的 rule_name/condition/quantitative_standard，但不要带编号），并说明该条与当前作品如何对应。
4) 至少给出 5 条“可执行修改动作”，每条包含：动作、理由、依据（用原文要点转述，不要编号）、预期影响（对应评分维度）。
4) 对比分析部分必须引用至少 2 条 comparisons（如果存在），并解释“当前 vs 参考”差异意味着什么。
5) 关键点用 ✅ / ❗ / 📌 / ⚠️ 标记，避免空泛套话；只根据输入数据与图像内容推断，不得编造引用与案例。
6) 必须把示例图片“融入正文”：在对应段落插入 Markdown 图片，格式：![简短标题](image_url)；从 example_images 中挑选 3-6 张插入，并在插图上下用 1-2 句解释这张图为什么能说明问题/改法。
"""

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "stream": False,
        "max_tokens": int(getattr(settings, "COMPOSITION_LLM_MAX_TOKENS", 2500)),
        "temperature": 0.4,
    }

    url = _build_chat_url(settings.QWEN_BASE_URL)
    headers = {"Authorization": f"Bearer {settings.QWEN_API_KEY}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0, read=80.0, write=30.0)) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            text = (content or "").strip()
            if text.startswith("```"):
                text = text.lstrip("`").strip()
            text = _postprocess_text(text, example_images)
            return {"ok": True, "model": model, "text": text}
    except Exception as e:
        fallback = (settings.QWEN_MODEL or "").strip()
        if fallback and fallback != model:
            payload["model"] = fallback
            try:
                with httpx.Client(timeout=httpx.Timeout(90.0, connect=10.0, read=80.0, write=30.0)) as client:
                    r = client.post(url, headers=headers, json=payload)
                    r.raise_for_status()
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    text = (content or "").strip()
                    if text.startswith("```"):
                        text = text.lstrip("`").strip()
                    text = _postprocess_text(text, example_images)
                    return {"ok": True, "model": fallback, "text": text}
            except Exception:
                pass
        return {"ok": False, "error": str(e), "model": model}


_FORBIDDEN_RE = re.compile(
    r"(KH-\d{2}-\d{2,3})|(rule_id)|(blank_ratio)|(too_void)|(too_dense)|(flat_rhythm)|(parallel)|(严重度\s*[:：]?\s*\d+)",
    re.IGNORECASE,
)


def _postprocess_text(text: str, example_images: List[Dict[str, Any]]) -> str:
    t = (text or "").strip()
    t = _FORBIDDEN_RE.sub("", t)
    if "![" not in t and example_images:
        items = []
        for it in example_images[:6]:
            url = (it.get("image_url") or "").strip()
            if not url:
                continue
            title = (it.get("title") or "示例图").strip()
            note = (it.get("note") or "").strip()
            items.append(f"![{title}]({url})")
            if note:
                items.append(f"> {note}")
        if items:
            t = t + "\n\n## 🖼️ 示例图讲解\n\n" + "\n\n".join(items) + "\n"
    return t.strip()
