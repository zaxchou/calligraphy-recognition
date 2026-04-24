"""
bird_flower_ingest.py — Ingest bird_flower_tutorial knowledge into Qdrant.

DEPRECATED collections (knowledge_figures, knowledge_chapters, knowledge_artists)
have been consolidated into:
  - knowledge_images (1024-dim): Tutorial figure images with multimodal embeddings
  - knowledge_texts (1024-dim): Chapter sections and artist profiles with text embeddings

Usage:
    from app.modules.pantianshou_composition.bird_flower_ingest import (
        ingest_knowledge_figures,
        ingest_knowledge_chapters,
        ingest_knowledge_artists,
        ingest_all_bird_flower,
    )
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import cv2

from app.core.config import get_settings
from app.modules.pantianshou_composition.analyzer import to_feature_vector_1024
from app.modules.pantianshou_composition.qdrant_client import (
    ensure_collection,
    upsert_points,
    count_collection,
    search_collection,
    KNOWLEDGE_IMAGES_COLLECTION,
    KNOWLEDGE_TEXTS_COLLECTION,
    KNOWLEDGE_VECTOR_SIZE,
)
from app.modules.pantianshou_composition.storage import build_static_url

logger = logging.getLogger(__name__)

settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _knowledge_dir() -> str:
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    return os.path.join(base_data, "knowledge")


# ---------------------------------------------------------------------------
# 1. knowledge_figures — CLIP vectors for tutorial figure images
# ---------------------------------------------------------------------------

@dataclass
class FigureMeta:
    figure_id: str
    figure_num: int
    figure_type: str  # artwork | technique | unknown
    filename: Optional[str] = None
    image_path: Optional[str] = None
    page: Optional[int] = None
    era: str = ""
    artist: str = ""
    artwork_title: str = ""
    medium: str = ""
    size: str = ""
    year: str = ""
    collection_name: str = ""
    is_section: bool = False
    chapter: str = ""
    section: str = ""
    description: str = ""


def load_figure_metadata() -> Dict[str, FigureMeta]:
    """Load figure_metadata.json into structured FigureMeta objects."""
    meta_path = os.path.join(_knowledge_dir(), "figure_metadata.json")
    if not os.path.exists(meta_path):
        logger.warning("figure_metadata.json not found at %s", meta_path)
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, FigureMeta] = {}
    for fig_id, data in raw.items():
        out[fig_id] = FigureMeta(
            figure_id=data.get("figure_id", fig_id),
            figure_num=data.get("figure_num", 0),
            figure_type=data.get("figure_type", "unknown"),
            filename=data.get("filename"),
            image_path=data.get("image_path"),
            page=data.get("page"),
            era=data.get("era", ""),
            artist=data.get("artist", ""),
            artwork_title=data.get("artwork_title", ""),
            medium=data.get("medium", ""),
            size=data.get("size", ""),
            year=data.get("year", ""),
            collection_name=data.get("collection", ""),
            is_section=data.get("is_section", False),
            chapter=data.get("chapter", ""),
            section=data.get("section", ""),
            description=data.get("description", ""),
        )
    return out


def ingest_knowledge_figures(
    recreate: bool = False,
) -> Dict[str, Any]:
    """Ingest tutorial figure images with multimodal embeddings into knowledge_images.

    Uses DashScope multimodal-embedding-v1 (1024-dim) instead of CLIP (512-dim).
    """
    meta = load_figure_metadata()
    if not meta:
        return {"ok": False, "error": "no_figure_metadata"}

    ok = ensure_collection(KNOWLEDGE_IMAGES_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE, recreate=recreate)
    if not ok:
        return {"ok": False, "error": "qdrant_unavailable"}

    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    points: List[Dict[str, Any]] = []
    n_vectorized = 0
    n_zero = 0

    for fig_id, fm in meta.items():
        if not fm.image_path or not os.path.exists(fm.image_path):
            points.append(_build_figure_point(fm, vector=None))
            n_zero += 1
            continue

        # Use multimodal embedding (1024-dim) via DashScope API
        try:
            vec = to_feature_vector_1024(fm.image_path)
        except Exception as e:
            logger.warning("Failed to vectorize %s: %s", fig_id, e)
            vec = None

        # Build image URL
        rel = os.path.relpath(fm.image_path, base_data_dir)
        image_url = build_static_url(rel)

        points.append(_build_figure_point(fm, vector=vec, image_url=image_url))
        if vec is not None:
            n_vectorized += 1
        else:
            n_zero += 1

    success = upsert_points(KNOWLEDGE_IMAGES_COLLECTION, points, wait=True)
    return {
        "ok": bool(success),
        "collection": KNOWLEDGE_IMAGES_COLLECTION,
        "total": len(points),
        "vectorized": n_vectorized,
        "zero_vector": n_zero,
    }


def _build_figure_point(
    fm: FigureMeta,
    vector: Optional[List[float]] = None,
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"knowledge_fig:{fm.figure_id}"))
    payload: Dict[str, Any] = {
        "type": "knowledge_figure",
        "source": "bird_flower_tutorial",
        "figure_id": fm.figure_id,
        "figure_num": fm.figure_num,
        "figure_type": fm.figure_type,
        "era": fm.era,
        "artist": fm.artist,
        "artwork_title": fm.artwork_title,
        "medium": fm.medium,
        "size": fm.size,
        "year": fm.year,
        "collection": fm.collection_name,
        "is_section": fm.is_section,
        "chapter": fm.chapter,
        "page": fm.page,
    }
    if fm.description:
        payload["description"] = fm.description
    if image_url:
        payload["image_url"] = image_url
    return {
        "id": point_id,
        "vector": vector or [0.0] * KNOWLEDGE_VECTOR_SIZE,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# 2. knowledge_chapters — Chapter section embeddings
# ---------------------------------------------------------------------------

_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十]+章\s+(.+?)(?:\s*•|\s*$)")
_SECTION_RE = re.compile(r"^第[一二三四五六七八九十]+节\s+(.+?)(?:\s*$)")
_PAGE_RE = re.compile(r"===== PAGE (\d+) =====")
_SUB_TOPIC_RE = re.compile(r"^(?:[一二三四五六七八九十]+)[、.]?\s+(.{2,30})")


@dataclass
class ChapterSection:
    chapter_num: int
    chapter_title: str
    section_num: int
    section_title: str
    page_start: int
    page_end: int
    full_text: str
    keywords: List[str] = field(default_factory=list)
    related_figures: List[str] = field(default_factory=list)


def parse_chapters(text: str) -> List[ChapterSection]:
    """Parse bird_flower_tutorial.txt into chapter sections."""
    lines = text.splitlines()
    sections: List[ChapterSection] = []

    chapter_num = 0
    chapter_title = ""
    section_num = 0
    section_title = ""
    page_start = 0
    section_lines: List[str] = []

    def _flush():
        nonlocal section_lines
        full = "\n".join(section_lines).strip()
        if full and chapter_num > 0:
            sections.append(ChapterSection(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                section_num=section_num,
                section_title=section_title,
                page_start=page_start,
                page_end=page_start,
                full_text=full,
            ))
        section_lines = []

    for line in lines:
        stripped = line.strip()

        # Track page numbers
        m_page = _PAGE_RE.match(stripped)
        if m_page:
            page_num = int(m_page.group(1))
            if sections:
                sections[-1].page_end = page_num
            continue

        # Detect chapter headers
        m_ch = _CHAPTER_RE.match(stripped)
        if m_ch:
            _flush()
            chapter_num += 1
            chapter_title = m_ch.group(1).strip()
            section_num = 0
            section_title = ""
            continue

        # Detect section headers
        m_sec = _SECTION_RE.match(stripped)
        if m_sec:
            _flush()
            section_num += 1
            section_title = m_sec.group(1).strip()
            continue

        # Skip empty lines and page markers
        if not stripped or stripped.startswith("====="):
            continue

        section_lines.append(stripped)

    _flush()
    return sections


def ingest_knowledge_chapters(
    recreate: bool = False,
) -> Dict[str, Any]:
    """Ingest chapter sections into knowledge_texts collection (1024-dim).

    Uses multimodal-embedding-v1 text encoding for semantic search.
    """
    txt_path = os.path.join(_repo_root(), "bird_flower_tutorial.txt")
    if not os.path.exists(txt_path):
        return {"ok": False, "error": "txt_not_found"}

    text = _read_text(txt_path)
    chapters = parse_chapters(text)

    ok = ensure_collection(KNOWLEDGE_TEXTS_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE, recreate=recreate)
    if not ok:
        return {"ok": False, "error": "qdrant_unavailable"}

    # Generate text embeddings using DashScope multimodal-embedding-v1
    chapter_texts = []
    for ch in chapters:
        chapter_texts.append(f"{ch.chapter_title} {ch.section_title}\n{ch.full_text}")

    embeddings: List[List[float]] = []
    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        service = EmbeddingService()
        results = service.embed_texts_sync(chapter_texts)
        embeddings = [r.embedding for r in results]
    except Exception as e:
        logger.error("Failed to generate embeddings for chapters: %s, using zero vectors", e)
        embeddings = [[0.0] * KNOWLEDGE_VECTOR_SIZE for _ in chapters]

    points: List[Dict[str, Any]] = []
    for i, ch in enumerate(chapters):
        keywords = _extract_keywords(ch.section_title, ch.full_text[:500])
        fig_refs = re.findall(r"（图\s*(\d+)）", ch.full_text)
        fig_refs += re.findall(r"（图\s*(\d+)\s", ch.full_text)
        related_figs = [f"图{fig}" for fig in fig_refs[:10]]

        point_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"knowledge_ch:ch{ch.chapter_num}_sec{ch.section_num}"
        ))
        payload = {
            "type": "knowledge_chapter",
            "source": "bird_flower_tutorial",
            "book": "中国写意花鸟画教程",
            "chapter_num": ch.chapter_num,
            "chapter_title": ch.chapter_title,
            "section_num": ch.section_num,
            "section_title": ch.section_title,
            "page_start": ch.page_start,
            "page_end": ch.page_end,
            "keywords": keywords,
            "related_figures": related_figs,
            "text_preview": ch.full_text[:300],
            "content": ch.full_text,  # Full text for BM25 search
        }
        vec = embeddings[i] if i < len(embeddings) else [0.0] * KNOWLEDGE_VECTOR_SIZE
        points.append({
            "id": point_id,
            "vector": vec,
            "payload": payload,
        })

    success = upsert_points(KNOWLEDGE_TEXTS_COLLECTION, points, wait=True)
    return {
        "ok": bool(success),
        "collection": KNOWLEDGE_TEXTS_COLLECTION,
        "sections_count": len(points),
    }


def _extract_keywords(title: str, text_sample: str) -> List[str]:
    """Extract keywords from section title and text."""
    keywords = set()
    # From title
    if title:
        keywords.add(title.strip())
    # Common art terms
    art_terms = [
        "构图", "章法", "布局", "笔墨", "用笔", "用墨", "设色",
        "疏密", "虚实", "开合", "气势", "留白", "款印", "穿插",
        "造形", "一笔造形", "写意", "花鸟", "梅兰竹菊",
        "勾花点叶", "点厾", "泼墨", "破墨", "积墨",
        "吴昌硕", "八大山人", "朱耷", "石涛", "齐白石", "潘天寿",
        "金农", "徐渭", "扬州八怪", "海派",
        "主次呼应", "均衡稳定", "疏密聚散", "穿插交叉",
        "开合起结", "大小相间", "藏露向背", "题款钤印",
        "占边占角", "杆秤", "蓄势", "女字交叉", "直起横破",
    ]
    for term in art_terms:
        if term in text_sample:
            keywords.add(term)
    return sorted(list(keywords))[:15]


# ---------------------------------------------------------------------------
# 3. knowledge_artists — Artist profiles
# ---------------------------------------------------------------------------

@dataclass
class ArtistProfile:
    name: str
    era: str
    works: List[str]
    figure_ids: List[str]
    mediums: List[str]
    collections: List[str]
    specialties: List[str] = field(default_factory=list)
    description: str = ""


def load_artist_profiles() -> Dict[str, ArtistProfile]:
    """Load artist_index.json into structured ArtistProfile objects."""
    artist_path = os.path.join(_knowledge_dir(), "artist_index.json")
    if not os.path.exists(artist_path):
        logger.warning("artist_index.json not found at %s", artist_path)
        return {}
    with open(artist_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, ArtistProfile] = {}
    for name, data in raw.items():
        out[name] = ArtistProfile(
            name=data.get("name", name),
            era=data.get("era", ""),
            works=data.get("works", []),
            figure_ids=data.get("figure_ids", []),
            mediums=data.get("mediums", []),
            collections=data.get("collections", []),
        )
    # Add specialty descriptions
    _add_specialties(out)
    return out


def _add_specialties(artists: Dict[str, ArtistProfile]):
    """Add composition specialties based on artist knowledge."""
    specialty_map = {
        "朱耷": ["简约洗练", "形疏意密", "布白自觉", "款印分割", "大疏大密", "蓄势借力"],
        "吴昌硕": ["纵横互破", "斜势章法", "占边占角", "大实空白", "画气不画形", "金石味"],
        "石涛": ["一画论", "纵横泼辣", "破势", "笔墨酣畅", "四边开合"],
        "徐渭": ["大写意", "草书入画", "豪放俊发", "气势逼人", "折枝斜势"],
        "金农": ["漆书入画", "大密中疏", "朴拙浑厚", "款印分割空间"],
        "潘天寿": ["几何分割", "方圆并用", "黑线交错", "强其骨", "奇险造境"],
        "齐白石": ["极工而后写意", "精微笔墨", "红花墨叶", "天真烂漫"],
        "华喦": ["小写意", "形疏意密", "外柔内刚", "机趣天成"],
        "李鱓": ["破笔泼墨", "用水有法", "气势豪放", "款印造势"],
        "林良": ["大斧劈法", "点垛法", "水墨兼施", "写意花鸟创始人"],
        "郑燮": ["兰竹专精", "六分半书", "长跋题画", "款代石壁"],
        "刘海勇": ["学院派", "写意花鸟教学", "笔墨结构"],
    }
    for name, specs in specialty_map.items():
        if name in artists:
            artists[name].specialties = specs


def ingest_knowledge_artists(
    recreate: bool = False,
) -> Dict[str, Any]:
    """Ingest artist profiles into knowledge_texts collection (1024-dim).

    Uses multimodal-embedding-v1 text encoding for semantic search.
    """
    artists = load_artist_profiles()
    if not artists:
        return {"ok": False, "error": "no_artist_profiles"}

    ok = ensure_collection(KNOWLEDGE_TEXTS_COLLECTION, vector_size=KNOWLEDGE_VECTOR_SIZE, recreate=recreate)
    if not ok:
        return {"ok": False, "error": "qdrant_unavailable"}

    # Generate text embeddings
    artist_texts = []
    for name, profile in artists.items():
        text_parts = [
            profile.name,
            profile.era,
            " ".join(profile.specialties),
            " ".join(profile.works),
            " ".join(profile.mediums),
        ]
        artist_texts.append(" ".join(text_parts))

    embeddings: List[List[float]] = []
    try:
        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        service = EmbeddingService()
        results = service.embed_texts_sync(artist_texts)
        embeddings = [r.embedding for r in results]
    except Exception as e:
        logger.error("Failed to generate embeddings for artists: %s, using zero vectors", e)
        embeddings = [[0.0] * KNOWLEDGE_VECTOR_SIZE for _ in artists]

    points: List[Dict[str, Any]] = []
    for i, (name, profile) in enumerate(artists.items()):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"knowledge_artist:{name}"))
        payload = {
            "type": "knowledge_artist",
            "source": "bird_flower_tutorial",
            "name": profile.name,
            "era": profile.era,
            "works": profile.works,
            "figure_ids": profile.figure_ids,
            "mediums": profile.mediums,
            "collections": profile.collections,
            "specialties": profile.specialties,
            "keywords": profile.specialties + [profile.era] + profile.works,
            "content": " ".join([
                profile.name, profile.era,
                " ".join(profile.specialties),
                " ".join(profile.works),
                " ".join(profile.mediums),
            ]),
        }
        vec = embeddings[i] if i < len(embeddings) else [0.0] * KNOWLEDGE_VECTOR_SIZE
        points.append({
            "id": point_id,
            "vector": vec,
            "payload": payload,
        })

    success = upsert_points(KNOWLEDGE_TEXTS_COLLECTION, points, wait=True)
    return {
        "ok": bool(success),
        "collection": KNOWLEDGE_TEXTS_COLLECTION,
        "artists_count": len(points),
    }


# ---------------------------------------------------------------------------
# Master ingest function
# ---------------------------------------------------------------------------

def ingest_all_bird_flower(recreate: bool = False) -> Dict[str, Any]:
    """Run all bird_flower_tutorial ingestion steps."""
    results: Dict[str, Any] = {}

    r1 = ingest_knowledge_figures(recreate=recreate)
    results["figures"] = r1

    r2 = ingest_knowledge_chapters(recreate=recreate)
    results["chapters"] = r2

    r3 = ingest_knowledge_artists(recreate=recreate)
    results["artists"] = r3

    results["ok"] = all(r.get("ok") for r in [r1, r2, r3])
    return results
