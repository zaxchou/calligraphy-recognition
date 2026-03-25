from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from typing import Any, List, Tuple

from PIL import Image

from app.modules.pantianshou_composition.knowledge_storage import ensure_knowledge_dirs


_FIGURE_RE = re.compile(r"(图|圖)\s*([0-9]+|[一二三四五六七八九十百〇零○]+)(?:\s*[\(（]([一二三四五六七八九十0-9]+)[\)）])?(?:\s*([①②③④⑤⑥⑦⑧⑨⑩]))?")


@dataclass(frozen=True)
class ExtractedImage:
    file_name: str
    stored_path: str
    stored_url: str
    page: int
    index_in_page: int
    figure_id: str | None = None


def _safe_stem(path: str) -> str:
    base = os.path.basename(path)
    stem = os.path.splitext(base)[0]
    return stem.replace(" ", "_")


def _to_png(image_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode not in {"RGB", "RGBA"}:
            im = im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        return out.getvalue()


def _norm_figure_id(s: str) -> str:
    s = (s or "").strip()
    s = s.replace(" ", "")
    s = s.replace("圖", "图")
    s = s.replace("○", "〇")
    return s


def _rect_overlap_ratio(ax0: float, ax1: float, bx0: float, bx1: float) -> float:
    inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    denom = max(1.0, min(ax1 - ax0, bx1 - bx0))
    return inter / denom


def _find_near_figure_text(page: Any, rect: Any) -> str | None:
    blocks = page.get_text("blocks") or []
    best = None
    best_dist = 1e18
    rx0 = float(rect.x0)
    rx1 = float(rect.x1)
    ry0 = float(rect.y0)
    ry1 = float(rect.y1)

    for b in blocks:
        if not b or len(b) < 5:
            continue
        x0, y0, x1, y1, text = b[:5]
        if not text:
            continue
        m = _FIGURE_RE.search(str(text))
        if not m:
            continue
        bx0 = float(x0)
        bx1 = float(x1)
        by0 = float(y0)
        by1 = float(y1)
        overlap = _rect_overlap_ratio(rx0, rx1, bx0, bx1)
        if overlap < 0.2:
            continue
        if by0 >= ry1 - 2:
            dist = by0 - ry1
            if dist <= 120 and dist < best_dist:
                best_dist = dist
                best = m.group(0)
        elif ry0 >= by1 - 2:
            dist = ry0 - by1 + 50
            if dist < best_dist:
                best_dist = dist
                best = m.group(0)

    return _norm_figure_id(best) if best else None


def extract_pdf_images_to_data(pdf_path: str, out_subdir: str | None = None, limit: int | None = None) -> Tuple[str, List[ExtractedImage]]:
    try:
        import fitz  # type: ignore
    except Exception as e:
        raise RuntimeError("missing_dependency_pymupdf") from e

    dirs = ensure_knowledge_dirs()
    stem = _safe_stem(pdf_path)
    out_subdir = out_subdir or os.path.join("extracted", stem)
    out_dir = os.path.join(dirs["base"], out_subdir)
    os.makedirs(out_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    results: List[ExtractedImage] = []
    count = 0

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            images = page.get_images(full=True) or []
            for idx, img in enumerate(images):
                xref = img[0]
                extracted = doc.extract_image(xref) or {}
                raw = extracted.get("image") or b""
                if not raw:
                    continue
                figure_id = None
                try:
                    rects = page.get_image_rects(xref) or []
                    if rects:
                        figure_id = _find_near_figure_text(page, rects[0])
                except Exception:
                    figure_id = None
                file_name = f"{stem}_p{page_index + 1:03d}_{idx + 1:03d}.png"
                stored_path = os.path.join(out_dir, file_name)
                try:
                    png = _to_png(raw)
                except Exception:
                    png = raw
                with open(stored_path, "wb") as f:
                    f.write(png)
                rel = os.path.relpath(stored_path, dirs["base_data"])
                stored_url = f"/static/{rel.replace(os.sep, '/')}"
                results.append(
                    ExtractedImage(
                        file_name=file_name,
                        stored_path=stored_path,
                        stored_url=stored_url,
                        page=page_index + 1,
                        index_in_page=idx + 1,
                        figure_id=figure_id,
                    )
                )
                count += 1
                if limit is not None and count >= limit:
                    return out_dir, results
    finally:
        doc.close()

    return out_dir, results
