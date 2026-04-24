from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2

from app.core.config import get_settings
from app.modules.pantianshou_composition.analyzer import to_feature_vector_1024
from app.modules.pantianshou_composition.qdrant_client import ensure_collection, upsert_points, KNOWLEDGE_IMAGES_COLLECTION, KNOWLEDGE_VECTOR_SIZE
from app.modules.pantianshou_composition.storage import build_static_url

logger = logging.getLogger(__name__)
settings = get_settings()

_PAN_FIGURE_CACHE: Dict[str, PanFigureIndex] | None = None
_PANPLUS_RULE_CACHE: List[PanRule] | None = None

# Arabic → Chinese digit mapping
_ARABIC_TO_ZH = {
    "0": "〇", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}
# Chinese units for multi-digit numbers
_ZH_UNITS = {2: "十", 3: "百", 4: "千"}


def _arabic_to_chinese_num(n: int) -> str:
    """Convert an Arabic number to Chinese numeral (e.g. 14 → 十四, 100 → 一〇〇)."""
    if n <= 0:
        return "〇"
    if n <= 10:
        return {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
                6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}.get(n, str(n))
    if n < 100:
        tens = n // 10
        ones = n % 10
        if tens == 1:
            result = "十"
        else:
            result = _ARABIC_TO_ZH[str(tens)] + "十"
        if ones > 0:
            result += _ARABIC_TO_ZH[str(ones)]
        return result
    # For 100+, just convert digit by digit (e.g. 100 → 一〇〇)
    return "".join(_ARABIC_TO_ZH.get(d, d) for d in str(n))


def _normalize_figure_num(s: str) -> str:
    """Normalize figure id: convert Arabic numbers to Chinese.
    E.g. '图14' → '图十四', '图5' → '图五'
    If already Chinese, return as-is.
    """
    m = re.match(r"^(图)(\d+)$", s)
    if m:
        prefix = m.group(1)
        num = int(m.group(2))
        return prefix + _arabic_to_chinese_num(num)
    return s


def _expand_figure_range(raw: str) -> List[str]:
    """Expand figure ranges like '图7-8' into ['图七', '图八'].
    Also normalizes Arabic numbers: '图14' → ['图十四'].
    """
    # Check for range pattern: 图X-Y (Arabic numbers)
    range_m = re.match(r"^(图)(\d+)-(\d+)$", raw)
    if range_m:
        prefix = range_m.group(1)
        start = int(range_m.group(2))
        end = int(range_m.group(3))
        if start <= end:
            return [prefix + _arabic_to_chinese_num(n) for n in range(start, end + 1)]
    # Single figure: normalize
    normalized = _normalize_figure_num(raw)
    return [normalized] if normalized else []


def _norm_figure_id(s: str) -> str:
    s = (s or "").strip()
    s = s.replace(" ", "")
    s = s.replace("圖", "图")
    s = s.replace("○", "〇")
    return s


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _load_pan_figure_index() -> Dict[str, PanFigureIndex]:
    global _PAN_FIGURE_CACHE
    if _PAN_FIGURE_CACHE is not None:
        return _PAN_FIGURE_CACHE
    pan_md = os.path.join(_repo_root(), "pan.md")
    if not os.path.exists(pan_md):
        _PAN_FIGURE_CACHE = {}
        return _PAN_FIGURE_CACHE
    text = _read_text(pan_md)
    figs = parse_pan_figure_index(text)
    out: Dict[str, PanFigureIndex] = {}
    for it in figs:
        out[_norm_figure_id(it.figure_id)] = it
    _PAN_FIGURE_CACHE = out
    return out


_CATEGORY_RE = re.compile(r"^##\s*.*?、\s*(?P<name>.+?)规则（(?P<code>[A-Z]{2})）")
_SUBCATEGORY_RE = re.compile(r"^###\s*\d+(?:\.\d+)?\s+(?P<name>.+)$")
_TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|$")


@dataclass(frozen=True)
class PanRule:
    rule_id: str
    rule_name: str
    condition: str
    quantitative_standard: str
    reference_figures: List[str]
    weight: float
    category_name: str
    category_code: str
    subcategory_name: str

    def point(self, ruleset_version: str) -> Dict[str, Any]:
        payload = {
            "type": "pantianshou_rule",
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category_name,
            "category_code": self.category_code,
            "subcategory": self.subcategory_name,
            "condition": self.condition,
            "quantitative_standard": self.quantitative_standard,
            "weight": float(self.weight),
            "reference_figures": list(self.reference_figures),
            "ruleset_version": ruleset_version,
            "source": "pan.md",
        }
        # 生成语义向量：基于规则文本内容构建可搜索的表示
        vector = _generate_rule_vector(self)
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"rule:{self.rule_id}")),
            "vector": vector,
            "payload": payload,
        }


@dataclass(frozen=True)
class PanFigureIndex:
    figure_id: str
    figure_type: str
    score_ref: float | None
    description: str

    def point(self, ruleset_version: str) -> Dict[str, Any]:
        payload = {
            "type": "pantianshou_illustration",
            "figure_id": self.figure_id,
            "figure_type": self.figure_type,
            "score_ref": self.score_ref,
            "description": self.description,
            "ruleset_version": ruleset_version,
            "source": "pan.md",
        }
        # Note: PanFigureIndex uses hash-based vectors (not semantic embeddings).
        # These are padded/zero vectors for text-searchable metadata only.
        vector = _generate_figure_vector(self)
        # Pad to 1024 dimensions if needed (hash vectors are 512-dim)
        if len(vector) < 1024:
            vector = vector + [0.0] * (1024 - len(vector))
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fig:{self.figure_id}")),
            "vector": vector,
            "payload": payload,
        }


def _split_figures(s: str) -> List[str]:
    s = (s or "").strip()
    if not s or s in {"通用", "通用 ", "通用\t"}:
        return []
    # First, handle "鸟花教程 图X ..." format: extract just the figure id
    # Pattern: 鸟花教程 followed by 图 + number (Arabic or Chinese)
    bird_tutorial_re = re.compile(r"鸟花教程\s*(图\d+(?:-\d+)?|图[一二三四五六七八九十〇零]+)")
    bird_match = bird_tutorial_re.search(s)
    if bird_match:
        raw_fig = bird_match.group(1)
        results = _expand_figure_range(raw_fig)
        return results if results else []

    s = s.replace(" ", "")
    parts: List[str] = []
    for chunk in re.split(r"[、，,;；]", s):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "/" in chunk:
            segs = [p for p in chunk.split("/") if p]
            if not segs:
                continue
            prefix = ""
            first = segs[0]
            if first.startswith("图") or first.startswith("圖"):
                prefix = "图"
            parts.append(first.replace("圖", "图"))
            for seg in segs[1:]:
                seg = seg.strip()
                if not seg:
                    continue
                if (seg.startswith("图") or seg.startswith("圖")) or not prefix:
                    parts.append(seg.replace("圖", "图"))
                else:
                    parts.append(prefix + seg)
        else:
            parts.append(chunk.replace("圖", "图"))
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def _parse_weight(cell: str) -> float:
    cell = (cell or "").strip()
    if not cell:
        return 0.0
    if cell.endswith("%"):
        try:
            return float(cell[:-1]) / 100.0
        except Exception:
            return 0.0
    try:
        v = float(cell)
        if v > 1.0:
            return v / 100.0
        return v
    except Exception:
        return 0.0


def _iter_table_rows(lines: List[str], start_idx: int) -> Tuple[int, List[List[str]]]:
    rows: List[List[str]] = []
    i = start_idx
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if not line.strip():
            break
        if not line.lstrip().startswith("|"):
            break
        m = _TABLE_ROW_RE.match(line.strip())
        if not m:
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
        i += 1
    return i, rows


def parse_pan_rules(md_text: str) -> List[PanRule]:
    lines = md_text.splitlines()
    rules: List[PanRule] = []
    category_name = ""
    category_code = ""
    subcategory_name = ""
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        m_cat = _CATEGORY_RE.match(line.strip())
        if m_cat:
            category_name = m_cat.group("name").strip()
            category_code = m_cat.group("code").strip()
            i += 1
            continue

        m_sub = _SUBCATEGORY_RE.match(line.strip())
        if m_sub:
            subcategory_name = m_sub.group("name").strip()
            if subcategory_name.endswith("规则"):
                subcategory_name = subcategory_name[:-2]
            i += 1
            continue

        if line.strip().startswith("|") and "规则ID" in line:
            i += 1
            if i < len(lines) and set(lines[i].replace("|", "").strip()) <= {"-", " "}:
                i += 1
            end_i, rows = _iter_table_rows(lines, i)
            for cells in rows:
                if len(cells) < 6:
                    continue
                rule_id, rule_name, condition, quantitative, refs, weight = cells[:6]
                rule_id = rule_id.strip()
                if not rule_id or rule_id.lower() == "规则id":
                    continue
                rules.append(
                    PanRule(
                        rule_id=rule_id,
                        rule_name=rule_name.strip(),
                        condition=condition.strip(),
                        quantitative_standard=quantitative.strip(),
                        reference_figures=_split_figures(refs),
                        weight=_parse_weight(weight),
                        category_name=category_name,
                        category_code=category_code,
                        subcategory_name=subcategory_name,
                    )
                )
            i = end_i
            continue

        i += 1
    return rules


def parse_pan_figure_index(md_text: str) -> List[PanFigureIndex]:
    lines = md_text.splitlines()
    items: List[PanFigureIndex] = []
    i = 0
    section: str | None = None
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("### 正例插图"):
            section = "positive"
            i += 1
            continue
        if line.startswith("### 反例插图"):
            section = "negative"
            i += 1
            continue
        if section and line.startswith("|") and "图号" in line and "特点描述" in line:
            i += 1
            if i < len(lines) and set(lines[i].replace("|", "").strip()) <= {"-", " "}:
                i += 1
            end_i, rows = _iter_table_rows(lines, i)
            for cells in rows:
                if len(cells) < 4:
                    continue
                fig_cell, _, score_cell, desc = cells[:4]
                for fig in _split_figures(fig_cell):
                    score_ref = None
                    try:
                        score_ref = float(str(score_cell).strip())
                    except Exception:
                        score_ref = None
                    items.append(
                        PanFigureIndex(
                            figure_id=fig,
                            figure_type=section,
                            score_ref=score_ref,
                            description=str(desc).strip(),
                        )
                    )
            i = end_i
            continue
        if section and line.startswith("|") and "违规规则" in line and "扣分参考" in line:
            i += 1
            if i < len(lines) and set(lines[i].replace("|", "").strip()) <= {"-", " "}:
                i += 1
            end_i, rows = _iter_table_rows(lines, i)
            for cells in rows:
                if len(cells) < 4:
                    continue
                fig_cell, _, score_cell, desc = cells[:4]
                for fig in _split_figures(fig_cell):
                    score_ref = None
                    try:
                        score_ref = float(str(score_cell).strip())
                    except Exception:
                        score_ref = None
                    items.append(
                        PanFigureIndex(
                            figure_id=fig,
                            figure_type=section,
                            score_ref=score_ref,
                            description=str(desc).strip(),
                        )
                    )
            i = end_i
            continue
        i += 1
    uniq: Dict[str, PanFigureIndex] = {}
    for it in items:
        if it.figure_id not in uniq:
            uniq[it.figure_id] = it
    return list(uniq.values())


def _generate_rule_vector(rule: "PanRule") -> List[float]:
    """为规则生成基于文本内容的确定性语义向量。
    
    使用 TF-IDF 简化版 + hash 映射到 512 维。
    这比零向量好得多：至少同类别的规则会聚集在一起。
    
    未来改进方向：使用 CLIP 文本编码器或 DashScope embedding API。
    """
    import hashlib
    
    # 构建规则的关键文本
    text_parts = [
        rule.category_name or "",
        rule.category_code or "",
        rule.subcategory_name or "",
        rule.rule_name or "",
        rule.condition or "",
        rule.quantitative_standard or "",
    ]
    full_text = " ".join(t for t in text_parts if t)
    
    # 方法: 多个 hash 函数映射到 512 维，模拟 minhash/feature hashing
    vector = [0.0] * 512
    tokens = re.split(r"[\s,，。；;：:、（）()\[\]【】「」""'']+|(?<=[a-zA-Z])(?=[a-zA-Z])", full_text)
    
    for token in tokens:
        token = token.strip().lower()
        if not token or len(token) < 2:
            continue
        
        # 每个字符/词贡献到多个维度
        h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        h2 = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        
        # 使用 hash 高位选维度，低位定符号
        dim1 = h1 % 512
        sign1 = 1.0 if (h1 >> 16) % 2 == 0 else -1.0
        vector[dim1] += sign1 * 0.3
        
        dim2 = h2 % 512
        sign2 = 1.0 if (h2 >> 16) % 2 == 0 else -1.0
        vector[dim2] += sign2 * 0.2
        
        # 单字粒度：中文每个字也贡献
        if any('\u4e00' <= c <= '\u9fff' for c in token):
            for char in token:
                if '\u4e00' <= char <= '\u9fff':
                    h3 = int(hashlib.md5(char.encode("utf-8")).hexdigest(), 16)
                    dim3 = h3 % 512
                    sign3 = 1.0 if (h3 >> 16) % 2 == 0 else -1.0
                    vector[dim3] += sign3 * 0.15
    
    # 类别编码器: 给类别维度更强的信号
    category_map = {"KH": 0, "XS": 100, "SM": 200, "QS": 300, "FZ": 400, "JH": 50, "CC": 150, "BJ": 250, "GF": 350, "MC": 450}
    cat_code = rule.category_code or ""
    cat_base = category_map.get(cat_code, 0)
    for i in range(10):
        idx = (cat_base + i) % 512
        vector[idx] += 0.5
    
    # L2 归一化
    import math
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    
    return vector


def _generate_figure_vector(figure: "PanFigureIndex") -> List[float]:
    """为插图索引生成基于图号和描述的确定性语义向量。"""
    import hashlib
    import math
    
    text_parts = [
        figure.figure_id or "",
        figure.figure_type or "",
        figure.description or "",
    ]
    full_text = " ".join(t for t in text_parts if t)
    
    vector = [0.0] * 512
    tokens = re.split(r"[\s,，。；;：:、（）()\[\]【】「」""'']+|(?<=[a-zA-Z])(?=[a-zA-Z])", full_text)
    
    for token in tokens:
        token = token.strip().lower()
        if not token:
            continue
        
        h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        h2 = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        
        dim1 = h1 % 512
        sign1 = 1.0 if (h1 >> 16) % 2 == 0 else -1.0
        vector[dim1] += sign1 * 0.3
        
        dim2 = h2 % 512
        sign2 = 1.0 if (h2 >> 16) % 2 == 0 else -1.0
        vector[dim2] += sign2 * 0.2
        
        for char in token:
            if '\u4e00' <= char <= '\u9fff':
                h3 = int(hashlib.md5(char.encode("utf-8")).hexdigest(), 16)
                dim3 = h3 % 512
                sign3 = 1.0 if (h3 >> 16) % 2 == 0 else -1.0
                vector[dim3] += sign3 * 0.15
    
    # 正例/反例信号
    if figure.figure_type == "positive":
        vector[0] += 0.5
        vector[1] += 0.5
    elif figure.figure_type == "negative":
        vector[0] -= 0.5
        vector[1] -= 0.5
    
    # L2 归一化
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    
    return vector


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ingest_pan_md(pan_md_path: str, recreate: bool = False, ruleset_version: str | None = None) -> Dict[str, Any]:
    """Ingest pan.md figures into knowledge_images collection.

    NOTE: composition_rules and composition_cases collections are DEPRECATED.
    Rules are matched by rule_matcher.py (keyword logic), not vector search.
    Figures are now stored in knowledge_images (1024-dim multimodal).
    """
    ruleset_version = ruleset_version or date.today().isoformat()
    text = _read_text(pan_md_path)

    # Only parse figures — rules go to rule_matcher, not Qdrant
    figures = parse_pan_figure_index(text)

    ok_cases = ensure_collection(KNOWLEDGE_IMAGES_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE, recreate=recreate)

    if not ok_cases:
        return {"ok": False, "error": "qdrant_unavailable"}

    fig_points = [f.point(ruleset_version) for f in figures]

    ok = upsert_points(KNOWLEDGE_IMAGES_COLLECTION, fig_points, wait=True)

    return {
        "ok": bool(ok),
        "ruleset_version": ruleset_version,
        "rules_count": 0,  # Rules no longer stored in Qdrant
        "figures_count": len(fig_points),
        "collection": KNOWLEDGE_IMAGES_COLLECTION,
    }


def _load_mapping(mapping_path: str | None) -> Dict[str, str]:
    if not mapping_path:
        return {}
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, str] = {}
    for k, v in (data or {}).items():
        if not k or not v:
            continue
        out[str(k)] = str(v)
    return out


def _iter_image_files(images_dir: str) -> Iterable[str]:
    for name in os.listdir(images_dir):
        if name.startswith("."):
            continue
        lower = name.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            yield os.path.join(images_dir, name)


def ingest_illustration_images(
    images_dir: str,
    mapping_json: str | None = None,
    ruleset_version: str | None = None,
    skip_unmapped: bool = False,
) -> Dict[str, Any]:
    ruleset_version = ruleset_version or date.today().isoformat()
    if not ensure_collection(KNOWLEDGE_IMAGES_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE, recreate=False):
        return {"ok": False, "error": "qdrant_unavailable"}

    mapping = _load_mapping(mapping_json)
    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    pan_meta = _load_pan_figure_index() if mapping else {}
    points: List[Dict[str, Any]] = []
    n_read = 0
    n_skip = 0
    for path in _iter_image_files(images_dir):
        n_read += 1
        fname = os.path.basename(path)
        stem = os.path.splitext(fname)[0]
        if skip_unmapped and mapping and (fname not in mapping) and (stem not in mapping):
            n_skip += 1
            continue
        figure_id = mapping.get(fname) or mapping.get(stem) or stem
        figure_id = _norm_figure_id(str(figure_id))
        img = cv2.imread(path)
        if img is None:
            n_skip += 1
            continue
        rel = os.path.relpath(path, base_data_dir)
        image_url = build_static_url(rel)
        meta = pan_meta.get(figure_id) if pan_meta else None
        figure_type = meta.figure_type if meta else "unknown"
        description = meta.description if meta else ""
        score_ref = meta.score_ref if meta else None
        vec = to_feature_vector_1024(path)
        points.append(
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fig:{figure_id}")),
                "vector": vec,
                "payload": {
                    "type": "pantianshou_illustration",
                    "figure_id": figure_id,
                    "figure_type": figure_type,
                    "score_ref": score_ref,
                    "description": description,
                    "ruleset_version": ruleset_version,
                    "source": "uploaded_images",
                    "file_name": fname,
                    "image_url": image_url,
                },
            }
        )
    ok = upsert_points(KNOWLEDGE_IMAGES_COLLECTION, points, wait=True)
    return {"ok": bool(ok), "ruleset_version": ruleset_version, "images_read": n_read, "images_upserted": len(points), "images_skipped": n_skip, "collection": KNOWLEDGE_IMAGES_COLLECTION}


# ======================================================================
# panplus.md support (写意花鸟画教程补充规则)
# ======================================================================

# Regex for supplementary sections like "开合结构新增（3条）"
_SUPPLEMENT_RE = re.compile(r"^###\s*(?P<cat_name>.+?)新增（\d+条）")
_SUPPLEMENT_CAT_MAP = {
    "开合结构": ("KH", "开合结构"),
    "虚实关系": ("XS", "虚实关系"),
    "疏密布局": ("SM", "疏密布局"),
    "气势趋向": ("QS", "气势趋向"),
    "辅助元素": ("FZ", "辅助元素"),
}


def parse_panplus_supplement_rules(md_text: str) -> List[PanRule]:
    """Parse the supplementary rules section at the end of panplus.md.

    These are rules that extend existing pan.md categories (KH/XS/SM/QS/FZ)
    with new rule IDs. The section header format is:
        ### 开合结构新增（3条）
    followed by a markdown table with rule_id, rule_name, etc.
    """
    lines = md_text.splitlines()
    rules: List[PanRule] = []
    i = 0
    current_cat_code = ""
    current_cat_name = ""
    current_subcat = ""

    while i < len(lines):
        line = lines[i].rstrip("\n")
        m_sup = _SUPPLEMENT_RE.match(line.strip())
        if m_sup:
            raw_name = m_sup.group("cat_name").strip()
            mapped = _SUPPLEMENT_CAT_MAP.get(raw_name)
            if mapped:
                current_cat_code, current_cat_name = mapped
            else:
                current_cat_code = ""
                current_cat_name = raw_name
            i += 1
            continue

        # Match category headers (JH, CC, BJ) — reuse existing regex
        m_cat = _CATEGORY_RE.match(line.strip())
        if m_cat:
            current_cat_name = m_cat.group("name").strip()
            current_cat_code = m_cat.group("code").strip()
            i += 1
            continue

        m_sub = _SUBCATEGORY_RE.match(line.strip())
        if m_sub:
            current_subcat = m_sub.group("name").strip()
            if current_subcat.endswith("规则"):
                current_subcat = current_subcat[:-2]
            i += 1
            continue

        if line.strip().startswith("|") and "规则ID" in line:
            i += 1
            if i < len(lines) and set(lines[i].replace("|", "").strip()) <= {"-", " "}:
                i += 1
            end_i, rows = _iter_table_rows(lines, i)
            for cells in rows:
                if len(cells) < 6:
                    continue
                rule_id, rule_name, condition, quantitative, refs, weight = cells[:6]
                rule_id = rule_id.strip()
                if not rule_id or rule_id.lower() == "规则id":
                    continue
                rules.append(
                    PanRule(
                        rule_id=rule_id,
                        rule_name=rule_name.strip(),
                        condition=condition.strip(),
                        quantitative_standard=quantitative.strip(),
                        reference_figures=_split_figures(refs),
                        weight=_parse_weight(weight),
                        category_name=current_cat_name,
                        category_code=current_cat_code,
                        subcategory_name=current_subcat,
                    )
                )
            i = end_i
            continue

        i += 1
    return rules


def load_panplus_rules(panplus_md_path: str | None = None) -> List[PanRule]:
    """Load and cache panplus rules from panplus.md."""
    global _PANPLUS_RULE_CACHE
    if _PANPLUS_RULE_CACHE is not None:
        return _PANPLUS_RULE_CACHE
    if panplus_md_path is None:
        panplus_md_path = os.path.join(_repo_root(), "panplus.md")
    if not os.path.exists(panplus_md_path):
        _PANPLUS_RULE_CACHE = []
        return _PANPLUS_RULE_CACHE
    text = _read_text(panplus_md_path)
    # Parse main JH/CC/BJ rules using existing parser
    main_rules = parse_pan_rules(text)
    # Parse supplementary KH/XS/SM/QS/FZ rules
    supplement_rules = parse_panplus_supplement_rules(text)
    # Merge: deduplicate by rule_id
    seen: Dict[str, PanRule] = {}
    for r in main_rules + supplement_rules:
        if r.rule_id not in seen:
            seen[r.rule_id] = r
    _PANPLUS_RULE_CACHE = list(seen.values())
    return _PANPLUS_RULE_CACHE


def ingest_panplus_md(
    panplus_md_path: str | None = None,
    recreate: bool = False,
    ruleset_version: str | None = None,
) -> Dict[str, Any]:
    """Ingest panplus.md rules — stored locally only, NOT in Qdrant.

    NOTE: composition_rules collection is DEPRECATED.
    Rule matching uses rule_matcher.py (keyword logic), not vector search.
    This function now only clears the panplus cache for fresh re-parsing.
    """
    ruleset_version = ruleset_version or date.today().isoformat()
    if panplus_md_path is None:
        panplus_md_path = os.path.join(_repo_root(), "panplus.md")
    text = _read_text(panplus_md_path)

    # Parse to verify rules are valid
    main_rules = parse_pan_rules(text)
    supplement_rules = parse_panplus_supplement_rules(text)
    all_rules = main_rules + supplement_rules

    # Deduplicate by rule_id
    seen: Dict[str, PanRule] = {}
    for r in all_rules:
        if r.rule_id not in seen:
            seen[r.rule_id] = r
    all_rules = list(seen.values())

    # Clear cache so load_panplus_rules() re-reads next time
    global _PANPLUS_RULE_CACHE
    _PANPLUS_RULE_CACHE = None

    return {
        "ok": True,
        "ruleset_version": ruleset_version,
        "rules_count": len(all_rules),
        "source": "panplus.md",
        "note": "Rules stored locally (rule_matcher.py), not in Qdrant",
    }
