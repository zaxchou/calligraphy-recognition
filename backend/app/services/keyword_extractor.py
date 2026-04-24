import html
import math
import re
import json
import os
from typing import Dict, List, Optional, Tuple

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+")
_PUNC_RE = re.compile(r"[，。！？、；：,.!?;:\(\)（）《》“”‘’\"'…—\-]+")

_WHITELIST = {
    "写意",
    "花鸟",
    "山水",
    "人物",
    "仕女",
    "佛道",
    "界画",
    "走兽",
    "草虫",
    "蔬果",
    "水墨",
    "设色",
    "工笔",
    "泼墨",
    "写生",
    "墨竹",
    "墨兰",
    "怪石",
    "兰花",
    "梅花",
    "荷花",
    "菊花",
    "松树",
    "芭蕉",
    "竹石",
    "清代",
    "扬州八怪",
    "板桥",
    "复堂",
}

_BAD_START = {"的", "为", "以", "可", "更", "并", "而", "其", "这", "那", "此", "之", "一", "幅"}
_BAD_END = {"的", "了", "为", "于", "着", "而", "其", "是", "之", "以"}


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    s = html.unescape(text)
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = _TAG_RE.sub(" ", s)
    s = _URL_RE.sub(" ", s)
    s = s.replace("\u3000", " ")
    s = _PUNC_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    m = re.search(r"关键词[:：]", s)
    if m:
        s = s[: m.start()].strip()
    for noise in ("AI分析说明", "分析说明", "题跋分析", "题跋", "款识题跋", "款识", "暂无"):
        s = s.replace(noise, " ")
    s = _WS_RE.sub(" ", s).strip()
    return s


def _default_stop_phrases() -> set:
    return {
        "作品",
        "画作",
        "此作",
        "此图",
        "本作",
        "本图",
        "画面",
        "题跋",
        "款识",
        "题款",
        "作者",
        "绘画",
        "留白",
        "题画",
        "分析",
        "说明",
        "整体",
        "体现",
        "表现",
        "采用",
        "呈现",
        "画家",
        "风格",
        "特点",
        "暂无",
        "内容",
        "可在",
        "添加",
        "系统",
        "识别",
        "区域",
        "比例",
        "占比",
        "较多",
        "较少",
        "明显",
        "丰富",
        "细腻",
        "对比",
        "突出",
        "画法",
        "构图",
        "色彩",
        "笔墨",
        "笔触",
        "此幅",
        "此作",
        "这幅",
        "之一",
        "为清",
        "为清代",
    }


def _is_bad_term(term: str, stop_phrases: set) -> bool:
    if not term:
        return True
    if len(term) < 2 or len(term) > 6:
        return True
    if any(ch.isdigit() for ch in term):
        return True
    if re.search(r"[a-zA-Z_]", term):
        return True
    if term in stop_phrases:
        return True
    if term.startswith("http"):
        return True
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,6}", term):
        return True
    if term[0] in _BAD_START:
        return True
    if term[-1] in _BAD_END:
        return True
    if "的" in term or "了" in term:
        return True
    if "为" in term and term not in _WHITELIST:
        return True
    if len(term) == 2 and term not in _WHITELIST:
        return True
    if re.fullmatch(r"[，。！？、；：,.!?;:（）()\[\]{}<>《》“”‘’\-—]+", term):
        return True
    return False


def _dedupe_terms(scored: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    kept: List[Tuple[str, float]] = []
    for term, score in scored:
        replaced = False
        for i, (kept_term, kept_score) in enumerate(list(kept)):
            if term == kept_term:
                replaced = True
                break
            if term in kept_term:
                replaced = True
                break
            if kept_term in term and len(term) > len(kept_term) and score >= kept_score:
                kept[i] = (term, score)
                replaced = True
                break
        if not replaced:
            kept.append((term, score))
    kept.sort(key=lambda x: (x[1], len(x[0])), reverse=True)
    final: List[Tuple[str, float]] = []
    for term, score in kept:
        if any(term in t for t, _ in final if t != term):
            continue
        final.append((term, score))
    return final


def _char_ngrams(text: str, n_min: int, n_max: int) -> List[str]:
    chunks = [c for c in re.split(r"\s+", text) if c]
    if not chunks:
        return []
    out: List[str] = []
    for s in chunks:
        L = len(s)
        for n in range(n_min, n_max + 1):
            if n > L:
                break
            for i in range(0, L - n + 1):
                out.append(s[i : i + n])
    return out


_WORDCLOUD_CONFIG_CACHE: Optional[Dict] = None


def load_wordcloud_config() -> Dict:
    global _WORDCLOUD_CONFIG_CACHE
    if _WORDCLOUD_CONFIG_CACHE is not None:
        return _WORDCLOUD_CONFIG_CACHE

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "resources", "wordcloud_config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {"artists": [], "subject_keywords": []}

    if not isinstance(cfg, dict):
        cfg = {"artists": [], "subject_keywords": []}

    _WORDCLOUD_CONFIG_CACHE = cfg
    return cfg


def get_artist_aliases(name: str) -> List[str]:
    cfg = load_wordcloud_config()
    for a in cfg.get("artists", []) or []:
        if a.get("name") == name:
            aliases = a.get("aliases") or []
            out = [x for x in aliases if isinstance(x, str) and x]
            if name not in out:
                out.insert(0, name)
            return out
    return [name]


def extract_wordcloud_keywords(
    documents: List[Dict[str, Optional[str]]],
    *,
    artist: Optional[str] = None,
    top_k: int = 40,
) -> Dict:
    cfg = load_wordcloud_config()
    subject_keywords = cfg.get("subject_keywords") or []
    curated_by_artist: Dict[str, List[str]] = {}
    for a in cfg.get("artists", []) or []:
        name = a.get("name")
        kws = a.get("keywords") or []
        if isinstance(name, str) and name and isinstance(kws, list):
            curated_by_artist[name] = [x for x in kws if isinstance(x, str) and x]

    texts: List[str] = []
    for doc in documents:
        analysis_note = _clean_text(doc.get("analysis_note"))
        inscription = _clean_text(doc.get("inscription_content"))
        title = _clean_text(doc.get("title"))
        notes = _clean_text(doc.get("notes"))
        merged = " ".join([title, notes, analysis_note, inscription]).strip()
        if merged:
            texts.append(merged)

    if not texts:
        return {"keywords": [], "total_keywords": 0, "total_count": 0}

    candidates = curated_by_artist.get(artist or "", []) or subject_keywords
    seen = set()
    uniq_candidates: List[str] = []
    for kw in candidates:
        if kw and kw not in seen:
            uniq_candidates.append(kw)
            seen.add(kw)

    items = []
    total_count = 0
    for kw in uniq_candidates:
        count = 0
        for t in texts:
            count += t.replace(" ", "").count(kw)
        items.append({"word": kw, "count": int(count), "score": float(count)})
        if count > 0:
            total_count += int(count)

    if candidates is not subject_keywords:
        existing = {x["word"] for x in items}
        for kw in subject_keywords:
            if kw in existing:
                continue
            count = 0
            for t in texts:
                count += t.replace(" ", "").count(kw)
            items.append({"word": kw, "count": int(count), "score": float(count)})
            if count > 0:
                total_count += int(count)

    items.sort(key=lambda x: x["count"], reverse=True)
    items = items[: max(0, int(top_k))]

    return {"keywords": items, "total_keywords": len(items), "total_count": total_count}
