from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2

from app.core.config import get_settings
from app.modules.pantianshou_composition.analyzer import to_feature_vector_512
from app.modules.pantianshou_composition.qdrant_client import ensure_collection, upsert_points
from app.modules.pantianshou_composition.storage import build_static_url

settings = get_settings()

_PAN_FIGURE_CACHE: Dict[str, PanFigureIndex] | None = None


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
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"rule:{self.rule_id}")),
            "vector": [0.0] * 512,
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
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"fig:{self.figure_id}")),
            "vector": [0.0] * 512,
            "payload": payload,
        }


def _split_figures(s: str) -> List[str]:
    s = (s or "").strip()
    if not s or s in {"通用", "通用 ", "通用\t"}:
        return []
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


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ingest_pan_md(pan_md_path: str, recreate: bool = False, ruleset_version: str | None = None) -> Dict[str, Any]:
    ruleset_version = ruleset_version or date.today().isoformat()
    text = _read_text(pan_md_path)

    rules = parse_pan_rules(text)
    figures = parse_pan_figure_index(text)

    ok_rules = ensure_collection("composition_rules", vector_size=512, recreate=recreate)
    ok_cases = ensure_collection("composition_cases", vector_size=512, recreate=recreate)

    if not ok_rules or not ok_cases:
        return {"ok": False, "error": "qdrant_unavailable"}

    rules_points = [r.point(ruleset_version) for r in rules]
    fig_points = [f.point(ruleset_version) for f in figures]

    ok1 = upsert_points("composition_rules", rules_points, wait=True)
    ok2 = upsert_points("composition_cases", fig_points, wait=True)

    return {
        "ok": bool(ok1 and ok2),
        "ruleset_version": ruleset_version,
        "rules_count": len(rules_points),
        "figures_count": len(fig_points),
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
    if not ensure_collection("composition_cases", vector_size=512, recreate=False):
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
        vec = to_feature_vector_512(img)
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
    ok = upsert_points("composition_cases", points, wait=True)
    return {"ok": bool(ok), "ruleset_version": ruleset_version, "images_read": n_read, "images_upserted": len(points), "images_skipped": n_skip}
